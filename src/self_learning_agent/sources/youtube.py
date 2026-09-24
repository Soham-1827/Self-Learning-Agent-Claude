"""YouTube source, backed by yt-dlp. No API key required (D5)."""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
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
        meta["_has_manual_en"] = any(
            k.startswith("en") for k in (full.get("subtitles") or {})
        )
        meta["_has_auto_en"] = any(
            k.startswith("en") for k in (full.get("automatic_captions") or {})
        )
        return meta

    def _fetch_captions(self, video_id: str, meta: dict) -> dict:
        """Captions for a video; {} only when the video genuinely has none.

        A failure must never look like an absence. The result is cached, so a
        transient rate-limit that returned {} would become a permanent "this
        video has no transcript" — and the note would be written from the
        description alone without anyone noticing.
        """
        url = f"https://www.youtube.com/watch?v={video_id}"
        manual = bool(meta.get("_has_manual_en"))
        if not manual and not meta.get("_has_auto_en"):
            return {}
        flag = "--write-subs" if manual else "--write-auto-subs"
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "cap"
            _, stderr = self._run([
                "--skip-download", flag, "--sub-langs", "en.*",
                "--sub-format", "json3", "-o", str(out), url,
            ], with_stderr=True)
            files = sorted(Path(tmp).glob("*.json3"))
            if not files:
                # Metadata said captions exist, so this is a failure, not an absence.
                raise YouTubeError(
                    f"captions for {video_id} were not downloaded: {_error_summary(stderr)}"
                )
            payload = json.loads(files[0].read_text(encoding="utf-8"))
        payload["_quality"] = (
            TextQuality.MANUAL_CAPTIONS if manual else TextQuality.AUTO_CAPTIONS
        )
        return payload

    def _run(self, args: list[str], *, with_stderr: bool = False):
        """Run yt-dlp; return stdout, or (stdout, stderr) when asked.

        yt-dlp can print an ERROR and still exit 0 — a rate-limited subtitle
        download does exactly that — so a caller that cares must read stderr.
        """
        cmd = [*self.config.ytdlp_cmd, "--no-warnings", *args]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
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


def _error_summary(stderr: str | None, limit: int = 400) -> str:
    """The part of yt-dlp's stderr that says what actually went wrong.

    yt-dlp prints warnings and notices first — the Python 3.10 deprecation among
    them — and its ERROR line last, so the head of stderr is its least useful part.
    """
    lines = [line.strip() for line in (stderr or "").splitlines() if line.strip()]
    errors = [line for line in lines if line.startswith("ERROR")]
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
