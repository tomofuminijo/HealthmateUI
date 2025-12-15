"""
Session management for user authentication
"""
import json
import secrets
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from fastapi import Request, Response, HTTPException, status

from ..utils.config import get_config
from ..utils.logger import setup_logger
from ..models.auth import UserSession, UserInfo, CognitoTokens, AuthStatus

logger = setup_logger(__name__)
config = get_config()


class SessionManager:
    """Manages user sessions using secure cookies"""
    
    def __init__(self):
        self.session_timeout = 3600  # 1 hour
        self.cookie_name = "healthmate_session"
        # For localhost development, cookies need specific settings
        self.cookie_secure = False  # Must be False for HTTP (localhost)
        self.cookie_httponly = False  # Set to False for debugging
        self.cookie_samesite = "lax"  # Lax allows cross-site requests
        
        # Debug: Log cookie configuration
        logger.debug(f"SessionManager initialized: secure={self.cookie_secure}, httponly={self.cookie_httponly}, samesite={self.cookie_samesite}, debug={config.DEBUG}")
        
        # In-memory session store (for development)
        # In production, this should be replaced with Redis or database
        self._sessions: Dict[str, UserSession] = {}
    
    def create_session(self, user_info: UserInfo, tokens: CognitoTokens) -> str:
        """
        Create a new user session
        
        Args:
            user_info: User information
            tokens: Authentication tokens
            
        Returns:
            str: Session ID
        """
        try:
            # Generate secure session ID
            session_id = secrets.token_urlsafe(32)
            
            # Create session
            session = UserSession(
                user_info=user_info,
                tokens=tokens
            )
            
            # Store session
            self._sessions[session_id] = session
            
            logger.info(f"Created session for user: {user_info.user_id}")
            logger.debug(f"Session store now has {len(self._sessions)} sessions")
            logger.debug(f"Session ID: {session_id}")
            return session_id
            
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            raise
    
    def get_session(self, session_id: str) -> Optional[UserSession]:
        """
        Get session by ID
        
        Args:
            session_id: Session ID
            
        Returns:
            Optional[UserSession]: Session data or None if not found/expired
        """
        try:
            session = self._sessions.get(session_id)
            
            if not session:
                return None
            
            # Check if session is expired
            if session.is_expired():
                logger.info(f"Session expired for user: {session.user_info.user_id}")
                self.delete_session(session_id)
                return None
            
            # Update last accessed time
            session.update_last_accessed()
            
            return session
            
        except Exception as e:
            logger.error(f"Failed to get session: {e}")
            return None
    
    def update_session_tokens(self, session_id: str, tokens: CognitoTokens) -> bool:
        """
        Update session tokens (after refresh)
        
        Args:
            session_id: Session ID
            tokens: New tokens
            
        Returns:
            bool: True if successful
        """
        try:
            session = self._sessions.get(session_id)
            
            if not session:
                return False
            
            # Update tokens
            session.tokens = tokens
            session.update_last_accessed()
            
            logger.info(f"Updated tokens for session: {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update session tokens: {e}")
            return False
    
    def delete_session(self, session_id: str) -> bool:
        """
        Delete session
        
        Args:
            session_id: Session ID
            
        Returns:
            bool: True if successful
        """
        try:
            session = self._sessions.pop(session_id, None)
            
            if session:
                logger.info(f"Deleted session for user: {session.user_info.user_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to delete session: {e}")
            return False
    
    def set_session_cookie(self, response: Response, session_id: str):
        """
        Set session cookie in response
        
        Args:
            response: FastAPI response object
            session_id: Session ID to set
        """
        try:
            # Debug: Log cookie settings
            logger.debug(f"Setting cookie '{self.cookie_name}' with: secure={self.cookie_secure}, httponly={self.cookie_httponly}, samesite={self.cookie_samesite}, path='/'")
            logger.debug(f"Session ID to set: {session_id}")
            
            # For development on localhost, use minimal cookie settings
            response.set_cookie(
                key=self.cookie_name,
                value=session_id,
                max_age=self.session_timeout,
                httponly=False,  # Allow JavaScript access for debugging
                secure=False,    # HTTP only (localhost)
                samesite="lax",  # Allow cross-site requests
                path="/",
                domain=None      # Let browser determine domain
            )
            
            logger.info(f"Set session cookie: {session_id[:20]}...")
            
        except Exception as e:
            logger.error(f"Failed to set session cookie: {e}")
            raise
    
    def get_session_from_request(self, request: Request) -> Optional[UserSession]:
        """
        Get session from request cookies
        
        Args:
            request: FastAPI request object
            
        Returns:
            Optional[UserSession]: Session data or None
        """
        try:
            # Debug: Log all cookies
            all_cookies = dict(request.cookies)
            logger.debug(f"All cookies in request: {list(all_cookies.keys())}")
            
            session_id = request.cookies.get(self.cookie_name)
            logger.debug(f"Looking for cookie '{self.cookie_name}': {session_id[:20] if session_id else 'None'}...")
            
            if not session_id:
                logger.debug(f"No session cookie found")
                return None
            
            # Debug: Log session store status
            logger.debug(f"Session store has {len(self._sessions)} sessions")
            
            session = self.get_session(session_id)
            if session:
                logger.debug(f"Found session for user: {session.user_info.user_id}")
            else:
                logger.debug(f"Session not found in store for ID: {session_id[:20]}...")
            
            return session
            
        except Exception as e:
            logger.error(f"Failed to get session from request: {e}")
            return None
    
    def clear_session_cookie(self, response: Response):
        """
        Clear session cookie
        
        Args:
            response: FastAPI response object
        """
        try:
            response.delete_cookie(
                key=self.cookie_name,
                path="/",
                secure=self.cookie_secure,
                httponly=self.cookie_httponly,
                samesite=self.cookie_samesite
            )
            
            logger.debug("Cleared session cookie")
            
        except Exception as e:
            logger.error(f"Failed to clear session cookie: {e}")
    
    def cleanup_expired_sessions(self):
        """
        Clean up expired sessions (should be called periodically)
        """
        try:
            expired_sessions = []
            
            for session_id, session in self._sessions.items():
                if session.is_expired():
                    expired_sessions.append(session_id)
            
            for session_id in expired_sessions:
                self.delete_session(session_id)
            
            if expired_sessions:
                logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")
                
        except Exception as e:
            logger.error(f"Failed to cleanup expired sessions: {e}")
    
    def get_auth_status(self, request: Request) -> AuthStatus:
        """
        Get authentication status from request
        
        Args:
            request: FastAPI request object
            
        Returns:
            AuthStatus: Authentication status
        """
        try:
            session = self.get_session_from_request(request)
            
            if not session:
                return AuthStatus(is_authenticated=False)
            
            return AuthStatus(
                is_authenticated=True,
                user_id=session.user_info.user_id,
                email=session.user_info.email,
                session_expires_at=session.tokens.expires_at
            )
            
        except Exception as e:
            logger.error(f"Failed to get auth status: {e}")
            return AuthStatus(is_authenticated=False)


