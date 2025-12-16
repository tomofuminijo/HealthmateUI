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
        """Convert to JSON payload for AgentCore CLI (optimized to avoid duplication)"""
        # Minimal payload structure - only essential information
        payload = {
            "prompt": self.prompt
        }
        
        # Session state with only required attributes for HealthCoachAI
        session_attributes = {
            "session_id": self.session_id,  # Required by HealthCoachAI agent for session continuity
            "jwt_token": self.jwt_token,    # Required for authentication and user ID extraction
            "timezone": self.timezone,      # Required for time-aware responses
            "language": self.language       # Required for language preference
        }
        
        # Filter out attributes that HealthCoachAI doesn't need
        excluded_attributes = {
            "user_id",          # Extracted from JWT token by HealthCoachAI
            "auth_session_id",  # Not used by HealthCoachAI
            "chat_session_id"   # Redundant with session_id
        }
        
        # Add any additional session attributes from existing session state (filtered)
        if self.session_state and "sessionAttributes" in self.session_state:
            additional_attrs = self.session_state["sessionAttributes"]
            for key, value in additional_attrs.items():
                # Only add attributes that are not already included and not excluded
                if key not in session_attributes and key not in excluded_attributes:
                    session_attributes[key] = value
        
        payload["sessionState"] = {
            "sessionAttributes": session_attributes
        }
        
        return payload