"""The local studio server: the pieces and their controls, rendering, and kept candidates.

Request bodies come from a browser whose stored settings may be stale, so the body is taken as a
plain dict: missing, extra or wrongly typed keys go to `render`, which makes them valid. Every
error reaches the browser as {"error": "..."}. Endpoints are plain `def` so that rendering (up
to a few seconds of CPU) runs in FastAPI's thread pool and the server keeps answering meanwhile.
"""
import logging
from dataclasses import asdict
from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException

from inkfield.core.controls import describe
from inkfield.core.piece import discover
from inkfield.finish import FINISH_INFO, FINISH_PARAMS
from inkfield.page.formats import PAGE_PARAMS
from inkfield.render import RenderResult, render
from inkfield.server.candidates import CandidateStore

WEB = Path(__file__).resolve().parent.parent / "web"
log = logging.getLogger("inkfield.server")


class Refused(Exception):
    """An error answered as {"error": message} with the given HTTP status."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def create_app(candidates_dir: Path = Path("candidates"), pieces: dict | None = None) -> FastAPI:
    pieces = discover() if pieces is None else pieces
    store = CandidateStore(candidates_dir)
    app = FastAPI(title="inkfield", docs_url=None, redoc_url=None, openapi_url=None)

    catalogue = {
        "pieces": [{"slug": slug, "title": piece.meta.title, "subtitle": piece.meta.subtitle,
                    "info": piece.meta.info, "params": describe(piece.params)}
                   for slug, piece in pieces.items()],
        "finish": {"info": FINISH_INFO, "params": describe(FINISH_PARAMS)},
        "page": {"params": describe(PAGE_PARAMS)},
    }

    @app.exception_handler(Refused)
    def refused(request: Request, error: Refused):
        return JSONResponse({"error": error.message}, status_code=error.status)

    @app.exception_handler(RequestValidationError)
    def unreadable_body(request: Request, error: RequestValidationError):
        return JSONResponse({"error": "the request body is not valid JSON"}, status_code=400)

    @app.exception_handler(HTTPException)
    def http_error(request: Request, error: HTTPException):
        return JSONResponse({"error": str(error.detail)}, status_code=error.status_code,
                            headers=getattr(error, "headers", None))

    def draw(body) -> RenderResult:
        if not isinstance(body, dict):
            raise Refused(400, "the request body must be a JSON object")
        slug = body.get("piece")
        if not isinstance(slug, str) or slug not in pieces:
            raise Refused(404, f"unknown piece: {slug!r}")
        try:
            return render(pieces, slug, body.get("seed", 0), body.get("params"),
                          body.get("finish"), body.get("page"))
        except Exception as error:
            log.exception("rendering %r failed", slug)   # full traceback on the server console
            raise Refused(422, f"{type(error).__name__}: {error}") from None

    def candidate_url(slug: str, cid: str) -> str:
        return f"/api/candidates/{slug}/{cid}.svg"

    @app.get("/api/pieces")
    def list_pieces():
        return catalogue

    @app.post("/api/render")
    def render_one(body: Any = Body(None)):
        result = draw(body)
        return {"svg": result.svg, "stats": result.stats, "settings": result.settings,
                "page": asdict(result.page)}

    @app.get("/api/candidates/{slug}")
    def list_candidates(slug: str):
        return [{**item, "url": candidate_url(slug, item["id"])} for item in store.list(slug)]

    @app.post("/api/candidates")
    def keep_candidate(body: Any = Body(None)):
        result = draw(body)
        slug, seed = result.settings["piece"], result.settings["seed"]
        try:
            cid = store.save(slug, seed, result.svg)
        except KeyError:
            raise Refused(422, f"cannot keep candidates for a piece named {slug!r}") from None
        return {"id": cid, "seed": seed, "settings": result.settings, "url": candidate_url(slug, cid)}

    @app.get("/api/candidates/{slug}/{cid}.svg")
    def candidate_file(slug: str, cid: str):
        try:
            return FileResponse(store.path(slug, cid), media_type="image/svg+xml")
        except KeyError:
            raise Refused(404, "no such candidate") from None

    @app.delete("/api/candidates/{slug}/{cid}", status_code=204)
    def remove_candidate(slug: str, cid: str):
        try:
            store.remove(slug, cid)
        except KeyError:
            raise Refused(404, "no such candidate") from None
        return Response(status_code=204)

    # Any other /api path is a 404 for every method; without this it would fall through to the
    # static files below and answer 405. Paths with "../" arrive decoded and end up here too.
    @app.api_route("/api/{rest:path}", methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE"])
    def no_such_endpoint(rest: str):
        raise Refused(404, f"no such endpoint: /api/{rest}")

    app.mount("/", StaticFiles(directory=WEB, html=True), name="web")
    return app
