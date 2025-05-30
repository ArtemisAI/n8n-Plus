import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import pathlib
from dotenv import load_dotenv
import uvicorn
import logging # Added for logging

# Configure basic logging for the application
# Load environment variables first to get LOG_LEVEL
BASE_DIR_MAIN = pathlib.Path(__file__).resolve().parent
dotenv_path_main = BASE_DIR_MAIN / '.env'

if dotenv_path_main.exists():
    load_dotenv(dotenv_path_main)
    # print(f"Loaded .env from {dotenv_path_main}") # For debugging
else:
    # Also check one level up if main.py is in 'app' subdirectory
    dotenv_path_alt = BASE_DIR_MAIN.parent / '.env'
    if dotenv_path_alt.exists():
        load_dotenv(dotenv_path_alt)
        # print(f"Loaded .env from {dotenv_path_alt}") # For debugging
    # else:
        # print(f".env file not found at {dotenv_path_main} or {dotenv_path_alt}") # For debugging


LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=LOG_LEVEL, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__) # Logger for this module

from app.api.endpoints import router as api_router
from app.db.database import create_db_and_tables

logger.info("Application starting up...")

# Create database and tables on startup
try:
    logger.info("Initializing database and tables...")
    create_db_and_tables()
except Exception as e:
    logger.error(f"Database initialization failed: {e}", exc_info=True)
    # Depending on the app's requirements, you might want to exit if DB init fails
    # For now, just log the error and continue, FastAPI might still start but DB operations will fail.


app = FastAPI(title="n8n Template Manager API")

# Mount static files
static_dir = BASE_DIR_MAIN / "app/static"
if not static_dir.exists():
    logger.warning(f"Static files directory not found at {static_dir}. Frontend might not load.")
app.mount("/static", StaticFiles(directory=static_dir), name="static")


# Include API router
app.include_router(api_router, prefix="/api/v1")

@app.get("/", response_class=HTMLResponse)
async def read_root():
    index_html_path = static_dir / "index.html"
    if not index_html_path.exists():
        logger.error(f"index.html not found at {index_html_path}")
        return HTMLResponse(content="<h1>Frontend not found. Ensure index.html is in app/static.</h1>", status_code=404)
    try:
        with open(index_html_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content)
    except Exception as e:
        logger.error(f"Error reading index.html: {e}", exc_info=True)
        return HTMLResponse(content=f"<h1>An error occurred: {e}</h1>", status_code=500)

if __name__ == "__main__":
    app_host = os.getenv("APP_HOST", "0.0.0.0")
    app_port = int(os.getenv("APP_PORT", "8000"))
    logger.info(f"Starting Uvicorn server on {app_host}:{app_port} with LOG_LEVEL={LOG_LEVEL}")
    uvicorn.run("main:app", host=app_host, port=app_port, reload=True, log_level=LOG_LEVEL.lower())
