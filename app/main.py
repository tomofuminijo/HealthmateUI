"""
HealthmateUI FastAPI Application
Main application entry point for the Backend for Frontend (BFF)
"""
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
import uvicorn
import os
from contextlib import asynccontextmanager

from .utils.config import get_config
from .utils.logger import setup_logger
from .auth import auth_router, add_auth_middleware
from .healthcoach import healthcoach_router
from .api.unified_chat import router as chat_router

# Get configuration and logger
config = get_config()
logger = setup_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("HealthmateUI application starting up...")
    logger.info(f"Environment: {config.__class__.__name__}")
    logger.info(f"Debug mode: {config.DEBUG}")
    logger.info(f"Cognito User Pool: {config.COGNITO_USER_POOL_ID}")
    logger.info(f"HealthCoachAI Runtime: {config.HEALTH_COACH_AI_RUNTIME_ID}")
    
    yield
    
    # Shutdown
    logger.info("HealthmateUI application shutting down...")


# Create FastAPI application
app = FastAPI(
    title="HealthmateUI",
    description="Web interface for HealthCoach AI interactions",
    version="1.0.0",
    debug=config.DEBUG,
    lifespan=lifespan
)

# Add security middleware
app.add_middleware(
    TrustedHostMiddleware, 
    allowed_hosts=["localhost", "127.0.0.1", "*.amazonaws.com"] if config.DEBUG else ["*.amazonaws.com"]
)

# Add CORS middleware for development
if config.DEBUG:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://localhost:8000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup Jinja2 templates
templates = Jinja2Templates(directory="templates")

# Add authentication middleware
add_auth_middleware(app)

# Include authentication routes
app.include_router(auth_router)

# Include HealthCoachAI routes
app.include_router(healthcoach_router)

# Include Chat API routes (unified)
app.include_router(chat_router)


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint for load balancers"""
    return {
        "status": "healthy",
        "service": "HealthmateUI",
        "version": "1.0.0",
        "environment": config.__class__.__name__
    }


# Root endpoint - redirect to login or chat based on authentication
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Root endpoint - main application entry point"""
    from .auth.session import get_current_user
    
    # Check authentication status and redirect accordingly
    user_session = get_current_user(request)
    if user_session:
        # User is authenticated, redirect to chat
        return RedirectResponse(url="/chat", status_code=302)
    else:
        # User is not authenticated, redirect to login
        return RedirectResponse(url="/login", status_code=302)


# Login page
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Login page"""
    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "title": "Login - HealthmateUI",
            "cognito_config": config.get_cognito_config()
        }
    )


# Chat page (requires authentication)
@app.get("/chat", response_class=HTMLResponse)
async def chat_page(request: Request):
    """Chat interface page"""
    from .auth.session import get_current_user
    
    # Check authentication
    user_session = get_current_user(request)
    if not user_session:
        # Redirect to login if not authenticated
        return RedirectResponse(url="/login", status_code=302)
    
    return templates.TemplateResponse(
        "chat/chat_page.html",
        {
            "request": request,
            "title": "Health Coach - HealthmateUI",
            "user": user_session.user_info
        }
    )


# API routes will be added here
@app.get("/api/status")
async def api_status():
    """API status endpoint"""
    return {
        "api_status": "operational",
        "cognito_configured": bool(config.COGNITO_USER_POOL_ID),
        "healthcoach_configured": bool(config.HEALTH_COACH_AI_RUNTIME_ID)
    }


# Error handlers
@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    """Custom 404 handler"""
    return templates.TemplateResponse(
        "error.html",
        {
            "request": request,
            "title": "Page Not Found",
            "error_code": 404,
            "error_message": "The requested page was not found."
        },
        status_code=404
    )


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc: HTTPException):
    """Custom 500 handler"""
    logger.error(f"Internal server error: {exc}")
    return templates.TemplateResponse(
        "error.html",
        {
            "request": request,
            "title": "Internal Server Error",
            "error_code": 500,
            "error_message": "An internal server error occurred."
        },
        status_code=500
    )


# Development server
if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=config.DEBUG,
        log_level="debug" if config.DEBUG else "info"
    )