import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager

# Initialize httpx.AsyncClient as a global reusable client
client = httpx.AsyncClient(
    follow_redirects=True,
    timeout=httpx.Timeout(10.0)
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown: Ensure the httpx client is closed gracefully
    await client.aclose()

# Initialize FastAPI app with the lifespan manager
app = FastAPI(lifespan=lifespan)

@app.get("/fetch-html", response_class=HTMLResponse)
async def fetch_html(url: str = Query(..., description="The URL to fetch")):
    """
    Fetches the HTML content of a given URL.
    """
    if not url.startswith(('http://', 'https://')):
        raise HTTPException(
            status_code=400,
            detail="Invalid URL scheme. URL must start with http:// or https://."
        )

    try:
        # Use the global async client to make the request
        response = await client.get(url)

        # Raise an exception for 4xx/5xx responses from the target URL
        response.raise_for_status()

        # Return the content
        return HTMLResponse(
            content=response.text,
            status_code=response.status_code
        )

    except httpx.HTTPStatusError as e:
        # Handle errors returned by the target server (e.g., 404, 500)
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Error from target server: {e.request.url}"
        )
    except httpx.RequestError as e:
        # Handle network errors (e.g., DNS errors, connection timeouts)
        raise HTTPException(
            status_code=504, # Gateway Timeout
            detail=f"Error connecting to target URL: {e.request.url}"
        )
    except Exception as e:
        # Catch any other unexpected errors
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred: {str(e)}"
        )

@app.get("/")
async def health_check():
    return {"status": "healthy"}