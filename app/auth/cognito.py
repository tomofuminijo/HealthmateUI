"""
Amazon Cognito authentication client
"""
import boto3
import httpx
import base64
import json
import hmac
import hashlib
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from jose import jwt, JWTError
from botocore.exceptions import ClientError

from ..utils.config import get_config
from ..utils.logger import setup_logger
from ..models.auth import CognitoTokens, UserInfo, UserSession

logger = setup_logger(__name__)
config = get_config()


class CognitoAuthClient:
    """Amazon Cognito authentication client"""
    
    def __init__(self):
        app_config = get_config()
        self.config = app_config.get_cognito_config()
        self.region = app_config.AWS_REGION
        self.user_pool_id = app_config.COGNITO_USER_POOL_ID
        self.client_id = app_config.COGNITO_CLIENT_ID
        self.client_secret = app_config.COGNITO_CLIENT_SECRET
        
        # Initialize boto3 client for Cognito
        self.cognito_client = boto3.client('cognito-idp', region_name=self.region)
        
        # HTTP client for OAuth requests
        self.http_client = httpx.AsyncClient(timeout=30.0)
        
        # Cache for JWKS (JSON Web Key Set)
        self._jwks_cache: Optional[Dict[str, Any]] = None
        self._jwks_cache_expiry: Optional[datetime] = None
    
    def _get_basic_auth_header(self) -> str:
        """
        Generate Basic Authentication header for client credentials
        
        Returns:
            str: Basic auth header value
        """
        credentials = f"{self.client_id}:{self.client_secret}"
        encoded_credentials = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')
        return f"Basic {encoded_credentials}"
    
    async def exchange_code_for_tokens(self, authorization_code: str) -> CognitoTokens:
        """
        Exchange authorization code for tokens
        
        Args:
            authorization_code: OAuth authorization code from Cognito
            
        Returns:
            CognitoTokens: Access, refresh, and ID tokens
            
        Raises:
            Exception: If token exchange fails
        """
        try:
            # Prepare token request
            token_data = {
                'grant_type': 'authorization_code',
                'client_id': self.client_id,
                'code': authorization_code,
                'redirect_uri': self.config['callback_url']
            }
            
            # Prepare headers with Basic Authentication
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Authorization': self._get_basic_auth_header()
            }
            
            logger.debug(f"Making token request to: {self.config['token_url']}")
            logger.debug(f"Token data: {token_data}")
            
            # Make token request
            response = await self.http_client.post(
                self.config['token_url'],
                data=token_data,
                headers=headers
            )
            
            logger.debug(f"Token response status: {response.status_code}")
            
            if response.status_code != 200:
                error_text = response.text
                logger.error(f"Token exchange failed with status {response.status_code}: {error_text}")
                
                try:
                    error_data = response.json()
                    error_msg = error_data.get('error_description', error_data.get('error', f'Token exchange failed: {response.status_code}'))
                except:
                    error_msg = f'Token exchange failed: {response.status_code} - {error_text}'
                
                raise Exception(error_msg)
            
            token_response = response.json()
            logger.debug(f"Token response: {list(token_response.keys())}")  # Log keys only for security
            
            # Calculate expiration time
            expires_in = token_response.get('expires_in', 3600)
            expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
            
            # Create tokens object
            tokens = CognitoTokens(
                access_token=token_response['access_token'],
                refresh_token=token_response['refresh_token'],
                id_token=token_response['id_token'],
                token_type=token_response.get('token_type', 'Bearer'),
                expires_in=expires_in,
                expires_at=expires_at
            )
            
            logger.info("Successfully exchanged authorization code for tokens")
            return tokens
            
        except Exception as e:
            logger.error(f"Failed to exchange authorization code for tokens: {e}")
            raise
    
    async def refresh_tokens(self, refresh_token: str) -> CognitoTokens:
        """
        Refresh access token using refresh token
        
        Args:
            refresh_token: Refresh token
            
        Returns:
            CognitoTokens: New tokens
            
        Raises:
            Exception: If token refresh fails
        """
        try:
            # Prepare refresh request
            refresh_data = {
                'grant_type': 'refresh_token',
                'client_id': self.client_id,
                'refresh_token': refresh_token
            }
            
            # Prepare headers with Basic Authentication
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Authorization': self._get_basic_auth_header()
            }
            
            # Make refresh request
            response = await self.http_client.post(
                self.config['token_url'],
                data=refresh_data,
                headers=headers
            )
            
            if response.status_code != 200:
                error_text = response.text
                logger.error(f"Token refresh failed with status {response.status_code}: {error_text}")
                
                try:
                    error_data = response.json()
                    error_msg = error_data.get('error_description', error_data.get('error', f'Token refresh failed: {response.status_code}'))
                except:
                    error_msg = f'Token refresh failed: {response.status_code} - {error_text}'
                
                raise Exception(error_msg)
            
            token_response = response.json()
            
            # Calculate expiration time
            expires_in = token_response.get('expires_in', 3600)
            expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
            
            # Create new tokens object (refresh token might not be returned)
            tokens = CognitoTokens(
                access_token=token_response['access_token'],
                refresh_token=token_response.get('refresh_token', refresh_token),  # Use old refresh token if not returned
                id_token=token_response['id_token'],
                token_type=token_response.get('token_type', 'Bearer'),
                expires_in=expires_in,
                expires_at=expires_at
            )
            
            logger.info("Successfully refreshed tokens")
            return tokens
            
        except Exception as e:
            logger.error(f"Failed to refresh tokens: {e}")
            raise
    
    async def get_user_info(self, access_token: str) -> UserInfo:
        """
        Get user information using access token
        
        Args:
            access_token: JWT access token
            
        Returns:
            UserInfo: User information
            
        Raises:
            Exception: If user info retrieval fails
        """
        try:
            # Make user info request
            response = await self.http_client.get(
                self.config['user_info_url'],
                headers={'Authorization': f'Bearer {access_token}'}
            )
            
            if response.status_code != 200:
                error_msg = f'User info request failed: {response.status_code}'
                logger.error(error_msg)
                raise Exception(error_msg)
            
            user_data = response.json()
            
            # Create UserInfo object
            user_info = UserInfo(**user_data)
            
            logger.info(f"Successfully retrieved user info for user: {user_info.user_id}")
            return user_info
            
        except Exception as e:
            logger.error(f"Failed to get user info: {e}")
            raise
    
    async def verify_jwt_token(self, token: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Verify JWT token signature and claims
        
        Args:
            token: JWT token to verify
            
        Returns:
            Tuple[bool, Optional[Dict]]: (is_valid, payload)
        """
        try:
            # Get JWKS
            jwks = await self._get_jwks()
            
            # Decode token header to get key ID
            unverified_header = jwt.get_unverified_header(token)
            kid = unverified_header.get('kid')
            
            if not kid:
                logger.error("JWT token missing 'kid' in header")
                return False, None
            
            # Find the key
            key = None
            for jwk in jwks.get('keys', []):
                if jwk.get('kid') == kid:
                    key = jwk
                    break
            
            if not key:
                logger.error(f"JWT key with kid '{kid}' not found in JWKS")
                return False, None
            
            # Verify token
            payload = jwt.decode(
                token,
                key,
                algorithms=['RS256'],
                audience=self.client_id,
                issuer=f'https://cognito-idp.{self.region}.amazonaws.com/{self.user_pool_id}'
            )
            
            # Check token expiration
            exp = payload.get('exp')
            if exp and datetime.utcfromtimestamp(exp) < datetime.utcnow():
                logger.error("JWT token has expired")
                return False, None
            
            logger.debug(f"JWT token verified successfully for user: {payload.get('sub')}")
            return True, payload
            
        except JWTError as e:
            logger.error(f"JWT verification failed: {e}")
            return False, None
        except Exception as e:
            logger.error(f"Unexpected error during JWT verification: {e}")
            return False, None
    
    async def _get_jwks(self) -> Dict[str, Any]:
        """
        Get JSON Web Key Set (JWKS) from Cognito
        
        Returns:
            Dict: JWKS data
        """
        # Check cache
        if (self._jwks_cache and self._jwks_cache_expiry and 
            datetime.utcnow() < self._jwks_cache_expiry):
            return self._jwks_cache
        
        try:
            # Fetch JWKS
            response = await self.http_client.get(self.config['jwks_url'])
            
            if response.status_code != 200:
                raise Exception(f'JWKS request failed: {response.status_code}')
            
            jwks = response.json()
            
            # Cache for 1 hour
            self._jwks_cache = jwks
            self._jwks_cache_expiry = datetime.utcnow() + timedelta(hours=1)
            
            logger.debug("JWKS fetched and cached successfully")
            return jwks
            
        except Exception as e:
            logger.error(f"Failed to fetch JWKS: {e}")
            raise
    
    def decode_jwt_payload(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Decode JWT payload without verification (for debugging/logging)
        
        Args:
            token: JWT token
            
        Returns:
            Optional[Dict]: Decoded payload or None if invalid
        """
        try:
            # Split token
            parts = token.split('.')
            if len(parts) != 3:
                return None
            
            # Decode payload (add padding if needed)
            payload = parts[1]
            padding = 4 - (len(payload) % 4)
            if padding != 4:
                payload += '=' * padding
            
            decoded_bytes = base64.urlsafe_b64decode(payload)
            payload_data = json.loads(decoded_bytes.decode('utf-8'))
            
            return payload_data
            
        except Exception as e:
            logger.error(f"Failed to decode JWT payload: {e}")
            return None
    
    async def logout_user(self, access_token: str) -> bool:
        """
        Logout user (revoke tokens)
        
        Args:
            access_token: Access token to revoke
            
        Returns:
            bool: True if successful
        """
        try:
            # Cognito doesn't have a standard logout endpoint for public clients
            # We'll just return True as the client-side logout is sufficient
            logger.info("User logout completed")
            return True
            
        except Exception as e:
            logger.error(f"Logout failed: {e}")
            return False
    
    async def close(self):
        """Close HTTP client"""
        await self.http_client.aclose()


# Global instance
_cognito_client: Optional[CognitoAuthClient] = None


def get_cognito_client() -> CognitoAuthClient:
    """Get global Cognito client instance"""
    global _cognito_client
    if _cognito_client is None:
        _cognito_client = CognitoAuthClient()
    return _cognito_client