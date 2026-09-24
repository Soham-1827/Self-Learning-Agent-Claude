"""YouTube source, backed by yt-dlp. No API key required (D5)."""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from ..cache import Cache
from ..config import Config
from ..models import Chapter, Link, SourceDocument, TextQuality, TranscriptSegment

VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
_URL_ID_PATTERNS = (
    re.compile(r"(?:youtube\.com/watch\?(?:.*&)?v=)([A-Za-z0-9_-]{11})"),
    re.compile(r"(?:youtu\.be/)([A-Za-z0-9_-]{11})"),
    re.compile(r"(?:youtube\.com/(?:shorts|embed|live)/)([A-Za-z0-9_-]{11})"),
)
_URL_IN_TEXT = re.compile(r"https?://[^\s<>\)\]\}\"']+")
# "en", "en-orig", "en-GB", "en_US" — but not "eng" or "enigma".
_EN_TRACK = re.compile(r"^en(?![A-Za-z])")
# Every English track, if the metadata recording them predates this code (§23).
_LEGACY_TRACKS = ("en", "en.*")
_RATE_LIMITED = re.compile(r"\b429\b|too many requests", re.IGNORECASE)
# Each retry waits this much longer than the last: 5s, then 20s by default,
# and never more than MAX_BACKOFF_SECONDS however many attempts are configured.
BACKOFF_FACTOR = 4
MAX_BACKOFF_SECONDS = 120.0
_TRAILING_PUNCT = ".,;:!?"
# "label — https://url" / "label - https://url" / "label: https://url"
_LABELLED = re.compile(r"^(?P<label>.{2,80}?)\s*[—–\-:]\s*(?P<url>https?://\S+)$")


class YouTubeError(RuntimeError):
    pass


