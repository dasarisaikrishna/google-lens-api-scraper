import asyncio
import os
import time
import logging
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from contextlib import asynccontextmanager

from scraper import get_exact_match_html, validate_exact_match_html

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

MAX_CONCURRENCY = int(os.getenv("MAX_CONCURRENCY", "5"))  # 5 for 16GB RAM

# Stats tracking
_stats = {
    "total": 0,
    "success": 0,
    "failed": 0,
    "total_time": 0.0,
}

@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info(f"Starting API — max concurrency: {MAX_CONCURRENCY}")
    yield
    log.info("Shutting down API")

app = FastAPI(
    title="Google Lens Exact Match API",
    version="3.0.0",
    lifespan=lifespan,
)

_semaphore = asyncio.Semaphore(MAX_CONCURRENCY)


@app.get("/health")
def health():
    avg_time = (
        _stats["total_time"] / _stats["success"]
        if _stats["success"] > 0 else 0
    )
    return {
        "status": "ok",
        "max_concurrency": MAX_CONCURRENCY,
        "stats": {
            "total_requests": _stats["total"],
            "successful": _stats["success"],
            "failed": _stats["failed"],
            "avg_response_time_seconds": round(avg_time, 2),
            "success_rate": f"{(_stats['success'] / _stats['total'] * 100) if _stats['total'] > 0 else 0:.1f}%",
        }
    }


@app.get("/google-lens/browser", response_class=HTMLResponse)
async def google_lens_browser(
    imageUrl: str = Query(..., description="Publicly accessible image URL"),
):
    if not imageUrl.strip():
        raise HTTPException(status_code=400, detail="imageUrl must not be empty")

    _stats["total"] += 1
    start = time.time()
    log.info(f"Request #{_stats['total']} — {imageUrl[:80]}")

    async with _semaphore:
        try:
            html = await get_exact_match_html(imageUrl)

            # Validate before returning
            is_valid, reason = validate_exact_match_html(html)
            if not is_valid:
                _stats["failed"] += 1
                log.warning(f"Invalid HTML — {reason} — {imageUrl[:80]}")
                raise HTTPException(status_code=502, detail=f"Invalid response: {reason}")

            elapsed = time.time() - start
            _stats["success"] += 1
            _stats["total_time"] += elapsed
            log.info(f"Success #{_stats['success']} in {elapsed:.1f}s — {reason}")
            return HTMLResponse(content=html, status_code=200)

        except HTTPException:
            raise
        except RuntimeError as exc:
            _stats["failed"] += 1
            elapsed = time.time() - start
            log.error(f"RuntimeError in {elapsed:.1f}s — {exc}")
            raise HTTPException(status_code=502, detail=str(exc))
        except Exception as exc:
            _stats["failed"] += 1
            elapsed = time.time() - start
            log.error(f"Unexpected error in {elapsed:.1f}s — {exc}")
            raise HTTPException(status_code=500, detail=f"Unexpected error: {exc}")


@app.get("/stats")
def stats():
    """Detailed stats endpoint for monitoring"""
    avg_time = (
        _stats["total_time"] / _stats["success"]
        if _stats["success"] > 0 else 0
    )
    return JSONResponse({
        "total_requests": _stats["total"],
        "successful": _stats["success"],
        "failed": _stats["failed"],
        "avg_response_time_seconds": round(avg_time, 2),
        "success_rate": f"{(_stats['success'] / _stats['total'] * 100) if _stats['total'] > 0 else 0:.1f}%",
        "max_concurrency": MAX_CONCURRENCY,
    })