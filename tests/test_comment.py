import json

from shd.cli import main
from shd.detect import DriftResult
from shd.post_comment import upsert_comment
from shd.report import MARKER, render_comment

DOCS = [{"id": "d.md::A"}, {"id": "d.md::B"}, {"id": "d.md::C"}]
RESULTS = [
    DriftResult(code_id=None, doc_id="d.md::A", detection="reference", is_stale=True, tier="stale",
                reason="doc references no longer in code: route /v1/x", suggested_fix="update"),
    DriftResult(code_id="a.py::f", doc_id="d.md::B", detection="llm", is_stale=True, tier="review",
                reason="prose claim", doc_claim="returns ten results", suggested_fix="say twenty"),
    DriftResult(code_id="a.py::f", doc_id="d.md::C", detection="llm", is_stale=False),
]


def test_comment_has_marker_and_two_separate_sections():
    text = render_comment(DOCS, RESULTS, {"changed_chunks": 2, "calls": 5})
    assert text.startswith(MARKER)
    stale, review = text.index("### Stale"), text.index("### Worth a look")
    assert stale < text.index("d.md::A") < review < text.index("d.md::B")
    assert "d.md::C" not in text and "returns ten results" in text and "2 changed code chunk(s)" in text


def test_comment_without_flags_says_so_and_keeps_marker():
    text = render_comment(DOCS, [], {"changed_chunks": 0})
    assert MARKER in text and "No stale docs found." in text and "### Stale" not in text


def test_comment_reports_budget_stop():
    assert "3 comparison(s) were not checked" in render_comment(DOCS, [], {"unchecked": 3})


class FakeComment:
    def __init__(self, body):
        self.body, self.edited = body, None

    def edit(self, body):
        self.edited = body


class FakeIssue:
    def __init__(self, bodies):
        self.comments, self.created = [FakeComment(b) for b in bodies], []

    def get_comments(self):
        return self.comments

    def create_comment(self, body):
        self.created.append(body)


def test_upsert_creates_when_no_marker_comment_exists():
    issue = FakeIssue(["unrelated", "lgtm"])
    assert upsert_comment(issue, f"{MARKER}\nnew") == "created"
    assert issue.created == [f"{MARKER}\nnew"] and all(c.edited is None for c in issue.comments)


def test_upsert_updates_the_existing_marker_comment_only():
    issue = FakeIssue(["unrelated", f"{MARKER}\nold"])
    assert upsert_comment(issue, f"{MARKER}\nnew") == "updated"
    assert issue.comments[1].edited == f"{MARKER}\nnew" and issue.comments[0].edited is None and not issue.created


def test_cli_writes_comment_file(tmp_path):
    from pathlib import Path
    out, comment = tmp_path / "r.json", tmp_path / "c.md"
    main(["check", "--fixture", str(Path(__file__).parent.parent / "fixtures" / "01_wrong_path_missing_param"),
          "--out", str(out), "--comment-file", str(comment), "--fake"])
    assert MARKER in comment.read_text() and "### Stale" in comment.read_text()
