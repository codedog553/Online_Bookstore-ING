from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .api import router
from .config import settings
from .container import build_container
from .db import build_sessionmaker


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, version="0.1.0", description="DeepSeek powered bookstore agent microservice")

    if settings.enforce_https:
        app.add_middleware(HTTPSRedirectMiddleware)

    if settings.trusted_hosts:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.container = build_container(settings, build_sessionmaker(settings.read_db_url), build_sessionmaker(settings.write_db_url))
    app.include_router(router)

    @app.middleware("http")
    async def secure_headers(request: Request, call_next):
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            content_type = request.headers.get("content-type", "")
            if "application/json" not in content_type:
                return JSONResponse(status_code=415, content={"detail": "仅支持 application/json"})
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = "default-src 'self'; connect-src 'self' http://localhost:5173 http://127.0.0.1:5173; img-src 'self' data:; style-src 'self' 'unsafe-inline';"
        return response

    return app


app = create_app()