class YouTubeSource:
    source_type = "youtube"

    def __init__(self, config: Config, cache: Cache | None = None) -> None:
        self.config = config.resolved()
        self.cache = cache or Cache(self.config.cache_dir)

    # -- reference handling ------------------------------------------------

    def handles(self, ref: str) -> bool:
        ref = ref.strip()
        return bool(
            "youtube.com" in ref
            or "youtu.be" in ref
            or ref.startswith("@")
            or VIDEO_ID.match(ref)
        )

    def resolve(self, ref: str, limit: int = 1) -> list[str]:
        """URL, bare id, or @handle -> video ids (newest first for a channel)."""
        ref = ref.strip()
        if VIDEO_ID.match(ref):
            return [ref]
        for pattern in _URL_ID_PATTERNS:
            if match := pattern.search(ref):
                return [match.group(1)]
        if ref.startswith("@") or "/@" in ref or "/channel/" in ref:
            return self._channel_video_ids(ref, limit)
        raise YouTubeError(f"Could not resolve a YouTube reference from: {ref!r}")

    def _channel_video_ids(self, ref: str, limit: int) -> list[str]:
        handle = ref if ref.startswith("http") else f"https://www.youtube.com/{ref}"
        url = handle.rstrip("/")
        if not url.endswith("/videos"):
            url += "/videos"
        out = self._run(
            ["--flat-playlist", "--dump-json", "--playlist-end", str(limit), url]
        )
        ids = []
        for line in out.splitlines():
            if not line.strip():
                continue
            entry = json.loads(line)
            if vid := entry.get("id"):
                ids.append(vid)
        return ids[:limit]

    # -- fetching ----------------------------------------------------------

    def fetch(self, source_id: str, *, refresh: bool = False) -> SourceDocument:
        meta = None if refresh else self.cache.get(self.source_type, source_id, "meta")
        if meta is None:
            meta = self._fetch_metadata(source_id)
            self.cache.put(self.source_type, source_id, "meta", meta)

        captions = (
            None if refresh else self.cache.get(self.source_type, source_id, "captions")
        )
        if captions is None:
            captions = self._fetch_captions(source_id, meta)
            self.cache.put(self.source_type, source_id, "captions", captions)

        return self._build(source_id, meta, captions)

    def metadata(self, source_id: str, *, refresh: bool = False) -> dict:
        """Metadata only — never captions. Cached exactly as `fetch` caches it.

        Triage calls this for every candidate on a channel, so it has to stay
        cheap: one yt-dlp metadata call per video, none on a cache hit, and no
        transcript download at any point.
        """
        meta = None if refresh else self.cache.get(self.source_type, source_id, "meta")
        if meta is None:
            meta = self._fetch_metadata(source_id)
            self.cache.put(self.source_type, source_id, "meta", meta)
        return meta

    def _fetch_metadata(self, video_id: str) -> dict:
        url = f"https://www.youtube.com/watch?v={video_id}"
        raw = self._run(["--skip-download", "--dump-single-json", url])
        full = json.loads(raw)
        # Keep only what the pipeline uses; the raw payload is ~660KB of formats.
        keep = (
            "id", "title", "description", "channel", "uploader", "uploader_id",
            "channel_id", "upload_date", "duration", "view_count", "webpage_url",
            "chapters", "tags", "categories",
        )
        meta = {k: full.get(k) for k in keep}
        # The names, not just a yes/no: only one track gets requested, so the
        # caption download has to know which one to ask for.
        meta["_en_manual"] = list(_english_tracks(full.get("subtitles")))
        meta["_en_auto"] = list(_english_tracks(full.get("automatic_captions")))
        meta["_has_manual_en"] = bool(meta["_en_manual"])
        meta["_has_auto_en"] = bool(meta["_en_auto"])
        return meta

    def _fetch_captions(self, video_id: str, meta: dict) -> dict:
        """Captions for a video; {} only when the video genuinely has none.

        A failure must never look like an absence. The result is cached, so a
        transient rate-limit that returned {} would become a permanent "this
        video has no transcript" — and the note would be written from the
        description alone without anyone noticing.
        """
        if "_has_manual_en" not in meta and "_has_auto_en" not in meta:
            # Metadata this old cannot tell "no captions" from "never asked",
            # and {} here would be cached as the former (§23).
            raise YouTubeError(
                f"metadata for {video_id} predates the caption check; re-fetch it "
                f"with --refresh so 'no captions' is an answer rather than a silence"
            )
        url = f"https://www.youtube.com/watch?v={video_id}"
        manual = bool(meta.get("_has_manual_en"))
        if not manual and not meta.get("_has_auto_en"):
            return {}
        flag = "--write-subs" if manual else "--write-auto-subs"

        reason = "no output"
        for track in _caption_tracks(meta, manual=manual):
            payload, stderr = self._download_track(url, flag, track)
            if payload is not None:
                payload["_quality"] = (
                    TextQuality.MANUAL_CAPTIONS if manual else TextQuality.AUTO_CAPTIONS
                )
                return payload
            reason = _error_summary(stderr)
            if _is_rate_limited(stderr):
                # The refusal is about the video, not the track. Asking for
                # another one spends a request to be refused again.
                break
        # Metadata said captions exist, so this is a failure, not an absence.
        raise YouTubeError(f"captions for {video_id} were not downloaded: {reason}")

    def _download_track(self, url: str, flag: str, track: str):
        """One subtitle request. Returns (payload, stderr); payload is None on failure."""
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "cap"
            _, stderr = self._run([
                "--skip-download", flag, "--sub-langs", track,
                "--sub-format", "json3", "-o", str(out), url,
            ], with_stderr=True)
            files = sorted(Path(tmp).glob("*.json3"))
            if not files:
                return None, stderr
            return json.loads(files[0].read_text(encoding="utf-8")), stderr

    def _run(self, args: list[str], *, with_stderr: bool = False):
        """Run yt-dlp; return stdout, or (stdout, stderr) when asked.

        yt-dlp can print an ERROR and still exit 0 — a rate-limited subtitle
        download does exactly that — so a caller that cares must read stderr,
        and so must the decision to retry.

        `HTTP 429` is a wait, not a verdict: a channel run spends one request
        per candidate before it reads anything, and the first live one was
        refused part-way through (§23). Every other failure is final, because
        asking again for a video that does not exist only spends the budget
        that made this fail.

        This reads an `ERROR` line as "the call failed", which is what makes the
        exit-0 case detectable at all. Where yt-dlp asks for several things at
        once it can refuse one and deliver another, and a retry then repeats
        work that succeeded. Only the legacy `en.*` fallback does that, and it
        costs a request rather than a wrong answer, so the simpler rule stands.
        """
        cmd = [*self.config.ytdlp_cmd, "--no-warnings", *args]
        attempts = max(1, self.config.ytdlp_attempts)
        for attempt in range(1, attempts + 1):
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if attempt == attempts or not _is_rate_limited(proc.stderr):
                break
            time.sleep(_backoff(self.config.ytdlp_backoff_seconds, attempt))
        if proc.returncode != 0:
            raise YouTubeError(
                f"yt-dlp failed ({proc.returncode}): {_error_summary(proc.stderr)}"
            )
        return (proc.stdout, proc.stderr) if with_stderr else proc.stdout

    def _build(self, video_id: str, meta: dict, captions: dict) -> SourceDocument:
        segments = parse_json3(captions)
        description = meta.get("description") or ""
        quality = captions.get("_quality") if captions else TextQuality.NONE
        return SourceDocument(
            source_type=self.source_type,
            source_id=video_id,
            title=meta.get("title") or video_id,
            text=" ".join(s.text for s in segments),
            text_quality=quality or TextQuality.NONE,
            url=meta.get("webpage_url") or f"https://www.youtube.com/watch?v={video_id}",
            author=meta.get("channel") or meta.get("uploader"),
            author_id=meta.get("uploader_id") or meta.get("channel_id"),
            published_at=_parse_date(meta.get("upload_date")),
            duration_seconds=meta.get("duration"),
            description=description,
            chapters=parse_chapters(meta.get("chapters")),
            links=extract_links(description),
            segments=segments,
            fetched_at=datetime.now(timezone.utc),
            extra={
                "view_count": meta.get("view_count"),
                "tags": meta.get("tags") or [],
            },
        )


