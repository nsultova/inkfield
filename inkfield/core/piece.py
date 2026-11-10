"""A piece is one Python file in `inkfield/pieces/` with three module-level names:

    META      a Meta: slug, title, subtitle, the shape it prefers when framed, and info text
    PARAMS    a list of controls (see `inkfield.core.controls`)
    generate  generate(params, frame, rng) -> list[Stroke]

`discover` imports every such file in a package, so dropping a new file in makes it appear.
Files whose name starts with "_" are skipped.
"""
import importlib
import pkgutil
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class Meta:
    slug: str
    title: str
    subtitle: str
    framed_shape: str
    info: str


@dataclass(frozen=True)
class Piece:
    meta: Meta
    params: list
    generate: Callable   # generate(params: dict, frame: Frame, rng) -> list[Stroke]


def discover(package: str = "inkfield.pieces") -> dict[str, Piece]:
    """Every piece in `package`, keyed by slug, in module-name order."""
    found = {}
    for module_info in pkgutil.iter_modules(importlib.import_module(package).__path__):
        if module_info.name.startswith("_"):
            continue
        module = importlib.import_module(f"{package}.{module_info.name}")
        piece = Piece(meta=module.META, params=list(module.PARAMS), generate=module.generate)
        if piece.meta.slug in found:
            raise ValueError(f"two pieces share the slug {piece.meta.slug!r}")
        found[piece.meta.slug] = piece
    return found
