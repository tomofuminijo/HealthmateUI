"""
Authentication API routes
"""
from fastapi import APIRouter, Request, Response, HTTPException, status, Query
from fastapi.responses import RedirectResponse, JSONResponse
from typing import Optional
import urllib.parse

from ..utils.logger import setup_logger
from ..models.auth import (
    LoginRequest, LoginResponse, LogoutRequest, 
    TokenRefreshRequest, TokenRefreshResponse, AuthStatus
)
from .cognito import get_cognito_client
from .session import get_session_manager, require_authentication, get_current_user

logger = setup_logger(__name__)

# Create router
router = APIRouter(prefix="/auth", tags=["authentication"])

# Get global instances
cognito_client = get_cognito_client()
session_manager = get_session_manager()


@router.get("/callback")
async def auth_callback_get(
    request: Request,
    response: Response,
    code: Optional[str] = Query(None, description="Authorization code"),
    state: Optional[str] = Query(None, description="OAuth state parameter"),
    error: Optional[str] = Query(None, description="OAuth error"),
    error_description: Optional[str] = Query(None, description="OAuth error description"),
    next_url: Optional[str] = Query(None, alias="next", description="Redirect URL after login")
):
    """
    Handle OAuth callback from Cognito (GET method)
    """
    return await _handle_auth_callback(request, response, code, state, error, error_description, next_url)


@router.post("/callback")
async def auth_callback_post(request: Request, response: Response):
    """
    Handle OAuth callback from Cognito (POST method for JavaScript)
    """
    try:
        body = await request.json()
        code = body.get("code")
        state = body.get("state")
        error = body.get("error")
        error_description = body.get("error_description")
        next_url = body.get("next")
        
        # Use the same handler as GET
        result = await _handle_auth_callback(request, response, code, state, error, error_description, next_url)
        
        # For POST requests, return JSON instead of redirect
        if isinstance(result, RedirectResponse):
            if "error=" in result.url:
                return JSONResponse(
                    content={"success": False, "error": "Authentication failed"},
                    status_code=400
                )
            else:
                return JSONResponse(
                    content={"success": True, "redirect_url": result.url},
                    status_code=200
                )
        
        return result
        
    except Exception as e:
        logger.error(f"POST callback failed: {e}")
        return JSONResponse(
            content={"success": False, "error": str(e)},
            status_code=500
        )


async def _handle_auth_callback(
    request: Request,
    response: Response,
    code: Optional[str],
    state: Optional[str],
    error: Optional[str],
    error_description: Optional[str],
    next_url: Optional[str]
):
    """
    Handle OAuth callback from Cognito
    """
    try:
        # Check for OAuth errors
        if error:
            error_msg = error_description or error
            logger.error(f"OAuth error: {error_msg}")
            return RedirectResponse(
                url=f"/login?error={urllib.parse.quote(error_msg)}", 
                status_code=302
            )
        
        # Validate authorization code
        if not code:
            logger.error("Missing authorization code in callback")
            return RedirectResponse(
                url="/login?error=Missing authorization code", 
                status_code=302
            )
        
        # Exchange code for tokens
        tokens = await cognito_client.exchange_code_for_tokens(code)
        
        # Get user information
        user_info = await cognito_client.get_user_info(tokens.access_token)
        
        # Create session
        session_id = session_manager.create_session(user_info, tokens)
        
        # Determine redirect URL
        redirect_url = next_url or "/chat"
        
        # Create redirect response and set session cookie on it
        redirect_response = RedirectResponse(url=redirect_url, status_code=302)
        session_manager.set_session_cookie(redirect_response, session_id)
        
        logger.info(f"User {user_info.email} logged in successfully")
        
        return redirect_response
        
    except Exception as e:
        logger.error(f"Authentication callback failed: {e}")
        error_msg = "Authentication failed. Please try again."
        return RedirectResponse(
            url=f"/login?error={urllib.parse.quote(error_msg)}", 
            status_code=302
        )


