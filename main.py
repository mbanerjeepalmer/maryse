from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from contextlib import asynccontextmanager
from playwright.async_api import async_playwright
import asyncio

# Global Playwright context manager
_pw = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _pw
    # Startup: Initialize Playwright
    _pw = await async_playwright().start()
    yield
    # Shutdown: Close Playwright
    await _pw.stop()

app = FastAPI(lifespan=lifespan)

@app.get("/screenshot")
async def take_screenshot(
    url: str = Query(..., description="URL of the page to take screenshot of"),
    full_page: bool = Query(False, description="Whether to take full scrollable page screenshot"),
    timeout: int = Query(30000, ge=1000, le=60000, description="Page load timeout in milliseconds"),
    viewport_width: int = Query(1920, ge=100, le=4096, description="Viewport width"),
    viewport_height: int = Query(1080, ge=100, le=4096, description="Viewport height"),
    format: str = Query("png", regex="^(png|jpeg)$", description="Image format (png or jpeg)"),
    quality: int = Query(80, ge=10, le=100, description="Image quality for jpeg (ignored for png)")
):
    """
    Takes a screenshot of the given URL and returns the image.
    """

    if not url.startswith(("http", "https")):
        raise HTTPException(status_code=400, detail="Invalid URL scheme")

    try:
        # Launch browser
        browser = await _pw.chromium.launch(headless=True)
        page = await browser.new_page()

        # Set viewport size
        await page.set_viewport_size({"width": viewport_width, "height": viewport_height})

        # Navigate to URL
        await page.goto(url, timeout=timeout, wait_until="networkidle")

        # Take screenshot
        img_bytes = await page.screenshot(full_page=full_page, type=format, quality=quality)

        # Close browser
        await browser.close()

        # Return image
        media_type = f"image/{format}"
        return Response(content=img_bytes, media_type=media_type)

    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Timeout while loading the page")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Screenshot failed: {str(e)}")

@app.get("/")
async def health_check():
    return {"status": "healthy"}
