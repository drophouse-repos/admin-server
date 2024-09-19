import os
import json
import asyncio
import signal
import sys
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from utils.format_error import format_error
from routers import admin_dashboard_router, org_router, prices_router, order_info_router, bulk_order_router
import uvicorn
import logging
from db import connect_to_mongo, close_mongo_connection
import firebase_admin
from firebase_admin import credentials
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware
from email_service.EmailService import EmailService

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables and Firebase credentials
load_dotenv()
cred = credentials.Certificate("service_firebase.json")
firebase_admin.initialize_app(cred)

# Initialize FastAPI
app = FastAPI()
email_service = EmailService()

# Middleware setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
    ],
    allow_origin_regex=r".*\.drophouse\.ai$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SESSION_SECRET"))

# Graceful shutdown handler
async def grace_shutdown(signal, loop):
    logger.info(f"Received signal {signal.name}, shutting down gracefully...")
    await close_mongo_connection()  # Close MongoDB connection here
    # Add any other shutdown cleanup logic (e.g., closing Redis if you're using it)
    loop.stop()

@app.middleware("http")
async def session_middleware(request: Request, call_next):
    response = await call_next(request)
    session = request.cookies.get("session")
    if session:
        response.set_cookie(
            key="session",
            value=session,
            httponly=True,
            secure=True,
        )
    return response

@app.get("/")
def root():
    return {"message": "Welcome to the New Order!!!"}

SEND_EMAIL_FOR_STATUS_CODES = {429, 500}

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request, exc):
    route_info = request.scope.get("route")
    path = route_info.path if route_info else "unknown"
    name = route_info.name if route_info else "unknown"
    response = await format_error(
        path=path, name=name, code=exc.status_code, exception=exc.detail
    )
    # Send error notification email if needed
    # if exc.status_code in SEND_EMAIL_FOR_STATUS_CODES:
    #     email_service.notify_error(response)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    error_details = json.dumps(exc.errors(), indent=2)
    logger.error(f"Validation error: {error_details}")
    return JSONResponse(status_code=422, content={"detail": exc.errors()})

# Add event handlers
app.add_event_handler("startup", connect_to_mongo)
app.add_event_handler("shutdown", close_mongo_connection)
app.include_router(admin_dashboard_router)
app.include_router(org_router)
app.include_router(prices_router)
app.include_router(order_info_router)
app.include_router(bulk_order_router)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    
    # Register signal handlers for graceful shutdown
    signals = (signal.SIGINT, signal.SIGTERM)
    for s in signals:
        loop.add_signal_handler(s, lambda s=s: asyncio.create_task(grace_shutdown(s, loop)))

    try:
        port = int(os.environ.get("SERVER_PORT", 8080))
        uvicorn.run(app, host="0.0.0.0", port=port)
    except KeyboardInterrupt:
        logger.info("Shutting down due to KeyboardInterrupt...")
        loop.run_until_complete(close_mongo_connection())  # Ensure MongoDB closes
    finally:
        loop.close()