@router.post("/logout")
async def logout(request: Request, response: Response):
    """
    Logout user and clear session
    """
    try:
        # Get current session
        session = get_current_user(request)
        
        if session:
            # Get session ID from cookie
            session_id = request.cookies.get(session_manager.cookie_name)
            
            if session_id:
                # Delete session
                session_manager.delete_session(session_id)
            
            # Logout from Cognito (optional)
            try:
                await cognito_client.logout_user(session.tokens.access_token)
            except Exception as e:
                logger.warning(f"Cognito logout failed: {e}")
            
            logger.info(f"User {session.user_info.email} logged out")
        
        # Clear session cookie
        session_manager.clear_session_cookie(response)
        
        return JSONResponse(
            content={"success": True, "message": "Logged out successfully"},
            status_code=200
        )
        
    except Exception as e:
        logger.error(f"Logout failed: {e}")
        # Clear cookie anyway
        session_manager.clear_session_cookie(response)
        return JSONResponse(
            content={"success": False, "error": "Logout failed"},
            status_code=500
        )


@router.get("/status", response_model=AuthStatus)
async def auth_status(request: Request):
    """
    Get current authentication status
    """
    try:
        return session_manager.get_auth_status(request)
        
    except Exception as e:
        logger.error(f"Failed to get auth status: {e}")
        return AuthStatus(is_authenticated=False)


@router.post("/refresh", response_model=TokenRefreshResponse)
async def refresh_tokens(
    request: Request,
    response: Response,
    refresh_request: TokenRefreshRequest
):
    """
    Refresh access token using refresh token
    """
    try:
        # Get current session
        session = get_current_user(request)
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No active session"
            )
        
        # Refresh tokens
        new_tokens = await cognito_client.refresh_tokens(refresh_request.refresh_token)
        
        # Update session
        session_id = request.cookies.get(session_manager.cookie_name)
        if session_id:
            session_manager.update_session_tokens(session_id, new_tokens)
        
        logger.info(f"Tokens refreshed for user: {session.user_info.user_id}")
        
        return TokenRefreshResponse(
            success=True,
            tokens=new_tokens
        )
        
    except Exception as e:
        logger.error(f"Token refresh failed: {e}")
        return TokenRefreshResponse(
            success=False,
            error_message=str(e)
        )


@router.get("/user")
async def get_current_user_info(session: dict = require_authentication):
    """
    Get current user information (requires authentication)
    """
    try:
        return {
            "user_id": session.user_info.user_id,
            "email": session.user_info.email,
            "username": session.user_info.username,
            "given_name": session.user_info.given_name,
            "family_name": session.user_info.family_name,
            "email_verified": session.user_info.email_verified
        }
        
    except Exception as e:
        logger.error(f"Failed to get user info: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user information"
        )


@router.post("/demo")
async def demo_login(request: Request, response: Response):
    """
    Demo mode login (development only)
    """
    try:
        from ..utils.config import get_config
        config = get_config()
        
        # Only allow in development mode
        if not config.DEBUG:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Demo mode is only available in development"
            )
        
        # Create demo user info
        from ..models.auth import UserInfo, CognitoTokens
        import uuid
        from datetime import datetime, timedelta
        
        demo_user = UserInfo(
            user_id=f"demo-user-{uuid.uuid4().hex[:8]}",
            username="demo_user",
            email="demo@healthmate.local",
            given_name="Demo",
            family_name="User",
            email_verified=True
        )
        
        # Create demo tokens (mock)
        demo_tokens = CognitoTokens(
            access_token="demo-access-token",
            id_token="demo-id-token",
            refresh_token="demo-refresh-token",
            token_type="Bearer",
            expires_in=3600,
            expires_at=datetime.utcnow() + timedelta(seconds=3600)
        )
        
        # Create session
        session_id = session_manager.create_session(demo_user, demo_tokens)
        
        logger.info(f"Demo user logged in: {demo_user.email}")
        
        # Create JSON response
        json_response = JSONResponse(
            content={"success": True, "message": "Demo login successful"},
            status_code=200
        )
        
        # Set session cookie on the JSON response
        session_manager.set_session_cookie(json_response, session_id)
        
        return json_response
        
    except Exception as e:
        logger.error(f"Demo login failed: {e}")
        return JSONResponse(
            content={"success": False, "error": str(e)},
            status_code=500
        )


@router.post("/verify-token")
async def verify_token(request: Request):
    """
    Verify JWT token (for debugging/testing)
    """
    try:
        # Get token from Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or invalid Authorization header"
            )
        
        token = auth_header.split(" ")[1]
        
        # Verify token
        is_valid, payload = await cognito_client.verify_jwt_token(token)
        
        return {
            "valid": is_valid,
            "payload": payload if is_valid else None
        }
        
    except Exception as e:
        logger.error(f"Token verification failed: {e}")
        return {
            "valid": False,
            "error": str(e)
        }