# -- pure helpers (unit-testable without the network) ----------------------


def video_id_from_ref(ref: str) -> str | None:
    """A video id from a bare id or any common video URL; None for anything else.

    Pure — unlike `YouTubeSource.resolve`, it never shells out, so it is safe to
    use where a reference only needs recognising, not resolving.
    """
    ref = (ref or "").strip()
    if VIDEO_ID.match(ref):
        return ref
    for pattern in _URL_ID_PATTERNS:
        if match := pattern.search(ref):
            return match.group(1)
    return None


def _backoff(base: float, attempt: int) -> float:
    """How long to wait before attempt+1, bounded.

    `ytdlp_attempts` is the owner's to set, and 4** grows fast enough that a
    generous value would otherwise park a run for hours.
    """
    return min(base * BACKOFF_FACTOR ** (attempt - 1), MAX_BACKOFF_SECONDS)


def _english_tracks(available: dict | None) -> tuple[str, ...]:
    """English caption track names, best first.

    A track named `<lang>-orig` is the video's own language rather than a machine
    translation of it, so it leads. The order decides which single track gets
    requested: `--sub-langs "en.*"` matched both `en` and `en-orig` and spent two
    subtitle requests per video where one would do (§23).
    """
    names = [k for k in (available or {}) if _EN_TRACK.match(k)]
    return tuple(sorted(names, key=lambda n: (not n.endswith("-orig"), n != "en", n)))


def _caption_tracks(meta: dict, *, manual: bool) -> tuple[str, ...]:
    """Which tracks to try, in order: one request, then a fallback if it fails.

    Metadata cached before the track names were recorded carries only the
    booleans. Asking for `en` and keeping the old `en.*` pattern as the fallback
    applies the same one-request-first rule to an older cache entry.
    """
    recorded = meta.get("_en_manual" if manual else "_en_auto")
    return tuple(recorded) if recorded else _LEGACY_TRACKS


def _error_lines(stderr: str | None) -> list[str]:
    """yt-dlp's own ERROR lines — the ones that mean it gave up."""
    return [
        line.strip()
        for line in (stderr or "").splitlines()
        if line.strip().startswith("ERROR")
    ]


def _is_rate_limited(stderr: str | None) -> bool:
    """Is YouTube refusing us for asking too often?

    Only ERROR lines count. yt-dlp retries internally and narrates it, and a
    warning it recovered from is not a failure to retry again from out here.
    """
    return any(_RATE_LIMITED.search(line) for line in _error_lines(stderr))


def _error_summary(stderr: str | None, limit: int = 400) -> str:
    """The part of yt-dlp's stderr that says what actually went wrong.

    yt-dlp prints warnings and notices first — the Python 3.10 deprecation among
    them — and its ERROR line last, so the head of stderr is its least useful part.
    """
    lines = [line.strip() for line in (stderr or "").splitlines() if line.strip()]
    errors = _error_lines(stderr)
    summary = errors[-1] if errors else (lines[-1] if lines else "no output")
    return summary[-limit:]


def parse_json3(payload: dict | None) -> tuple[TranscriptSegment, ...]:
    """YouTube json3 captions -> timestamped segments."""
    if not payload:
        return ()
    segments = []
    for event in payload.get("events") or []:
        text = "".join(s.get("utf8", "") for s in (event.get("segs") or []))
        text = text.replace("\n", " ").strip()
        if not text:
            continue
        segments.append(
            TranscriptSegment(start=(event.get("tStartMs") or 0) / 1000.0, text=text)
        )
    return tuple(segments)


def parse_chapters(raw: list | None) -> tuple[Chapter, ...]:
    if not raw:
        return ()
    return tuple(
        Chapter(start=float(c.get("start_time") or 0), title=(c.get("title") or "").strip())
        for c in raw
    )


def extract_links(description: str | None) -> tuple[Link, ...]:
    """URLs from human-typed description text, labelled where the line offers one.

    These carry the authoritative spelling of entity names (I1): ASR renders
    "SkillSpector" as "Skill Specter", but the description holds the real URL.
    """
    if not description:
        return ()
    seen: dict[str, Link] = {}
    for line in description.splitlines():
        line = line.strip()
        label = None
        if match := _LABELLED.match(line):
            label = match.group("label").strip() or None
        for url in _URL_IN_TEXT.findall(line):
            url = url.rstrip(_TRAILING_PUNCT)
            if url in seen:
                continue
            seen[url] = Link(url=url, label=label)
    return tuple(seen.values())


def _parse_date(value: str | None) -> datetime | None:
    if not value or len(value) != 8:
        return None
    try:
        return datetime.strptime(value, "%Y%m%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
