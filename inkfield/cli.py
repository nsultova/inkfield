"""The `inkfield` command: start the studio, render one SVG to a file, or list the pieces.

    inkfield [serve] [--port 8000] [--no-browser]
    inkfield render <slug> [--seed N] [--format A3] … [--set name=value]… -o FILE
    inkfield list
"""
import argparse
import sys
from pathlib import Path

from inkfield.core.controls import Choice
from inkfield.core.piece import discover
from inkfield.page.formats import PAGE_PARAMS
from inkfield.render import render

PAGE_CHOICES = {control.name: control.options for control in PAGE_PARAMS if isinstance(control, Choice)}


def _name_value(text: str) -> tuple[str, str]:
    name, sep, value = text.partition("=")
    if not sep or not name:
        raise argparse.ArgumentTypeError(f"expected name=value, got {text!r}")
    return name, value


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="inkfield", description="A local studio for pen-plotter art.")
    commands = parser.add_subparsers(dest="command")

    serve = commands.add_parser("serve", help="start the studio in the browser (the default)")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--no-browser", action="store_true")

    draw = commands.add_parser("render", help="render one piece to an SVG file")
    draw.add_argument("slug")
    draw.add_argument("--seed", default=0)
    for name in ("composition", "format", "orientation", "pen"):
        draw.add_argument(f"--{name}", choices=PAGE_CHOICES[name])
    draw.add_argument("--margin", type=float, help="mm")
    draw.add_argument("--wobble", type=float, help="0 … 1")
    draw.add_argument("--no-border", action="store_true")
    draw.add_argument("--set", type=_name_value, action="append", default=[], metavar="NAME=VALUE",
                      help="a piece setting; repeat for several")
    draw.add_argument("-o", "--output", required=True, metavar="FILE")

    commands.add_parser("list", help="list the available pieces")
    return parser


def _render(args) -> int:
    pieces = discover()
    if args.slug not in pieces:
        print(f"unknown piece {args.slug!r}; available: {', '.join(pieces)}", file=sys.stderr)
        return 2
    page = {name: getattr(args, name) for name in ("composition", "format", "orientation", "pen", "margin")
            if getattr(args, name) is not None}
    finish = {"border": not args.no_border}
    if args.wobble is not None:
        finish["wobble"] = args.wobble
    result = render(pieces, args.slug, args.seed, dict(args.set), finish, page)
    Path(args.output).write_text(result.svg, encoding="utf-8")
    s = result.stats
    print(f"{args.output}: {s['strokes']} strokes, {s['drawn_m']:.1f} m drawn, "
          f"{s['travel_m']:.1f} m pen-up travel, about {s['minutes']:.0f} min to plot")
    return 0


def main(argv=None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "render":
        return _render(args)
    if args.command == "list":
        for slug, piece in discover().items():
            print(f"{slug}\t{piece.meta.title}")
        return 0
    raise SystemExit("server not built yet")   # `serve`, also the default; built in Task 8
