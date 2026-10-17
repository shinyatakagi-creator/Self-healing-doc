import re
from pathlib import Path

import pytest
import yaml

WORKFLOWS = sorted((Path(__file__).parent.parent / ".github" / "workflows").glob("*.yml"))
IDS = [p.name for p in WORKFLOWS]


def load(path):
    return yaml.safe_load(path.read_text())


@pytest.mark.parametrize("path", WORKFLOWS, ids=IDS)
def test_workflow_hardening(path):
    wf, text = load(path), path.read_text()
    assert wf["concurrency"]["cancel-in-progress"] is True
    assert wf["permissions"]["contents"] == "read" and "write-all" not in text
    for job in wf["jobs"].values():
        assert job["runs-on"] == "ubuntu-24.04" and job["timeout-minutes"] <= 15
        for step in job["steps"]:
            assert "${{" not in step.get("run", ""), f"expression inside run: in {path.name}"
            if "uses" in step:
                assert re.fullmatch(r"[\w.-]+/[\w.-]+@(v\d+|[0-9a-f]{40})", step["uses"]), step["uses"]


@pytest.mark.parametrize("path", WORKFLOWS, ids=IDS)
def test_secret_steps_are_guarded_against_forks_and_dependabot(path):
    wf = load(path)
    for job in wf["jobs"].values():
        for step in job["steps"]:
            uses_api_key = bool(re.search(r"secrets\.(OPENAI|ANTHROPIC)_API_KEY", str(step)))
            guarded = f"{job.get('if', '')} {step.get('if', '')}"
            if uses_api_key or "secrets.GITHUB_TOKEN" in str(step):
                assert "head.repo.full_name == github.repository" in guarded and "dependabot[bot]" in guarded


def test_ai_reviewer_cannot_approve_or_push():
    wf = load(next(p for p in WORKFLOWS if p.name == "ai-review.yml"))
    step = next(s for s in wf["jobs"]["review"]["steps"] if "claude-code-action" in s.get("uses", ""))
    args = step["with"]["claude_args"]
    allowed = re.search(r'--allowedTools "([^"]*)"', args).group(1).split(",")
    disallowed = re.search(r'--disallowedTools "([^"]*)"', args).group(1).split(",")
    assert not [t for t in allowed if t in ("Edit", "Write", "MultiEdit") or t.startswith(("Bash(git", "Bash(gh pr review", "Bash(gh pr merge"))]
    assert {"Edit", "Write", "Bash(git:*)", "Bash(gh pr review:*)", "Bash(gh pr merge:*)"} <= set(disallowed)
    assert wf["permissions"]["contents"] == "read" and wf["jobs"]["review"]["if"].count("draft == false") == 1
    assert "ANTHROPIC_API_KEY" in step["with"]["anthropic_api_key"] and "sk-ant" not in str(wf)
    assert "## AI review (Claude)" in step["with"]["prompt"] and "Review guidelines" in step["with"]["prompt"]


def test_claude_md_has_review_guidelines():
    text = (Path(__file__).parent.parent / "CLAUDE.md").read_text()
    section = text.split("## Review guidelines")[1]
    for needle in ("validated", "real API calls", "Chunk IDs stay stable", "fixture or a test", ".env", "Precision"):
        assert needle in section, needle


def test_ai_reviewer_checkout_does_not_persist_credentials():
    wf = load(next(p for p in WORKFLOWS if p.name == "ai-review.yml"))
    checkout = next(s for s in wf["jobs"]["review"]["steps"] if s.get("uses", "").startswith("actions/checkout"))
    assert checkout["with"]["persist-credentials"] is False


def test_ai_reviewer_prompt_uses_expressions_not_env():
    wf = load(next(p for p in WORKFLOWS if p.name == "ai-review.yml"))
    step = next(s for s in wf["jobs"]["review"]["steps"] if "claude-code-action" in s.get("uses", ""))
    assert "env" not in step
    prompt = step["with"]["prompt"]
    assert "${{ github.event.pull_request.number }}" in prompt and "${{ github.repository }}" in prompt
    assert "$PR_NUMBER" not in prompt and "$REPO" not in prompt
