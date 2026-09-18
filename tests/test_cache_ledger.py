from pathlib import Path

from self_learning_agent.cache import Cache
from self_learning_agent.ledger import Ledger


def test_cache_round_trips(tmp_path: Path):
    cache = Cache(tmp_path)
    cache.put("youtube", "abc", "meta", {"title": "x"})
    assert cache.get("youtube", "abc", "meta") == {"title": "x"}


def test_cache_miss_is_none_not_an_error(tmp_path: Path):
    assert Cache(tmp_path).get("youtube", "nope", "meta") is None


def test_corrupt_entry_is_treated_as_a_miss(tmp_path: Path):
    cache = Cache(tmp_path)
    path = cache.path_for("youtube", "abc", "meta")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{ not json", encoding="utf-8")
    assert cache.get("youtube", "abc", "meta") is None


def test_source_ids_cannot_escape_the_cache_directory(tmp_path: Path):
    cache = Cache(tmp_path)
    path = cache.path_for("youtube", "../../etc/passwd", "meta")
    assert tmp_path.resolve() in path.resolve().parents


def test_ledger_dedupes_processed_sources(tmp_path: Path):
    ledger = Ledger(tmp_path / "l.db")
    assert not ledger.seen("youtube", "a")
    ledger.record("youtube", "a", title="A")
    assert ledger.seen("youtube", "a")
    assert ledger.unseen("youtube", ["a", "b", "c"]) == ["b", "c"]


def test_recording_twice_updates_rather_than_duplicates(tmp_path: Path):
    ledger = Ledger(tmp_path / "l.db")
    ledger.record("youtube", "a", title="first")
    ledger.record("youtube", "a", title="second", status="applied")
    rows = ledger.all()
    assert len(rows) == 1
    assert rows[0]["title"] == "second"
    assert rows[0]["status"] == "applied"


def test_same_id_on_different_source_types_are_distinct(tmp_path: Path):
    ledger = Ledger(tmp_path / "l.db")
    ledger.record("youtube", "a")
    assert not ledger.seen("article", "a")


def test_recording_without_a_title_keeps_the_existing_one(tmp_path: Path):
    """`sla apply` updates only the status, and that used to erase the title.

    Found on the first real approval: the ledger then listed the video as
    `[applied] 9_SZFIW7tus` with no title at all.
    """
    ledger = Ledger(tmp_path / "l.db")
    ledger.record("youtube", "a", title="A title", url="https://x", note_path="/n.md")
    ledger.record("youtube", "a", status="applied")
    row = ledger.all()[0]
    assert (row["title"], row["url"], row["note_path"], row["status"]) == (
        "A title", "https://x", "/n.md", "applied",
    )

