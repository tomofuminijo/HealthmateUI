"""
Chat related data models
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
import html
import re


class MessageRole(str, Enum):
    """Message role enumeration"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class MessageStatus(str, Enum):
    """Message status enumeration"""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    ERROR = "error"


class ChatMessage(BaseModel):
    """Chat message model"""
    id: Optional[str] = None
    role: MessageRole
    content: str = Field(..., min_length=1, max_length=4000)
    timestamp: datetime = Field(default_factory=datetime.now)
    status: MessageStatus = MessageStatus.SENT
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    @validator('content')
    def sanitize_content(cls, v):
        """Sanitize message content"""
        if not v or not v.strip():
            raise ValueError("Message content cannot be empty")
        
        # HTML escape to prevent XSS
        sanitized = html.escape(v.strip())
        
        # Remove excessive whitespace but preserve newlines
        # Replace multiple spaces/tabs with single space, but keep newlines
        sanitized = re.sub(r'[ \t]+', ' ', sanitized)  # Only spaces and tabs
        sanitized = re.sub(r'\n[ \t]+', '\n', sanitized)  # Remove leading spaces after newlines
        sanitized = re.sub(r'[ \t]+\n', '\n', sanitized)  # Remove trailing spaces before newlines
        
        return sanitized
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ChatHistory(BaseModel):
    """Chat history model"""
    messages: List[ChatMessage] = Field(default_factory=list)
    total_count: int = 0
    user_id: str
    session_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    def add_message(self, message: ChatMessage):
        """Add a message to the history"""
        self.messages.append(message)
        self.total_count = len(self.messages)
        self.updated_at = datetime.now()
    
    def get_recent_messages(self, limit: int = 50) -> List[ChatMessage]:
        """Get recent messages with limit"""
        return self.messages[-limit:] if limit > 0 else self.messages
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class SendMessageRequest(BaseModel):
    """Send message request model"""
    message: str = Field(..., min_length=1, max_length=4000)
    timezone: str = Field(default="Asia/Tokyo")
    language: str = Field(default="ja")
    session_attributes: Optional[Dict[str, Any]] = None
    
    @validator('message')
    def validate_message(cls, v):
        """Validate message content"""
        if not v or not v.strip():
            raise ValueError("Message cannot be empty")
        
        # Check for potentially harmful content
        harmful_patterns = [
            r'<script[^>]*>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
        ]
        
        for pattern in harmful_patterns:
            if re.search(pattern, v, re.IGNORECASE):
                raise ValueError("Message contains potentially harmful content")
        
        return v.strip()


class SendMessageResponse(BaseModel):
    """Send message response model"""
    success: bool
    message_id: Optional[str] = None
    user_message: Optional[ChatMessage] = None
    ai_response: Optional[ChatMessage] = None
    error: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class GetHistoryRequest(BaseModel):
    """Get chat history request model"""
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    since: Optional[datetime] = None


class GetHistoryResponse(BaseModel):
    """Get chat history response model"""
    success: bool
    messages: List[ChatMessage] = Field(default_factory=list)
    total_count: int = 0
    has_more: bool = False
    error: Optional[str] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class StreamingMessageRequest(BaseModel):
    """Streaming message request model"""
    message: str = Field(..., min_length=1, max_length=4000)
    timezone: str = Field(default="Asia/Tokyo")
    language: str = Field(default="ja")
    chat_session_id: Optional[str] = Field(None, description="Chat conversation session ID")
    session_attributes: Optional[Dict[str, Any]] = None
    
    @validator('message')
    def validate_message(cls, v):
        """Validate message content"""
        if not v or not v.strip():
            raise ValueError("Message cannot be empty")
        
        # Check for potentially harmful content
        harmful_patterns = [
            r'<script[^>]*>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
        ]
        
        for pattern in harmful_patterns:
            if re.search(pattern, v, re.IGNORECASE):
                raise ValueError("Message contains potentially harmful content")
        
        return v.strip()


class StreamingEvent(BaseModel):
    """Server-Sent Event model"""
    event_type: str = Field(..., description="Event type (start, chunk, complete, error)")
    data: Optional[Dict[str, Any]] = None
    message: Optional[str] = None
    error: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    
    def to_sse_format(self) -> str:
        """Convert to Server-Sent Events format"""
        import json
        
        event_data = {
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat()
        }
        
        if self.data:
            event_data.update(self.data)
        if self.message:
            event_data["message"] = self.message
        if self.error:
            event_data["error"] = self.error
        
        return f"data: {json.dumps(event_data)}\n\n"
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ChatSession(BaseModel):
    """Chat session model"""
    session_id: str
    user_id: str
    created_at: datetime = Field(default_factory=datetime.now)
    last_activity: datetime = Field(default_factory=datetime.now)
    message_count: int = 0
    is_active: bool = True
    
    def update_activity(self):
        """Update last activity timestamp"""
        self.last_activity = datetime.now()
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }