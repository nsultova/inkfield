"""Kept drawings ("candidates"): one SVG file per drawing, in a folder per piece.

    candidates/<slug>/<id>.svg          id = "YYYYmmdd-HHMMSS-seed<seed>", "-2", "-3"… on collision
    candidates/.trash/<slug>/<id>.svg   where `remove` puts them; nothing is ever deleted

Each SVG carries the settings that made it, so the folder is the whole record: no index file.
The folder may hold anything (stray files, sub-folders, SVGs from other tools), so `list` skips
what it cannot read. Slugs and ids arrive from URLs, so every name is checked to be a plain name
before any path is built, and the resulting path must stay inside the store.
"""
import re
import time
from pathlib import Path

from inkfield.page.svg import read_settings

PLAIN_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")
SAVED_ID = re.compile(r"(\d{8}-\d{6})-seed\d+(?:-(\d+))?")   # timestamp, collision number
TRASH = ".trash"


def _plain(name) -> str:
    if not isinstance(name, str) or not PLAIN_NAME.fullmatch(name):
        raise KeyError(name)
    return name


class CandidateStore:
    def __init__(self, root: Path):
        self.root = Path(root)

    def _inside(self, path: Path) -> Path:
        if not path.resolve().is_relative_to(self.root.resolve()):
            raise KeyError(str(path))
        return path

    def save(self, slug: str, seed: int, svg: str) -> str:
        """Write `svg` as a new candidate and return its id."""
        folder = self._inside(self.root / _plain(slug))
        folder.mkdir(parents=True, exist_ok=True)
        base = _plain(f"{time.strftime('%Y%m%d-%H%M%S')}-seed{seed}")
        number = 1
        while True:
            cid = base if number == 1 else f"{base}-{number}"
            number += 1
            if (self.root / TRASH / slug / f"{cid}.svg").exists():
                continue   # an id stays unique even after its file went to the trash
            try:
                # "x" creates the file only if it does not exist, so two saves in the same
                # second (from two browser tabs) can never overwrite each other.
                with open(folder / f"{cid}.svg", "x", encoding="utf-8", newline="") as file:
                    file.write(svg)
                return cid
            except FileExistsError:
                continue

    def list(self, slug: str) -> list[dict]:
        """The readable candidates of `slug`, oldest first: [{"id", "seed", "settings"}]."""
        try:
            folder = self._inside(self.root / _plain(slug))
        except KeyError:
            return []
        if not folder.is_dir():
            return []
        found = []
        for file in folder.iterdir():
            if file.suffix != ".svg":
                continue
            try:
                path = self.path(slug, file.stem)
                settings = read_settings(path.read_text(encoding="utf-8"))
                modified = path.stat().st_mtime_ns
            except (KeyError, ValueError, OSError):
                continue
            found.append((self._age(file.stem, modified), {
                "id": file.stem, "seed": settings.get("seed"), "settings": settings}))
        found.sort(key=lambda pair: pair[0])
        return [item for _, item in found]

    @staticmethod
    def _age(cid: str, modified_ns: int) -> tuple:
        """Sort key: the second in the id, then the file time, then the collision number.

        Plain string order would put "…-seed7-10" before "…-seed7-2". Ids not made by `save`
        take their second from the file time.
        """
        match = SAVED_ID.fullmatch(cid)
        if match:
            second, number = match.group(1), int(match.group(2) or 1)
        else:
            second = time.strftime("%Y%m%d-%H%M%S", time.localtime(modified_ns / 1e9))
            number = 1
        return (second, modified_ns, number, cid)

    def path(self, slug: str, cid: str) -> Path:
        """The file of one candidate; KeyError if it is missing or the names are not plain."""
        path = self._inside(self.root / _plain(slug) / f"{_plain(cid)}.svg")
        if not path.is_file():
            raise KeyError(cid)
        return path

    def remove(self, slug: str, cid: str) -> None:
        """Move one candidate to .trash/<slug>/, keeping any file already there."""
        source = self.path(slug, cid)
        trash = self.root / TRASH / slug
        trash.mkdir(parents=True, exist_ok=True)
        self._inside(trash)   # .trash could be a link to somewhere else
        target, number = trash / f"{cid}.svg", 2
        while target.exists():
            target, number = trash / f"{cid}~{number}.svg", number + 1
        source.rename(target)
