"""
HealthCoachAI client for AgentCore Runtime integration
"""
import asyncio
import json
import subprocess
import tempfile
import os
from typing import AsyncGenerator, Optional, Dict, Any
from datetime import datetime

from ..utils.config import get_config
from ..utils.logger import setup_logger
from .models import (
    ChatRequest, ChatResponse, StreamingChunk, StreamingResponse, 
    AgentCorePayload, ChatMessage, MessageRole
)

logger = setup_logger(__name__)


class HealthCoachClient:
    """HealthCoachAI AgentCore Runtime client"""
    
    def __init__(self):
        """Initialize the client"""
        self.config = get_config()
        self.runtime_id = self.config.HEALTH_COACH_AI_RUNTIME_ID
        self.timeout = 60  # 60 seconds timeout
        
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
                logger.error(f"Using session ID: {session_id}")  # Changed to ERROR for visibility
            else:
                logger.error(f"No session ID found in session_attributes: {session_attributes}")  # Debug info
            
            # Create payload
            payload = AgentCorePayload(
                prompt=message,
                jwt_token=jwt_token,
                timezone=timezone,
                language=language,
                session_id=session_id,
                session_state={
                    "sessionAttributes": session_attributes or {
                        "jwt_token": jwt_token,
                        "timezone": timezone,
                        "language": language
                    }
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
                logger.error(f"Using session ID for streaming: {session_id}")  # Changed to ERROR for visibility
            else:
                logger.error(f"No session ID found in session_attributes: {session_attributes}")  # Debug info
            
            # Create payload
            payload = AgentCorePayload(
                prompt=message,
                jwt_token=jwt_token,
                timezone=timezone,
                language=language,
                session_id=session_id,
                session_state={
                    "sessionAttributes": session_attributes or {
                        "jwt_token": jwt_token,
                        "timezone": timezone,
                        "language": language
                    }
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
        Call AgentCore Runtime API and get complete response
        
        Args:
            payload: JSON payload for AgentCore
            
        Returns:
            Dict with success status and response/error
        """
        try:
            import boto3
            import uuid
            from botocore.exceptions import ClientError
            
            logger.debug(f"AgentCore API payload: {json.dumps(payload)}")
            
            # Create Bedrock AgentCore client
            client = boto3.client('bedrock-agentcore', region_name=self.config.AWS_REGION)
            
            # Prepare the payload as JSON bytes
            json_payload = json.dumps(payload).encode('utf-8')
            
            # Use provided session ID or generate new one (must be at least 33 characters)
            session_id = payload.get('sessionId')
            if not session_id:
                session_id = f'healthmate-session-{uuid.uuid4().hex}'
                logger.error(f"Generated new session ID: {session_id}")  # Changed to ERROR for visibility
            else:
                logger.error(f"Using existing session ID: {session_id}")  # Changed to ERROR for visibility
            
            try:
                # Call the AgentCore Runtime API
                response = client.invoke_agent_runtime(
                    agentRuntimeArn=f"arn:aws:bedrock-agentcore:{self.config.AWS_REGION}:{self.config.AWS_ACCOUNT_ID}:runtime/{self.runtime_id}",
                    runtimeSessionId=session_id,
                    payload=json_payload
                )
                
                # Process the response
                response_text = ""
                
                # Handle streaming response similar to manual_test_deployed_agent.py
                stream = response["response"]
                buffer = ""
                
                # Read chunks from stream
                while True:
                    try:
                        chunk = stream.read(1024)  # Read 1KB at a time
                        if not chunk:
                            break
                        
                        # Add to buffer
                        buffer += chunk.decode('utf-8', errors='ignore')
                        
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
                                                response_text += text_chunk
                                except json.JSONDecodeError:
                                    continue
                    except Exception:
                        # Stream ended or error
                        break
                
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
                    
            except ClientError as e:
                error_code = e.response['Error']['Code']
                error_message = e.response['Error']['Message']
                logger.error(f"AgentCore API error: {error_code} - {error_message}")
                return {
                    "success": False,
                    "error": f"AgentCore API error: {error_code} - {error_message}"
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
        Call AgentCore Runtime API with streaming support
        
        Args:
            payload: JSON payload for AgentCore
            
        Yields:
            StreamingChunk objects with text chunks
        """
        try:
            import boto3
            import uuid
            from botocore.exceptions import ClientError
            
            logger.debug(f"AgentCore API streaming payload: {json.dumps(payload)}")
            
            # Create Bedrock AgentCore client
            client = boto3.client('bedrock-agentcore', region_name=self.config.AWS_REGION)
            
            # Prepare the payload as JSON bytes
            json_payload = json.dumps(payload).encode('utf-8')
            
            # Use provided session ID or generate new one (must be at least 33 characters)
            session_id = payload.get('sessionId')
            if not session_id:
                session_id = f'healthmate-session-{uuid.uuid4().hex}'
                logger.error(f"Generated new session ID for streaming: {session_id}")  # Changed to ERROR for visibility
            else:
                logger.error(f"Using existing session ID for streaming: {session_id}")  # Changed to ERROR for visibility
            
            try:
                # Call the AgentCore Runtime API with streaming
                response = client.invoke_agent_runtime(
                    agentRuntimeArn=f"arn:aws:bedrock-agentcore:{self.config.AWS_REGION}:{self.config.AWS_ACCOUNT_ID}:runtime/{self.runtime_id}",
                    runtimeSessionId=session_id,
                    payload=json_payload
                )
                
                # Process streaming response similar to manual_test_deployed_agent.py
                stream = response["response"]
                buffer = ""
                
                # Read chunks from stream
                while True:
                    try:
                        chunk = stream.read(1024)  # Read 1KB at a time
                        if not chunk:
                            break
                        
                        # Add to buffer
                        buffer += chunk.decode('utf-8', errors='ignore')
                        
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
                    except Exception:
                        # Stream ended or error
                        break
                
                # Send completion chunk
                yield StreamingChunk(
                    text="",
                    is_complete=True
                )
                
            except ClientError as e:
                error_code = e.response['Error']['Code']
                error_message = e.response['Error']['Message']
                logger.error(f"AgentCore API streaming error: {error_code} - {error_message}")
                yield StreamingChunk(
                    text="",
                    is_complete=True,
                    error=f"AgentCore API error: {error_code} - {error_message}"
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