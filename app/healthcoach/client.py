"""
HealthCoachAI client for AgentCore Runtime integration with JWT authentication
"""
import asyncio
import json
import subprocess
import tempfile
import os
import urllib.parse
import httpx
from typing import AsyncGenerator, Optional, Dict, Any
from datetime import datetime

from ..utils.config import get_config
from ..utils.logger import setup_logger
from ..models.chat import (
    ChatRequest, ChatResponse, StreamingChunk, StreamingResponse, 
    AgentCorePayload, ChatMessage, MessageRole
)

logger = setup_logger(__name__)


class HealthCoachClient:
    """HealthCoachAI AgentCore Runtime client with JWT authentication"""
    
    def __init__(self):
        """Initialize the client"""
        self.config = get_config()
        self.runtime_id = self.config.HEALTH_COACH_AI_RUNTIME_ID
        self.timeout = 60  # 60 seconds timeout
        
        # Build AgentCore Runtime endpoint URL
        # Use the correct ARN format: runtime (not agent)
        self.agent_arn = f"arn:aws:bedrock-agentcore:{self.config.AWS_REGION}:{self.config.AWS_ACCOUNT_ID}:runtime/{self.runtime_id}"
        escaped_agent_arn = urllib.parse.quote(self.agent_arn, safe='')
        self.endpoint_url = f"https://bedrock-agentcore.{self.config.AWS_REGION}.amazonaws.com/runtimes/{escaped_agent_arn}/invocations?qualifier=DEFAULT"
        
        logger.info(f"HealthCoachAI client initialized with endpoint: {self.endpoint_url}")
    
    def _extract_user_id_from_jwt(self, jwt_token: str) -> Optional[str]:
        """
        Extract user ID (sub) from JWT token
        
        Args:
            jwt_token: JWT access token
            
        Returns:
            Optional[str]: User ID (sub field) or None if extraction fails
        """
        try:
            from ..auth.cognito import get_cognito_client
            
            # Use Cognito client to decode JWT payload
            cognito_client = get_cognito_client()
            payload = cognito_client.decode_jwt_payload(jwt_token)
            
            if payload and 'sub' in payload:
                user_id = payload['sub']
                logger.debug(f"Successfully extracted user ID from JWT: {user_id}")
                return user_id
            else:
                logger.warning("JWT token payload missing 'sub' field")
                return None
                
        except Exception as e:
            logger.error(f"Failed to extract user ID from JWT token: {e}")
            return None
        
    async def send_message(
        self, 
        message: str, 
        jwt_token: str,
        timezone: str = "Asia/Tokyo",
        language: str = "ja",
        session_attributes: Optional[Dict[str, Any]] = None
    ) -> ChatResponse:
        """
        Send a message to HealthCoachAI and get complete response
        
        Args:
            message: User message
            jwt_token: JWT access token for authentication
            timezone: User timezone
            language: User language preference
            session_attributes: Additional session attributes
            
        Returns:
            ChatResponse with complete message
        """
        try:
            logger.info(f"Sending message to HealthCoachAI: {message[:100]}...")
            
            # Extract session ID from session_attributes
            session_id = None
            if session_attributes and "session_id" in session_attributes:
                session_id = session_attributes["session_id"]
                logger.debug(f"Using session ID: {session_id}")
            else:
                logger.debug(f"No session ID found in session_attributes: {session_attributes}")
            
            # Create optimized payload (avoid duplication - AgentCorePayload.to_json_payload() handles the structure)
            payload = AgentCorePayload(
                prompt=message,
                jwt_token=jwt_token,
                timezone=timezone,
                language=language,
                session_id=session_id,
                session_state={
                    "sessionAttributes": session_attributes or {}
                }
            )
            
            # Call AgentCore API
            result = await self._call_agentcore_api(payload.to_json_payload())
            
            if result["success"]:
                return ChatResponse(
                    success=True,
                    message=result["response"],
                    metadata={
                        "timezone": timezone,
                        "language": language,
                        "runtime_id": self.runtime_id
                    }
                )
            else:
                logger.error(f"HealthCoachAI error: {result['error']}")
                return ChatResponse(
                    success=False,
                    error=result["error"]
                )
                
        except Exception as e:
            logger.error(f"HealthCoachAI client error: {e}")
            return ChatResponse(
                success=False,
                error=f"Internal error: {str(e)}"
            )
    
    async def send_message_streaming(
        self,
        message: str,
        jwt_token: str,
        timezone: str = "Asia/Tokyo", 
        language: str = "ja",
        session_attributes: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[StreamingChunk, None]:
        """
        Send a message to HealthCoachAI and get streaming response
        
        Args:
            message: User message
            jwt_token: JWT access token for authentication
            timezone: User timezone
            language: User language preference
            session_attributes: Additional session attributes
            
        Yields:
            StreamingChunk objects with text chunks
        """
        try:
            logger.info(f"Sending streaming message to HealthCoachAI: {message[:100]}...")
            
            # Extract session ID from session_attributes
            session_id = None
            if session_attributes and "session_id" in session_attributes:
                session_id = session_attributes["session_id"]
                logger.debug(f"Using session ID for streaming: {session_id}")
            else:
                logger.debug(f"No session ID found in session_attributes: {session_attributes}")
            
            # Create optimized payload (avoid duplication - AgentCorePayload.to_json_payload() handles the structure)
            payload = AgentCorePayload(
                prompt=message,
                jwt_token=jwt_token,
                timezone=timezone,
                language=language,
                session_id=session_id,
                session_state={
                    "sessionAttributes": session_attributes or {}
                }
            )
            
            # Call AgentCore API with streaming
            async for chunk in self._call_agentcore_api_streaming(payload.to_json_payload()):
                yield chunk
                
        except Exception as e:
            logger.error(f"HealthCoachAI streaming error: {e}")
            yield StreamingChunk(
                text="",
                is_complete=True,
                error=f"Internal error: {str(e)}"
            )
    
    async def _call_agentcore_api(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call AgentCore Runtime API with JWT authentication and get complete response
        
        Args:
            payload: JSON payload for AgentCore
            
        Returns:
            Dict with success status and response/error
        """
        try:
            logger.debug(f"AgentCore API payload: {json.dumps(payload)}")
            
            # Extract JWT token and session ID from payload
            session_attrs = payload.get('sessionState', {}).get('sessionAttributes', {})
            jwt_token = session_attrs.get('jwt_token')
            session_id = session_attrs.get('session_id')
            
            if not jwt_token:
                return {
                    "success": False,
                    "error": "JWT token is required for authentication"
                }
            
            # Generate session ID if not provided (must be at least 33 characters)
            if not session_id:
                import uuid
                session_id = f'healthmate-session-{uuid.uuid4().hex}'
                logger.debug(f"Generated new session ID: {session_id}")
            else:
                logger.debug(f"Using existing session ID: {session_id}")
            
            # Prepare headers for JWT authentication
            headers = {
                "Authorization": f"Bearer {jwt_token}",
                "Content-Type": "application/json",
                "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": session_id
            }
            
            # Make HTTPS request to AgentCore Runtime
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.endpoint_url,
                    headers=headers,
                    json=payload
                )
                
                # Handle HTTP errors
                if response.status_code == 401:
                    return {
                        "success": False,
                        "error": "JWT認証エラー: アクセストークンが無効です"
                    }
                elif response.status_code == 403:
                    return {
                        "success": False,
                        "error": "認可エラー: 必要な権限がありません"
                    }
                elif response.status_code != 200:
                    return {
                        "success": False,
                        "error": f"AgentCore Runtime エラー: HTTP {response.status_code}"
                    }
                
                # Process streaming response
                response_text = ""
                response_content = response.text
                
                # Parse Server-Sent Events format
                lines = response_content.split('\n')
                for line in lines:
                    if line.startswith('data: '):
                        try:
                            data_json = line[6:]  # Remove "data: " prefix
                            if data_json.strip():
                                event_data = json.loads(data_json)
                                
                                # Extract text from contentBlockDelta events
                                if 'event' in event_data and 'contentBlockDelta' in event_data['event']:
                                    delta = event_data['event']['contentBlockDelta'].get('delta', {})
                                    if 'text' in delta:
                                        response_text += delta['text']
                        except json.JSONDecodeError:
                            continue
                
                if response_text:
                    return {
                        "success": True,
                        "response": response_text
                    }
                else:
                    return {
                        "success": False,
                        "error": "No response received from HealthCoachAI"
                    }
                    
        except httpx.TimeoutException:
            logger.error("AgentCore API request timeout")
            return {
                "success": False,
                "error": "Request timeout - HealthCoachAI did not respond in time"
            }
        except httpx.RequestError as e:
            logger.error(f"AgentCore API request error: {e}")
            return {
                "success": False,
                "error": f"Network error: {str(e)}"
            }
        except Exception as e:
            logger.error(f"AgentCore API call error: {e}")
            return {
                "success": False,
                "error": f"API execution error: {str(e)}"
            }
    
    async def _call_agentcore_api_streaming(
        self, 
        payload: Dict[str, Any]
    ) -> AsyncGenerator[StreamingChunk, None]:
        """
        Call AgentCore Runtime API with JWT authentication and streaming support
        
        Args:
            payload: JSON payload for AgentCore
            
        Yields:
            StreamingChunk objects with text chunks
        """
        try:
            logger.debug(f"AgentCore API streaming payload: {json.dumps(payload)}")
            
            # Extract JWT token and session ID from payload
            session_attrs = payload.get('sessionState', {}).get('sessionAttributes', {})
            jwt_token = session_attrs.get('jwt_token')
            session_id = session_attrs.get('session_id')
            
            if not jwt_token:
                yield StreamingChunk(
                    text="",
                    is_complete=True,
                    error="JWT token is required for authentication"
                )
                return
            
            # Generate session ID if not provided (must be at least 33 characters)
            if not session_id:
                import uuid
                session_id = f'healthmate-session-{uuid.uuid4().hex}'
                logger.debug(f"Generated new session ID for streaming: {session_id}")
            else:
                logger.debug(f"Using existing session ID for streaming: {session_id}")
            
            # Prepare headers for JWT authentication
            headers = {
                "Authorization": f"Bearer {jwt_token}",
                "Content-Type": "application/json",
                "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": session_id
            }
            
            # Make streaming HTTPS request to AgentCore Runtime
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream(
                    "POST",
                    self.endpoint_url,
                    headers=headers,
                    json=payload
                ) as response:
                    
                    # Handle HTTP errors
                    if response.status_code == 401:
                        yield StreamingChunk(
                            text="",
                            is_complete=True,
                            error="JWT認証エラー: アクセストークンが無効です"
                        )
                        return
                    elif response.status_code == 403:
                        yield StreamingChunk(
                            text="",
                            is_complete=True,
                            error="認可エラー: 必要な権限がありません"
                        )
                        return
                    elif response.status_code != 200:
                        yield StreamingChunk(
                            text="",
                            is_complete=True,
                            error=f"AgentCore Runtime エラー: HTTP {response.status_code}"
                        )
                        return
                    
                    # Process streaming response
                    buffer = ""
                    async for chunk in response.aiter_text():
                        buffer += chunk
                        
                        # Process complete lines
                        while '\n' in buffer:
                            line, buffer = buffer.split('\n', 1)
                            
                            if line.startswith('data: '):
                                try:
                                    data_json = line[6:]  # Remove "data: " prefix
                                    if data_json.strip():
                                        event_data = json.loads(data_json)
                                        
                                        # Extract text from contentBlockDelta events
                                        if 'event' in event_data and 'contentBlockDelta' in event_data['event']:
                                            delta = event_data['event']['contentBlockDelta'].get('delta', {})
                                            if 'text' in delta:
                                                text_chunk = delta['text']
                                                logger.debug(f"Streaming text chunk: {text_chunk}")
                                                yield StreamingChunk(
                                                    text=text_chunk,
                                                    is_complete=False
                                                )
                                        else:
                                            # Log other event types for debugging
                                            logger.debug(f"Streaming event: {event_data}")
                                except json.JSONDecodeError:
                                    continue
                    
                    # Send completion chunk
                    yield StreamingChunk(
                        text="",
                        is_complete=True
                    )
                    
        except httpx.TimeoutException:
            logger.error("AgentCore API streaming request timeout")
            yield StreamingChunk(
                text="",
                is_complete=True,
                error="Request timeout - HealthCoachAI did not respond in time"
            )
        except httpx.RequestError as e:
            logger.error(f"AgentCore API streaming request error: {e}")
            yield StreamingChunk(
                text="",
                is_complete=True,
                error=f"Network error: {str(e)}"
            )
        except Exception as e:
            logger.error(f"AgentCore API streaming error: {e}")
            yield StreamingChunk(
                text="",
                is_complete=True,
                error=f"API execution error: {str(e)}"
            )


# Global client instance
_healthcoach_client: Optional[HealthCoachClient] = None


def get_healthcoach_client() -> HealthCoachClient:
    """Get global HealthCoachAI client instance"""
    global _healthcoach_client
    if _healthcoach_client is None:
        _healthcoach_client = HealthCoachClient()
    return _healthcoach_client