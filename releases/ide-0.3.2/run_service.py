"""Serve the installed IDE's persistent CPU experience library on loopback."""
import argparse
from contextlib import asynccontextmanager
import html
import os
from pathlib import Path
import sys

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware
import uvicorn

from src.workbench.presentation import create_presentation_router
from src.workbench.router import create_workbench_router
from src.workbench.service import WorkbenchService
VERSION = "0.3.2"


def make_app(data_dir):
    model_dir = Path(__file__).resolve().parent / "models/multilingual-e5-small"
    local = WorkbenchService(data_dir, semantic_model_dir=model_dir if model_dir.is_dir() else None)
    workbench = create_workbench_router(data_dir, service=local)
    service = workbench.workbench_service

    @asynccontextmanager
    async def lifespan(app):
        yield
        service.close()

    app = FastAPI(title="SEED-A IDE 本机经验库", version=VERSION, lifespan=lifespan,
                  docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])
    app.state.workbench = service
    # Reuse production methods and their validators. The offline distribution
    # exposes IDE operations only, including its real persisted pytest receipts.
    for router in (workbench, create_presentation_router(data_dir)):
        for route in router.routes:
            prefix = route.path.removeprefix("/api/workbench/").split("/")[0]
            if prefix in {"overview", "experiences", "search", "graph", "maintenance",
                          "templates", "drafts", "ide-receipts", "ide-capabilities", "ide-verified-experiences", "ide-ranked-experiences"}:
                app.router.routes.append(route)

    @app.middleware("http")
    async def local_origin(request: Request, call_next):
        origin = request.headers.get("origin")
        if origin and origin != f"http://{request.headers.get('host')}":
            return JSONResponse({"detail": "仅允许本机工作台同源操作"}, status_code=403)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.get("/api/health")
    def health():
        return {"service": "seeda-ide", "version": VERSION, "status": "ok",
                "cpu": True, "python": sys.version.split()[0], "pid": os.getpid()}

    @app.get("/", response_class=HTMLResponse)
    def home():
        rows = service.experiences()
        items = "".join(
            "<li><strong>" + html.escape(str(row.get("title") or row.get("requirement") or "经验"))
            + "</strong> · " + html.escape(str(row.get("version") or ""))
            + " · " + ("已归档" if row.get("archived") else "活跃") + "</li>" for row in rows
        )
        layout = Path(__file__).with_name("library.html").read_text("utf-8")
        return layout.replace("{{experience_count}}", str(len(rows))).replace("{{experience_rows}}",
            f"<ol>{items}</ol>" if items else "<p>当前经验库为空。</p>")

    return app


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    default_data = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "SEED-A" / "IDE"
    parser.add_argument("--data-dir", type=Path,
                        default=Path(os.environ.get("SEEDA_IDE_DATA", default_data)))
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("端口应在 1024 至 65535 之间。")
    uvicorn.run(make_app(args.data_dir.resolve()), host="127.0.0.1", port=args.port)
