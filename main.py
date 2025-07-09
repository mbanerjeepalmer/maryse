import asyncio
from fastapi import FastAPI, Query, UploadFile, File, HTTPException, Response
from playwright.async_api import async_playwright
import openpyxl
from openpyxl.utils.cell import coordinate_from_string  # Correct import for coordinate_from_string
from openpyxl.utils.exceptions import InvalidFileException  # Correct import for InvalidFileException
from openpyxl.drawing.image import Image as XLImage
from PIL import Image as PILImage
from io import BytesIO

app = FastAPI()

# Shared helper function for screenshot logic
async def get_screenshot_bytes(
    url: str,
    full_page: bool = False,
    timeout: int = 30000,
    viewport_width: int = 1920,
    viewport_height: int = 1080,
    format: str = "png",
    quality: int = 80
) -> bytes:
    if not url.startswith(("http", "https")):
        raise ValueError("Invalid URL scheme")
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.set_viewport_size({"width": viewport_width, "height": viewport_height})
            await page.goto(url, timeout=timeout, wait_until="networkidle")
            img_bytes = await page.screenshot(full_page=full_page, type=format, quality=quality)
            await browser.close()
            return img_bytes
    except asyncio.TimeoutError:
        raise TimeoutError("Timeout while loading the page")
    except Exception as e:
        raise RuntimeError(f"Screenshot failed: {str(e)}")

# Refactored existing endpoint to use helper function
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
    try:
        img_bytes = await get_screenshot_bytes(url, full_page, timeout, viewport_width, viewport_height, format, quality)
        media_type = f"image/{format}"
        return Response(content=img_bytes, media_type=media_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except TimeoutError as e:
        raise HTTPException(status_code=504, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

# New endpoint using the helper function
@app.post("/insert-screenshot")
async def insert_screenshot(
    spreadsheet: UploadFile = File(..., description="Excel file (.xlsx) to insert screenshot into"),
    url: str = Query(..., description="URL to take screenshot of"),
    target_cell: str = Query(..., description="Target cell in Excel, e.g., 'A1'"),
    full_page: bool = Query(False, description="Whether to take full scrollable page screenshot"),
    timeout: int = Query(30000, ge=1000, le=60000, description="Page load timeout in milliseconds"),
    viewport_width: int = Query(1920, ge=100, le=4096, description="Viewport width"),
    viewport_height: int = Query(1080, ge=100, le=4096, description="Viewport height"),
    format: str = Query("png", regex="^(png|jpeg)$", description="Image format (png or jpeg)"),
    quality: int = Query(80, ge=10, le=100, description="Image quality for jpeg (ignored for png)")
):
    # Take screenshot using helper function
    try:
        img_bytes = await get_screenshot_bytes(url, full_page, timeout, viewport_width, viewport_height, format, quality)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except TimeoutError as e:
        raise HTTPException(status_code=504, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Handle spreadsheet modification
    try:
        # Read uploaded Excel file
        excel_bytes = await spreadsheet.read()
        excel_io = BytesIO(excel_bytes)
        
        # Load workbook and validate target cell
        try:
            coordinate_from_string(target_cell)  # Validate cell coordinate
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid target cell coordinate")
        
        wb = openpyxl.load_workbook(excel_io, read_only=False)
        ws = wb.active  # Modify the active (first) worksheet
        
        # Create and insert image
        img_io = BytesIO(img_bytes)
        pil_img = PILImage.open(img_io)
        xl_img = XLImage(pil_img)
        ws.add_image(xl_img, target_cell)
        
        # Save modified workbook
        output_io = BytesIO()
        wb.save(output_io)
        output_io.seek(0)
        
        # Return modified spreadsheet as download
        return Response(
            content=output_io.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=modified_spreadsheet.xlsx"}
        )
    
    except InvalidFileException:
        raise HTTPException(status_code=400, detail="Invalid Excel file uploaded")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to modify spreadsheet: {str(e)}")
