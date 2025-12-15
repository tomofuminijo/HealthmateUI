"""
Authentication module for HealthmateUI

This module provides:
- Cognito OAuth 2.0 authentication
- Session management
- JWT token verification
- Authentication middleware
"""

from .cognito import CognitoAuthClient, get_cognito_client
from .session import SessionManager, get_session_manager, require_authentication, get_current_user
from .middleware import AuthenticationMiddleware, add_auth_middleware
from .routes import router as auth_router

__all__ = [
    'CognitoAuthClient',
    'get_cognito_client',
    'SessionManager', 
    'get_session_manager',
    'require_authentication',
    'get_current_user',
    'AuthenticationMiddleware',
    'add_auth_middleware',
    'auth_router'
]