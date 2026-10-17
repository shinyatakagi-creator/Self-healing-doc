import ast
from pathlib import Path

HTTP_METHODS = {"get", "post", "put", "delete", "patch", "head", "options"}


def _route(decorator: ast.expr) -> dict | None:
    # matches @app.post("/x") / @router.get("/x", ...)
    if not (isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute)):
        return None
    method = decorator.func.attr
    if method not in HTTP_METHODS or not decorator.args:
        return None
    path = decorator.args[0]
    if not (isinstance(path, ast.Constant) and isinstance(path.value, str)):
        return None
    return {"method": method.upper(), "path": path.value}


def _params(args: ast.arguments) -> list[dict]:
    positional = args.posonlyargs + args.args
    defaults = [None] * (len(positional) - len(args.defaults)) + list(args.defaults)
    pairs = list(zip(positional, defaults)) + list(zip(args.kwonlyargs, args.kw_defaults))
    params = [
        {
            "name": a.arg,
            "annotation": ast.unparse(a.annotation) if a.annotation else None,
            "default": ast.unparse(d) if d is not None else None,
        }
        for a, d in pairs
        if a.arg not in ("self", "cls")
    ]
    for star in (args.vararg, args.kwarg):
        if star:
            params.append({"name": star.arg, "annotation": None, "default": None})
    return params


CONTEXT_CAP = 2000


def _short(text: str, n: int = 160) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 3] + "..."


def _signature(node: ast.AST, name: str) -> str:
    if isinstance(node, ast.ClassDef):
        bases = ", ".join(ast.unparse(b) for b in node.bases)
        return f"class {name}({bases})" if bases else f"class {name}"
    kind = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    ret = f" -> {ast.unparse(node.returns)}" if node.returns else ""
    return _short(f"{kind} {name}({ast.unparse(node.args)}){ret}")


def module_context(tree: ast.Module, exclude: str = "") -> str:
    """Bounded view of the rest of a file: module-level assignments with values, class attributes and
    dataclass fields, then signatures (no bodies) of other functions and classes. Capped at CONTEXT_CAP chars."""
    assigns, fields, sigs = [], [], []

    def walk(node: ast.AST, prefix: str, module_level: bool) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.Assign, ast.AnnAssign)) and module_level:
                assigns.append(_short(ast.unparse(child)))
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                name = prefix + child.name
                if name != exclude:
                    sigs.append(_signature(child, name))
                if isinstance(child, ast.ClassDef):
                    for stmt in child.body:
                        if isinstance(stmt, (ast.Assign, ast.AnnAssign)):
                            fields.append(f"{name}: {_short(ast.unparse(stmt))}")
                walk(child, name + ".", False)

    walk(tree, "", True)
    lines, size = [], 0
    for line in assigns + fields + sigs:
        if size + len(line) + 1 > CONTEXT_CAP:
            break
        lines.append(line)
        size += len(line) + 1
    return "\n".join(lines)


def chunk_code(filepath: str | Path, root: str | Path | None = None) -> list[dict]:
    """One chunk per function. ID is `<path relative to root>::<name>`;
    nested functions and methods use dotted names (`outer.inner`)."""
    path = Path(filepath)
    rel = path.relative_to(root).as_posix() if root else path.as_posix()
    return chunk_code_text(path.read_text(), rel)


def chunk_code_text(text: str, rel: str) -> list[dict]:
    tree = ast.parse(text)
    chunks: list[dict] = []

    def visit(node: ast.AST, prefix: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = prefix + child.name
                routes = [r for d in child.decorator_list if (r := _route(d))]
                chunks.append({
                    "id": f"{rel}::{name}",
                    "name": name,
                    "file": rel,
                    "is_async": isinstance(child, ast.AsyncFunctionDef),
                    "decorators": [ast.unparse(d) for d in child.decorator_list],
                    "routes": routes,
                    "params": _params(child.args),
                    "signature": ast.unparse(child.args),
                    "docstring": ast.get_docstring(child) or "",
                    "source": ast.unparse(child),
                    "context": module_context(tree, name),
                })
                visit(child, name + ".")
            elif isinstance(child, ast.ClassDef):
                visit(child, prefix + child.name + ".")
            else:
                visit(child, prefix)

    visit(tree, "")
    return chunks


def chunk_code_dir(root: str | Path) -> list[dict]:
    root = Path(root)
    return [c for f in sorted(root.rglob("*.py")) for c in chunk_code(f, root.parent)]


def code_identifiers(filepath: str | Path) -> set[str]:
    """Every name the code defines or uses as a keyword: functions, classes, params, assigned names
    (module variables, class attributes, dataclass fields), `self.x` attributes, keyword-argument names, imports."""
    names: set[str] = set()
    for node in ast.walk(ast.parse(Path(filepath).read_text())):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            names.add(node.id)
        elif isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Store):
            names.add(node.attr)
        elif isinstance(node, ast.keyword) and node.arg:
            names.add(node.arg)
        elif isinstance(node, ast.alias):
            names.add((node.asname or node.name).split(".")[-1])
    return names


def code_identifiers_dir(root: str | Path) -> set[str]:
    return set().union(*(code_identifiers(f) for f in Path(root).rglob("*.py")))
