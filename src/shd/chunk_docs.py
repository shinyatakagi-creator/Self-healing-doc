import re
from pathlib import Path

HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*#*\s*$")
BACKTICK = re.compile(r"`([^`\n]+)`")
ROUTE = re.compile(r"(?:GET|POST|PUT|DELETE|PATCH)\s+(/\S*)")
SKIPPED_FENCE = re.compile(r"^```(?:bash|sh|shell|console|yaml|ini|toml|json)\b.*?^```", re.M | re.S)
IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(\(.*\))?")


def extract_refs(text: str) -> dict:
    """Pull code-looking references out of backtick spans. Shell/config fenced blocks are ignored.
    `routes` are the paths written with an HTTP method in front; `calls` are names written as `name(...)`."""
    text = SKIPPED_FENCE.sub("", text)
    paths, routes, names, calls, config_keys = set(), set(), set(), set(), set()
    for span in BACKTICK.findall(text):
        span = span.strip()
        if m := ROUTE.search(span):
            paths.add(m.group(1))
            routes.add(m.group(1))
        elif span.startswith("/") or ("/" in span and "." in span):
            paths.add(span)
        elif re.fullmatch(r"[A-Z][A-Z0-9_]+", span):
            config_keys.add(span)
        elif re.fullmatch(r"[a-z0-9_]+(\.[a-z0-9_]+)+", span) and not span.endswith((".py", ".md")):
            config_keys.add(span)
        elif IDENT.fullmatch(span):
            names.add(span.split("(")[0])
            if "(" in span:
                calls.add(span.split("(")[0])
    return {k: sorted(v) for k, v in
            (("paths", paths), ("routes", routes), ("names", names), ("calls", calls), ("config_keys", config_keys))}


def chunk_docs(filepath: str | Path, root: str | Path | None = None) -> list[dict]:
    """One chunk per heading section; ID is `<path relative to root>::<heading>`.
    Text before the first heading becomes `(preamble)`. Sections with no body are skipped."""
    path = Path(filepath)
    rel = path.relative_to(root).as_posix() if root else path.as_posix()
    sections: list[tuple[str, list[str]]] = [("(preamble)", [])]
    in_fence = False
    for line in path.read_text().splitlines():
        if line.lstrip().startswith(("```", "~~~")):
            in_fence = not in_fence
        m = None if in_fence else HEADING.match(line)
        if m:
            sections.append((m.group(1), [line]))
        else:
            sections[-1][1].append(line)

    chunks = []
    for title, lines in sections:
        body = [l for l in lines if not HEADING.match(l)]
        if not "".join(body).strip():
            continue
        content = "\n".join(lines).strip()
        chunks.append({
            "id": f"{rel}::{title}",
            "title": title,
            "file": rel,
            "content": content,
            "refs": extract_refs(content),
        })
    return chunks


def chunk_docs_dir(root: str | Path) -> list[dict]:
    root = Path(root)
    return [c for f in sorted(root.rglob("*.md")) for c in chunk_docs(f, root.parent)]
