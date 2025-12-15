"""
HealthCoachAI API routes
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse as FastAPIStreamingResponse
from typing import Dict, Any
import json
import asyncio

from ..auth import require_authentication, get_current_user
from ..models.auth import UserSession
from ..utils.logger import setup_logger
from .client import get_healthcoach_client
from .models import ChatRequest, ChatResponse, StreamingChunk

logger = setup_logger(__name__)
router = APIRouter(prefix="/api/healthcoach", tags=["healthcoach"])


@router.post("/chat", response_model=ChatResponse)
async def send_chat_message(
    request: ChatRequest,
    user_session: UserSession = Depends(require_authentication)
) -> ChatResponse:
    """
    Send a chat message to HealthCoachAI and get complete response
    
    Args:
        request: Chat request with message and preferences
        current_user: Authenticated user
        
    Returns:
        ChatResponse with AI response
    """
    try:
        logger.info(f"Chat request from user {user_session.user_info.user_id}: {request.message[:100]}...")
        
        # Get HealthCoachAI client
        client = get_healthcoach_client()
        
        # Send message to HealthCoachAI
        response = await client.send_message(
            message=request.message,
            jwt_token=user_session.tokens.access_token,
            timezone=request.timezone,
            language=request.language,
            session_attributes=request.session_attributes
        )
        
        logger.info(f"HealthCoachAI response success: {response.success}")
        return response
        
    except Exception as e:
        logger.error(f"Chat endpoint error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.post("/chat/stream")
async def send_chat_message_streaming(
    request: ChatRequest,
    user_session: UserSession = Depends(require_authentication)
) -> FastAPIStreamingResponse:
    """
    Send a chat message to HealthCoachAI and get streaming response
    
    Args:
        request: Chat request with message and preferences
        current_user: Authenticated user
        
    Returns:
        Streaming response with Server-Sent Events
    """
    try:
        logger.info(f"Streaming chat request from user {user_session.user_info.user_id}: {request.message[:100]}...")
        
        # Get HealthCoachAI client
        client = get_healthcoach_client()
        
        async def generate_sse_stream():
            """Generate Server-Sent Events stream"""
            try:
                # Send initial event
                yield f"data: {json.dumps({'type': 'start', 'message': 'Starting HealthCoachAI response...'})}\n\n"
                
                # Stream response from HealthCoachAI
                async for chunk in client.send_message_streaming(
                    message=request.message,
                    jwt_token=user_session.tokens.access_token,
                    timezone=request.timezone,
                    language=request.language,
                    session_attributes=request.session_attributes
                ):
                    if chunk.error:
                        # Send error event
                        yield f"data: {json.dumps({'type': 'error', 'error': chunk.error})}\n\n"
                        break
                    elif chunk.is_complete:
                        # Send completion event
                        yield f"data: {json.dumps({'type': 'complete'})}\n\n"
                        break
                    else:
                        # Send text chunk
                        yield f"data: {json.dumps({'type': 'chunk', 'text': chunk.text})}\n\n"
                        
                        # Small delay to prevent overwhelming the client
                        await asyncio.sleep(0.01)
                
            except Exception as e:
                logger.error(f"SSE stream error: {e}")
                yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
        
        return FastAPIStreamingResponse(
            generate_sse_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Cache-Control"
            }
        )
        
    except Exception as e:
        logger.error(f"Streaming chat endpoint error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.get("/status")
async def healthcoach_status(
    user_session: UserSession = Depends(require_authentication)
) -> Dict[str, Any]:
    """
    Get HealthCoachAI service status
    
    Args:
        current_user: Authenticated user
        
    Returns:
        Status information
    """
    try:
        client = get_healthcoach_client()
        
        return {
            "status": "operational",
            "runtime_id": client.runtime_id,
            "user_authenticated": True,
            "user_id": user_session.user_info.user_id,
            "timestamp": "2024-12-15T00:00:00Z"  # Current timestamp would be added
        }
        
    except Exception as e:
        logger.error(f"Status endpoint error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )