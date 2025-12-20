"""
HealthCoachAI integration module for HealthmateUI

This module provides:
- AgentCore Runtime integration
- JWT token passing for user identification
- Streaming support for real-time responses
- Error handling and timeout management
"""

from .client import HealthCoachClient, get_healthcoach_client
from ..models.chat import ChatMessage, ChatResponse, StreamingResponse
from .routes import router as healthcoach_router

__all__ = [
    'HealthCoachClient',
    'get_healthcoach_client', 
    'ChatMessage',
    'ChatResponse',
    'StreamingResponse',
    'healthcoach_router'
]