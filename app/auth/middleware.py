"""
Authentication middleware for FastAPI
"""
from fastapi import Request, Response
from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from typing import List, Set
import re

from ..utils.logger import setup_logger
from .session import get_session_manager

logger = setup_logger(__name__)


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """
    Middleware to handle authentication for protected routes
    """
    
    def __init__(
        self, 
        app: ASGIApp,
        protected_paths: List[str] = None,
        public_paths: List[str] = None,
        login_url: str = "/login"
    ):
        super().__init__(app)
        
        # Default protected paths (require authentication)
        self.protected_paths = protected_paths or [
            "/chat",
            "/api/chat",
            "/api/user",
            "/api/health-data"
        ]
        
        # Default public paths (no authentication required)
        self.public_paths = public_paths or [
            "/",
            "/login",
            "/health",
            "/api/status",
            "/auth/callback",
            "/auth/logout",
            "/static",
            "/favicon.ico"
        ]
        
        self.login_url = login_url
        self.session_manager = get_session_manager()
        
        # Compile regex patterns for path matching
        self._protected_patterns = [re.compile(self._path_to_regex(path)) for path in self.protected_paths]
        self._public_patterns = [re.compile(self._path_to_regex(path)) for path in self.public_paths]
    
    def _path_to_regex(self, path: str) -> str:
        """Convert path pattern to regex"""
        # Escape special regex characters except *
        escaped = re.escape(path)
        # Replace escaped \* with .* for wildcard matching
        regex = escaped.replace(r'\*', '.*')
        # Ensure exact match or prefix match for directories
        if path.endswith('/'):
            regex += '.*'
        else:
            regex += '(?:/.*)?$'
        return f'^{regex}'
    
    def _is_protected_path(self, path: str) -> bool:
        """Check if path requires authentication"""
        # First check if it's explicitly public
        for pattern in self._public_patterns:
            if pattern.match(path):
                return False
        
        # Then check if it's protected
        for pattern in self._protected_patterns:
            if pattern.match(path):
                return True
        
        # Default to public for unmatched paths
        return False
    
    async def _get_session_from_jwt(self, request: Request):
        """Get session from JWT token in Authorization header"""
        try:
            # Get Authorization header
            auth_header = request.headers.get('Authorization')
            logger.debug(f"Authorization header: {auth_header[:50] if auth_header else 'None'}...")
            
            if not auth_header or not auth_header.startswith('Bearer '):
                logger.debug("No valid Authorization header found")
                return None
            
            # Extract JWT token
            jwt_token = auth_header[7:]  # Remove 'Bearer ' prefix
            logger.debug(f"Extracted JWT token: {jwt_token[:50]}...")
            
            # Create a temporary session from JWT
            from .cognito import get_cognito_client
            from ..models.auth import UserInfo, CognitoTokens, UserSession
            from datetime import datetime, timedelta
            
            cognito_client = get_cognito_client()
            
            # For testing: decode JWT without verification
            logger.debug("Decoding JWT token for testing...")
            payload = cognito_client.decode_jwt_payload(jwt_token)
            logger.debug(f"JWT decode result: payload={bool(payload)}")
            
            if not payload:
                logger.warning("JWT token decode failed")
                return None
            
            # Create UserInfo from JWT payload
            user_info = UserInfo(
                user_id=payload.get('sub'),
                email=payload.get('email', ''),
                username=payload.get('username', payload.get('cognito:username', '')),
                email_verified=payload.get('email_verified', False)
            )
            logger.debug(f"Created UserInfo for user: {user_info.user_id}")
            
            # Create temporary tokens object
            tokens = CognitoTokens(
                access_token=jwt_token,
                refresh_token="",  # Not available from header
                id_token="",       # Not available from header
                expires_in=3600,   # Default 1 hour
                expires_at=datetime.now() + timedelta(hours=1)
            )
            
            # Create temporary session
            session = UserSession(
                user_info=user_info,
                tokens=tokens
            )
            
            logger.info(f"Successfully created session from JWT for user: {user_info.user_id}")
            return session
            
        except Exception as e:
            logger.error(f"JWT session creation error: {e}")
            import traceback
            logger.error(f"JWT session creation traceback: {traceback.format_exc()}")
            return None
    
    async def dispatch(self, request: Request, call_next):
        """Process request through authentication middleware"""
        try:
            path = request.url.path
            method = request.method
            
            # Skip authentication for non-GET requests to public endpoints
            # and for static files
            if (path.startswith('/static/') or 
                path == '/favicon.ico' or
                path.startswith('/auth/') or
                path in ['/health', '/api/status']):
                return await call_next(request)
            
            # Check if path requires authentication
            if not self._is_protected_path(path):
                return await call_next(request)
            
            # Get current session (try both cookie and Authorization header)
            session = self.session_manager.get_session_from_request(request)
            
            # If no session from cookie, try JWT from Authorization header
            if not session and path.startswith('/api/'):
                session = await self._get_session_from_jwt(request)
            
            if not session:
                logger.info(f"Unauthenticated access to protected path: {path}")
                
                # For API endpoints, return 401
                if path.startswith('/api/'):
                    from fastapi import HTTPException, status
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Authentication required"
                    )
                
                # For web pages, redirect to login
                login_redirect = f"{self.login_url}?next={path}"
                return RedirectResponse(url=login_redirect, status_code=302)
            
            # Add user info to request state for use in route handlers
            request.state.user_session = session
            request.state.user_id = session.user_info.user_id
            request.state.user_email = session.user_info.email
            
            # Process request
            response = await call_next(request)
            
            return response
            
        except Exception as e:
            logger.error(f"Authentication middleware error: {e}")
            # Let the request continue and let the application handle the error
            return await call_next(request)


class SessionCleanupMiddleware(BaseHTTPMiddleware):
    """
    Middleware to periodically clean up expired sessions
    """
    
    def __init__(self, app: ASGIApp, cleanup_interval: int = 100):
        super().__init__(app)
        self.cleanup_interval = cleanup_interval
        self.request_count = 0
        self.session_manager = get_session_manager()
    
    async def dispatch(self, request: Request, call_next):
        """Process request and occasionally clean up sessions"""
        try:
            # Increment request counter
            self.request_count += 1
            
            # Clean up expired sessions periodically
            if self.request_count % self.cleanup_interval == 0:
                logger.debug("Running session cleanup")
                self.session_manager.cleanup_expired_sessions()
            
            # Process request
            response = await call_next(request)
            
            return response
            
        except Exception as e:
            logger.error(f"Session cleanup middleware error: {e}")
            return await call_next(request)


def add_auth_middleware(app, **kwargs):
    """
    Add authentication middleware to FastAPI app
    
    Args:
        app: FastAPI application
        **kwargs: Additional arguments for AuthenticationMiddleware
    """
    # Add session cleanup middleware first
    app.add_middleware(SessionCleanupMiddleware)
    
    # Add authentication middleware
    app.add_middleware(AuthenticationMiddleware, **kwargs)
    
    logger.info("Authentication middleware added to application")