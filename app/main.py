from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import (
    FileResponse,
    JSONResponse,
)
from fastapi.staticfiles import StaticFiles

from app.api.routes import router


app = FastAPI(
    title="Invoice Intelligence Agent",
    version="1.0.0",
)

app.include_router(router)


static_directory = Path("app/static")
assets_directory = static_directory / "assets"


if assets_directory.exists():
    app.mount(
        "/assets",
        StaticFiles(
            directory=assets_directory
        ),
        name="assets",
    )


@app.get(
    "/{full_path:path}",
    include_in_schema=False,
)
def serve_spa(full_path: str):
    del full_path

    index_file = (
        static_directory / "index.html"
    )

    if index_file.exists():
        return FileResponse(index_file)

    return JSONResponse(
        {
            "detail": (
                "Frontend not built yet"
            )
        },
        status_code=404,
    )