# Global session manager instance
_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """Get global session manager instance"""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager


async def require_authentication(request: Request) -> UserSession:
    """
    Dependency to require authentication
    
    Args:
        request: FastAPI request object
        
    Returns:
        UserSession: Current user session
        
    Raises:
        HTTPException: If not authenticated
    """
    session_manager = get_session_manager()
    session = session_manager.get_session_from_request(request)
    
    # If no session from cookie, try JWT from Authorization header
    if not session:
        session = await _get_session_from_jwt(request)
    
    if not session:
        logger.warning(f"Authentication failed for {request.url.path}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    return session


async def _get_session_from_jwt(request: Request):
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
        
        # Import here to avoid circular imports
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


def get_current_user(request: Request) -> Optional[UserSession]:
    """
    Get current user session (optional)
    
    Args:
        request: FastAPI request object
        
    Returns:
        Optional[UserSession]: Current user session or None
    """
    try:
        session_manager = get_session_manager()
        
        # First try to get session from cookie
        session = session_manager.get_session_from_request(request)
        
        if session:
            logger.debug(f"Found session from cookie for user: {session.user_info.user_id}")
            return session
        
        # If no session from cookie, try JWT from Authorization header
        # Note: This is a synchronous function, so we can't use await here
        # We'll implement a synchronous version for JWT checking
        logger.debug("No session from cookie, checking for JWT token...")
        
        # Get Authorization header
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            logger.debug("No valid Authorization header found")
            return None
        
        # For now, just return None and let the authentication middleware handle JWT
        # This function is used for optional authentication checks
        logger.debug("JWT token found but not processed in get_current_user")
        return None
        
    except Exception as e:
        logger.error(f"Error in get_current_user: {e}")
        return None