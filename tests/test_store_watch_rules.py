from app.services.store import _normalize_watch_rule_tlds


def test_normalize_watch_rule_tlds_adds_dot_and_deduplicates() -> None:
    assert _normalize_watch_rule_tlds(["io", ".ai", " RU ", "", "io"]) == [".io", ".ai", ".ru"]


def test_normalize_watch_rule_tlds_leaves_empty_list_empty() -> None:
    assert _normalize_watch_rule_tlds(None) == []
