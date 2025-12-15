"""
Configuration management for HealthmateUI
"""
import os
from typing import Dict, Any


class Config:
    """Application configuration"""
    
    # AWS Configuration
    AWS_REGION = os.getenv("AWS_REGION", "us-west-2")
    AWS_ACCOUNT_ID = os.getenv("AWS_ACCOUNT_ID")  # Required - no default
    
    # Cognito Configuration (from HealthManagerMCP stack)
    COGNITO_USER_POOL_ID = os.getenv("COGNITO_USER_POOL_ID")  # Required - no default
    COGNITO_CLIENT_ID = os.getenv("COGNITO_CLIENT_ID")  # Required - no default
    COGNITO_CLIENT_SECRET = os.getenv("COGNITO_CLIENT_SECRET")  # Required - no default
    
    # HealthCoachAI Configuration
    HEALTH_COACH_AI_RUNTIME_ID = os.getenv("HEALTH_COACH_AI_RUNTIME_ID")  # Required - no default
    
    def validate_required_config(self):
        """Validate that all required configuration is present"""
        required_vars = [
            ("AWS_ACCOUNT_ID", self.AWS_ACCOUNT_ID),
            ("COGNITO_USER_POOL_ID", self.COGNITO_USER_POOL_ID),
            ("COGNITO_CLIENT_ID", self.COGNITO_CLIENT_ID),
            ("COGNITO_CLIENT_SECRET", self.COGNITO_CLIENT_SECRET),
            ("HEALTH_COACH_AI_RUNTIME_ID", self.HEALTH_COACH_AI_RUNTIME_ID),
        ]
        
        missing_vars = []
        for var_name, var_value in required_vars:
            if not var_value:
                missing_vars.append(var_name)
        
        if missing_vars:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing_vars)}. "
                f"Please run the development server with 'python run_dev.py' to auto-configure these values."
            )
        
        return True
    
    # Application Configuration
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
    DEBUG = os.getenv("DEBUG", "True").lower() == "true"
    
    # Callback URLs (will be updated when deployed)
    CALLBACK_URL = os.getenv("CALLBACK_URL", "http://localhost:8000/auth/callback")
    LOGOUT_URL = os.getenv("LOGOUT_URL", "http://localhost:8000/auth/logout")
    
    @property
    def COGNITO_DOMAIN(self) -> str:
        """Generate Cognito domain based on region"""
        return f"healthmate.auth.{self.AWS_REGION}.amazoncognito.com"
    
    @property
    def AUTHORIZATION_URL(self) -> str:
        """Generate authorization URL based on region"""
        return f"https://{self.COGNITO_DOMAIN}/oauth2/authorize"
    
    @property
    def TOKEN_URL(self) -> str:
        """Generate token URL based on region"""
        return f"https://{self.COGNITO_DOMAIN}/oauth2/token"
    
    @property
    def USER_INFO_URL(self) -> str:
        """Generate user info URL based on region"""
        return f"https://{self.COGNITO_DOMAIN}/oauth2/userInfo"
    
    @property
    def JWKS_URL(self) -> str:
        """Generate JWKS URL based on region and user pool ID"""
        return f"https://cognito-idp.{self.AWS_REGION}.amazonaws.com/{self.COGNITO_USER_POOL_ID}/.well-known/jwks.json"
    
    @classmethod
    def get_oauth_scopes(cls) -> list:
        """Get OAuth 2.0 scopes"""
        return ["openid", "profile", "email", "phone"]
    
    def get_cognito_config(self) -> Dict[str, Any]:
        """Get Cognito configuration for authentication"""
        return {
            "user_pool_id": self.COGNITO_USER_POOL_ID,
            "client_id": self.COGNITO_CLIENT_ID,
            "client_secret": self.COGNITO_CLIENT_SECRET,
            "domain": self.COGNITO_DOMAIN,
            "authorization_url": self.AUTHORIZATION_URL,
            "token_url": self.TOKEN_URL,
            "user_info_url": self.USER_INFO_URL,
            "jwks_url": self.JWKS_URL,
            "scopes": self.get_oauth_scopes(),
            "callback_url": self.CALLBACK_URL,
            "logout_url": self.LOGOUT_URL
        }
    
    def get_healthcoach_config(self) -> Dict[str, Any]:
        """Get HealthCoachAI configuration"""
        return {
            "runtime_id": self.HEALTH_COACH_AI_RUNTIME_ID,
            "region": self.AWS_REGION,
            "account_id": self.AWS_ACCOUNT_ID
        }
    



class DevelopmentConfig(Config):
    """Development environment configuration"""
    DEBUG = True
    CALLBACK_URL = "http://localhost:8000/auth/callback"
    LOGOUT_URL = "http://localhost:8000/auth/logout"


class ProductionConfig(Config):
    """Production environment configuration"""
    DEBUG = False
    SECRET_KEY = os.getenv("SECRET_KEY")  # Must be set in production
    
    # Production URLs will be set via environment variables
    CALLBACK_URL = os.getenv("CALLBACK_URL")
    LOGOUT_URL = os.getenv("LOGOUT_URL")


def get_config() -> Config:
    """Get configuration based on environment"""
    env = os.getenv("ENVIRONMENT", "development").lower()
    
    if env == "production":
        config = ProductionConfig()
    else:
        config = DevelopmentConfig()
    
    # Validate configuration when not in development server startup
    # (to avoid circular imports during run_dev.py execution)
    import sys
    if 'run_dev.py' not in sys.argv[0]:
        try:
            config.validate_required_config()
        except ValueError:
            # In development, provide helpful error message
            if env == "development":
                pass  # Let run_dev.py handle the configuration
            else:
                raise
    
    return config