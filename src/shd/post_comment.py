import argparse
import os
from pathlib import Path

from github import Github

from shd.report import MARKER


def upsert_comment(issue, body: str) -> str:
    """Update the comment carrying our hidden marker, or create it."""
    for comment in issue.get_comments():
        if MARKER in comment.body:
            comment.edit(body)
            return "updated"
    issue.create_comment(body)
    return "created"


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="shd.post_comment")
    ap.add_argument("--file", required=True, type=Path)
    ap.add_argument("--pr", required=True, type=int)
    ap.add_argument("--repo", default=os.getenv("GITHUB_REPOSITORY"))
    args = ap.parse_args(argv)
    issue = Github(os.environ["GITHUB_TOKEN"]).get_repo(args.repo).get_issue(args.pr)
    print(upsert_comment(issue, args.file.read_text()))


if __name__ == "__main__":
    main()
