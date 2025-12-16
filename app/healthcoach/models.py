"""
Data models for HealthCoachAI integration
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum


class MessageRole(str, Enum):
    """Message role enumeration"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ChatMessage(BaseModel):
    """Chat message model"""
    role: MessageRole
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: Optional[Dict[str, Any]] = None


class ChatRequest(BaseModel):
    """Chat request model"""
    message: str = Field(..., min_length=1, max_length=4000)
    timezone: str = Field(default="Asia/Tokyo")
    language: str = Field(default="ja")
    session_attributes: Optional[Dict[str, Any]] = None


class StreamingChunk(BaseModel):
    """Streaming response chunk"""
    text: str
    is_complete: bool = False
    error: Optional[str] = None


class ChatResponse(BaseModel):
    """Chat response model"""
    success: bool
    message: Optional[str] = None
    error: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: Optional[Dict[str, Any]] = None


class StreamingResponse(BaseModel):
    """Streaming response model"""
    success: bool
    chunks: List[StreamingChunk] = Field(default_factory=list)
    complete_message: Optional[str] = None
    error: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class AgentCorePayload(BaseModel):
    """AgentCore Runtime payload model"""
    prompt: str
    jwt_token: str
    timezone: str = "Asia/Tokyo"
    language: str = "ja"
    session_id: Optional[str] = None
    session_state: Optional[Dict[str, Any]] = None
    
    def to_json_payload(self) -> Dict[str, Any]:
        """Convert to JSON payload for AgentCore CLI"""
        payload = {
            "prompt": self.prompt,
            "jwt_token": self.jwt_token,
            "timezone": self.timezone,
            "language": self.language
        }
        
        # Add session ID if provided
        if self.session_id:
            payload["sessionId"] = self.session_id
        
        if self.session_state:
            payload["sessionState"] = self.session_state
        else:
            payload["sessionState"] = {
                "sessionAttributes": {
                    "jwt_token": self.jwt_token,
                    "timezone": self.timezone,
                    "language": self.language
                }
            }
        
        return payload