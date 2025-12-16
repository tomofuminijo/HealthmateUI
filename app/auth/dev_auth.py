"""
Development authentication for testing without Cognito
"""
from datetime import datetime, timedelta
from typing import Optional
from fastapi import Request

from ..models.auth import UserSession, UserInfo, CognitoTokens
from ..utils.logger import setup_logger

logger = setup_logger(__name__)


class DevAuthManager:
    """Development authentication manager for testing"""
    
    def __init__(self):
        self.test_users = {
            "test-user-123": {
                "user_id": "test-user-123",
                "email": "test@healthmate.dev",
                "username": "testuser",
                "given_name": "Test",
                "family_name": "User"
            }
        }
    
    def create_test_session(self, user_id: str = "test-user-123") -> UserSession:
        """Create a test user session"""
        user_data = self.test_users.get(user_id, self.test_users["test-user-123"])
        
        user_info = UserInfo(
            user_id=user_data["user_id"],
            email=user_data["email"],
            username=user_data["username"],
            given_name=user_data["given_name"],
            family_name=user_data["family_name"],
            email_verified=True
        )
        
        # Create fake tokens
        tokens = CognitoTokens(
            access_token="dev-access-token-" + user_id,
            refresh_token="dev-refresh-token-" + user_id,
            id_token="dev-id-token-" + user_id,
            expires_in=3600,
            expires_at=datetime.utcnow() + timedelta(hours=1)
        )
        
        session = UserSession(
            user_info=user_info,
            tokens=tokens,
            auth_session_id="dev-auth-session-" + user_id
        )
        
        logger.info(f"Created development test session for user: {user_id}")
        return session
    
    def get_test_session_from_request(self, request: Request) -> Optional[UserSession]:
        """Get test session from request (for development)"""
        # Check for test user parameter
        test_user = request.query_params.get("test_user", "test-user-123")
        
        # Check for dev mode header
        if request.headers.get("X-Dev-Mode") == "true":
            return self.create_test_session(test_user)
        
        # Check for dev cookie
        if request.cookies.get("dev_mode") == "true":
            return self.create_test_session(test_user)
        
        return None


# Global dev auth manager
_dev_auth_manager: Optional[DevAuthManager] = None


def get_dev_auth_manager() -> DevAuthManager:
    """Get global dev auth manager instance"""
    global _dev_auth_manager
    if _dev_auth_manager is None:
        _dev_auth_manager = DevAuthManager()
    return _dev_auth_manager


def create_dev_session_for_testing() -> UserSession:
    """Create a development session for testing"""
    dev_auth = get_dev_auth_manager()
    return dev_auth.create_test_session()