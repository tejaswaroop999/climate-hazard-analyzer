import asyncio
import logging
import time
from pathlib import Path
from collections import OrderedDict, deque
from contextlib import asynccontextmanager
import httpx
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pymongo.errors import PyMongoError
from app.core.config import get_settings
from app.repositories.cache import MongoCache
from app.schemas import AnalysisRequest
from app.services.analysis import AnalysisService
from app.services.climate import DataQualityError
from app.services.weather import WeatherProvider, WeatherError

logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app):
    cache = MongoCache(
        settings.mongo_uri, settings.mongo_database, settings.cache_ttl_days
    )
    client = httpx.AsyncClient(
        timeout=httpx.Timeout(30, connect=5),
        follow_redirects=False,
        limits=httpx.Limits(max_connections=8, max_keepalive_connections=4),
    )
    try:
        await cache.initialize()
        app.state.cache = cache
        app.state.weather = WeatherProvider(client)
        app.state.analysis = AnalysisService(cache, app.state.weather)
        yield
    finally:
        await client.aclose()
        await cache.close()


app = FastAPI(title="Climate Hazard Trend Analyzer", version="1.0.0", lifespan=lifespan)
# Process-local guard: deploy one worker, or use a shared gateway limiter for scaling.
clients = OrderedDict()
MAX_CLIENTS = 10000


@app.middleware("http")
async def protections(request: Request, call_next):
    if request.url.path.startswith("/api/v1/") and request.url.path not in (
        "/api/v1/health",
        "/api/v1/ready",
    ):
        identity = request.client.host if request.client else "unknown"
        now = time.monotonic()
        bucket = clients.setdefault(identity, deque())
        clients.move_to_end(identity)
        while bucket and bucket[0] <= now - 60:
            bucket.popleft()
        if len(bucket) >= settings.rate_limit_per_minute:
            return JSONResponse(
                {"detail": "Too many requests. Try again shortly."},
                status_code=429,
                headers={"Retry-After": "60"},
            )
        bucket.append(now)
        while len(clients) > MAX_CLIENTS:
            clients.popitem(last=False)
    # Validate both advertised and actual size, including streamed/chunked bodies.
    if request.method == "POST":
        length = request.headers.get("content-length")
        if length and (not length.isdigit() or int(length) > 4096):
            return JSONResponse(
                {"detail": "Request body exceeds 4 KiB"}, status_code=413
            )
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 4096:
                return JSONResponse(
                    {"detail": "Request body exceeds 4 KiB"}, status_code=413
                )
        request._body = bytes(body)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


# Outer middleware also adds CORS headers to validation and rate-limit errors.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[s.strip() for s in settings.cors_origins.split(",") if s.strip()],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.exception_handler(WeatherError)
async def weather_error(request, exc):
    return JSONResponse({"detail": str(exc)}, status_code=502)


@app.exception_handler(DataQualityError)
async def quality_error(request, exc):
    return JSONResponse({"detail": str(exc)}, status_code=422)


@app.exception_handler(PyMongoError)
async def database_error(request, exc):
    logger.exception("MongoDB operation failed")
    return JSONResponse(
        {"detail": "Analysis storage is temporarily unavailable"}, status_code=503
    )


@app.exception_handler(Exception)
async def unexpected_error(request, exc):
    logger.exception("Unhandled request failure")
    return JSONResponse(
        {"detail": "An unexpected server error occurred"}, status_code=500
    )


@app.get("/api/v1/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


@app.get("/api/v1/ready")
async def ready(request: Request):
    await request.app.state.cache.ping()
    return {"status": "ready", "database": "connected"}


@app.get("/api/v1/regions/search")
async def regions(
    request: Request,
    q: str = Query(min_length=2, max_length=100, pattern=r"^[^<>\x00-\x1f]+$"),
):
    query = q.strip()
    if len(query) < 2:
        raise HTTPException(422, "Enter at least two non-space characters")
    return {"results": await request.app.state.weather.search(query)}


@app.post("/api/v1/analyze")
async def analysis(request: Request, body: AnalysisRequest):
    try:
        # Bound total work, including the capacity queue and retry budget.
        return await asyncio.wait_for(
            request.app.state.analysis.execute(body), timeout=240
        )
    except TimeoutError:
        raise HTTPException(
            504, "Analysis timed out. Retry later; completed weather blocks are cached."
        ) from None


# The root Dockerfile bundles the React build for a single-service deployment.
static_directory = Path(__file__).resolve().parent / "static"
if static_directory.is_dir():
    app.mount(
        "/assets", StaticFiles(directory=static_directory / "assets"), name="assets"
    )

    @app.get("/", include_in_schema=False)
    async def dashboard():
        return FileResponse(
            static_directory / "index.html",
            headers={
                "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
                "X-Frame-Options": "DENY",
            },
        )
