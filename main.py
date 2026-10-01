"""
UPF Optimal Placer (UOP) - v2.0

File: main.py

Description:
Application entry point that initializes the FastAPI instance, configures logging, and manages the Uvicorn server lifecycle.

@authors: R. Rodriguez <raul.rodriguez@hcltech.com>, Y. Aldoori <yaseen.aldoori@windriver.com>, L. Popokh <leo.popokh@asato.ai>
@license: MIT
@copyright: Copyright (c) 2026 R. Rodriguez, Y. Aldoori, L. Popokh
"""

# Standard library imports
import argparse
import sys

# Third-party libraries
import loguru
from fastapi import FastAPI

# Local application imports
from routes import router as api_router

# API Initialization
app = FastAPI(
    title="UPF Optimal Placer",
    description="Modernized API for Network and Edge Server Management",
    version="2.0.0"
)

# Register the split API routes
app.include_router(api_router)

if __name__ == "__main__":
    import uvicorn

    # Configure Argument Parser to match the original uop.py
    parser = argparse.ArgumentParser(description="UPF Optimal Placer v2.0")
    parser.add_argument("--host", default="0.0.0.0", help="Host address")
    parser.add_argument("--port", type=int, default=8000, help="Port number")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    parser.add_argument(
        "--log-level", 
        choices=["debug", "info", "warning", "error", "critical"], 
        default="info", 
        help="Logging level"
    )
    
    args = parser.parse_args()

    # Configure Loguru to match the requested log level
    log_level_upper = args.log_level.upper()
    loguru.logger.remove()  # Remove default handler
    loguru.logger.add(sys.stderr, level=log_level_upper)
    
    loguru.logger.info(f"Starting UPF Optimal Placer on http://{args.host}:{args.port}")
    
    # Run Uvicorn referencing the app inside main.py
    uvicorn.run(
        "main:app", 
        host=args.host, 
        port=args.port, 
        reload=args.reload, 
        log_level=args.log_level
    )