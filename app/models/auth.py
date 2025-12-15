"""
Authentication related data models
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
import json


class CognitoTokens(BaseModel):
    """Cognito OAuth 2.0 tokens"""
    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="Refresh token")
    id_token: str = Field(..., description="ID token")
    token_type: str = Field(default="Bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration in seconds")
    expires_at: datetime = Field(..., description="Token expiration timestamp")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class UserInfo(BaseModel):
    """User information from Cognito"""
    user_id: str = Field(..., alias="sub", description="User ID (Cognito sub)")
    email: Optional[str] = Field(None, description="User email")
    email_verified: Optional[bool] = Field(None, description="Email verification status")
    username: Optional[str] = Field(None, description="Username")
    given_name: Optional[str] = Field(None, description="Given name")
    family_name: Optional[str] = Field(None, description="Family name")
    phone_number: Optional[str] = Field(None, description="Phone number")
    phone_number_verified: Optional[bool] = Field(None, description="Phone verification status")
    
    class Config:
        populate_by_name = True


class UserSession(BaseModel):
    """User session data"""
    user_info: UserInfo = Field(..., description="User information")
    tokens: CognitoTokens = Field(..., description="Authentication tokens")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Session creation time")
    last_accessed: datetime = Field(default_factory=datetime.utcnow, description="Last access time")
    
    def is_expired(self) -> bool:
        """Check if the session is expired"""
        return datetime.utcnow() > self.tokens.expires_at
    
    def update_last_accessed(self):
        """Update last accessed timestamp"""
        self.last_accessed = datetime.utcnow()
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class AuthStatus(BaseModel):
    """Authentication status response"""
    is_authenticated: bool = Field(..., description="Authentication status")
    user_id: Optional[str] = Field(None, description="User ID if authenticated")
    email: Optional[str] = Field(None, description="User email if authenticated")
    session_expires_at: Optional[datetime] = Field(None, description="Session expiration time")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class LoginRequest(BaseModel):
    """Login request data"""
    authorization_code: str = Field(..., description="OAuth authorization code")
    state: Optional[str] = Field(None, description="OAuth state parameter")


class LoginResponse(BaseModel):
    """Login response data"""
    success: bool = Field(..., description="Login success status")
    redirect_url: Optional[str] = Field(None, description="Redirect URL after login")
    error_message: Optional[str] = Field(None, description="Error message if login failed")


class LogoutRequest(BaseModel):
    """Logout request data"""
    logout_uri: Optional[str] = Field(None, description="Post-logout redirect URI")


class TokenRefreshRequest(BaseModel):
    """Token refresh request"""
    refresh_token: str = Field(..., description="Refresh token")


class TokenRefreshResponse(BaseModel):
    """Token refresh response"""
    success: bool = Field(..., description="Refresh success status")
    tokens: Optional[CognitoTokens] = Field(None, description="New tokens if successful")
    error_message: Optional[str] = Field(None, description="Error message if refresh failed")