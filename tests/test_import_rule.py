"""The math folders stay free of plumbing: no server or web code, no file or network access.

Folders that do not exist yet (finish/, page/ before their tasks land) are simply skipped.
"""
import ast
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent.parent / "inkfield"
MATH_FOLDERS = ("pieces", "core", "finish", "page")

FORBIDDEN_PREFIXES = ("inkfield.server", "inkfield.web")
FORBIDDEN_MODULES = {"os", "pathlib", "io", "socket", "urllib", "requests", "httpx", "fastapi"}
PIECE_ALLOWED = {"numpy", "math", "dataclasses"}
DISCOVERY_FILE = "core/piece.py"
DISCOVERY_ONLY = {"importlib", "pkgutil"}


def math_files():
    for folder in MATH_FOLDERS:
        directory = PACKAGE_ROOT / folder
        if directory.is_dir():
            yield from sorted(directory.rglob("*.py"))


def imports_of(path):
    """Return (module, extra_names) for every import in the file.

    `module` is the absolute module imported from; for `from m import a`, `extra_names`
    holds "m.a" so that `from inkfield import server` is still caught.
    """
    package = list(path.relative_to(PACKAGE_ROOT.parent).parts[:-1])   # e.g. ["inkfield", "core"]
    found = []
    for node in ast.walk(ast.parse(path.read_text(), filename=str(path))):
        if isinstance(node, ast.Import):
            found += [(alias.name, []) for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package[: len(package) - (node.level - 1)]
                module = ".".join(base + ([node.module] if node.module else []))
            else:
                module = node.module
            found.append((module, [f"{module}.{alias.name}" for alias in node.names]))
    return found


def top(name):
    return name.split(".")[0]


def test_math_never_imports_plumbing():
    files = list(math_files())
    assert files, "no files found under the math folders"
    problems = []
    for path in files:
        rel = path.relative_to(PACKAGE_ROOT).as_posix()
        for module, extra in imports_of(path):
            for name in [module, *extra]:
                if name.startswith(FORBIDDEN_PREFIXES) or top(name) in FORBIDDEN_MODULES:
                    problems.append(f"{rel}: {name}")
                if top(name) in DISCOVERY_ONLY and rel != DISCOVERY_FILE:
                    problems.append(f"{rel}: {name} (only {DISCOVERY_FILE} may import it)")
            if rel.startswith("pieces/"):
                if not (top(module) in PIECE_ALLOWED or module == "inkfield.core"
                        or module.startswith("inkfield.core.")):
                    problems.append(f"{rel}: {module} (pieces import only numpy, math, dataclasses, inkfield.core)")
    assert not problems, "\n".join(problems)
