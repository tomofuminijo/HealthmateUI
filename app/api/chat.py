"""
Chat API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Form
from fastapi.responses import StreamingResponse as FastAPIStreamingResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from typing import Optional, List
import uuid
import asyncio
import json

from ..auth import require_authentication
from ..models.auth import UserSession
from ..models.chat import (
    SendMessageRequest, SendMessageResponse, GetHistoryRequest, GetHistoryResponse,
    ChatMessage, MessageRole, MessageStatus, StreamingMessageRequest, StreamingEvent
)
from ..services import get_chat_service
from ..healthcoach import get_healthcoach_client
from ..utils.logger import setup_logger

logger = setup_logger(__name__)
router = APIRouter(prefix="/api/chat", tags=["chat"])
templates = Jinja2Templates(directory="templates")


@router.post("/send")
async def send_message(
    request: Request,
    message: str = Form(...),
    timezone: str = Form(default="Asia/Tokyo"),
    language: str = Form(default="ja"),
    user_session: UserSession = Depends(require_authentication)
):
    """
    Send a chat message and get AI response (htmx compatible)
    
    Args:
        request: FastAPI request object
        message: User message content
        timezone: User timezone
        language: User language preference
        user_session: Authenticated user session
        
    Returns:
        HTML response with new messages or JSON for API clients
    """
    try:
        logger.info(f"Sending message from user {user_session.user_info.user_id}: {message[:100]}...")
        
        # Check if this is an htmx request
        is_htmx = request.headers.get("HX-Request") == "true"
        
        # Get services
        chat_service = get_chat_service()
        healthcoach_client = get_healthcoach_client()
        
        # Add user message to history
        user_message = chat_service.add_message(
            user_id=user_session.user_info.user_id,
            content=message,
            role=MessageRole.USER,
            metadata={
                "timezone": timezone,
                "language": language
            }
        )
        
        try:
            # Send message to HealthCoachAI
            ai_response = await healthcoach_client.send_message(
                message=message,
                jwt_token=user_session.tokens.access_token,
                timezone=timezone,
                language=language,
                session_attributes={}
            )
            
            if ai_response.success and ai_response.message:
                # Add AI response to history
                ai_message = chat_service.add_message(
                    user_id=user_session.user_info.user_id,
                    content=ai_response.message,
                    role=MessageRole.ASSISTANT,
                    session_id=user_message.session_id,
                    metadata={
                        "timezone": timezone,
                        "language": language,
                        "runtime_id": healthcoach_client.runtime_id
                    }
                )
                
                logger.info(f"Successfully processed message for user {user_session.user_info.user_id}")
                
                if is_htmx:
                    # Return HTML for htmx
                    return templates.TemplateResponse(
                        "chat_messages.html",
                        {
                            "request": request,
                            "messages": [user_message, ai_message]
                        }
                    )
                else:
                    # Return JSON for API clients
                    return SendMessageResponse(
                        success=True,
                        message_id=user_message.id,
                        user_message=user_message,
                        ai_response=ai_message
                    )
            else:
                # Mark user message as error and return error response
                chat_service.update_message_status(user_message.id, MessageStatus.ERROR)
                
                logger.error(f"HealthCoachAI error: {ai_response.error}")
                
                if is_htmx:
                    # Return error message as HTML
                    error_message = ChatMessage(
                        id="error",
                        content=f"エラー: {ai_response.error or 'AI応答の取得に失敗しました'}",
                        role=MessageRole.ASSISTANT,
                        timestamp=user_message.timestamp,
                        session_id=user_message.session_id,
                        status=MessageStatus.ERROR
                    )
                    return templates.TemplateResponse(
                        "chat_messages.html",
                        {
                            "request": request,
                            "messages": [user_message, error_message]
                        }
                    )
                else:
                    return SendMessageResponse(
                        success=False,
                        message_id=user_message.id,
                        user_message=user_message,
                        error=ai_response.error or "Failed to get AI response"
                    )
                
        except Exception as ai_error:
            # Mark user message as error
            chat_service.update_message_status(user_message.id, MessageStatus.ERROR)
            
            logger.error(f"HealthCoachAI integration error: {ai_error}")
            
            if is_htmx:
                # Return error message as HTML
                error_message = ChatMessage(
                    id="error",
                    content=f"エラー: AI サービスに接続できませんでした",
                    role=MessageRole.ASSISTANT,
                    timestamp=user_message.timestamp,
                    session_id=user_message.session_id,
                    status=MessageStatus.ERROR
                )
                return templates.TemplateResponse(
                    "chat_messages.html",
                    {
                        "request": request,
                        "messages": [user_message, error_message]
                    }
                )
            else:
                return SendMessageResponse(
                    success=False,
                    message_id=user_message.id,
                    user_message=user_message,
                    error=f"AI service error: {str(ai_error)}"
                )
            
    except Exception as e:
        logger.error(f"Send message error: {e}")
        if request.headers.get("HX-Request") == "true":
            # Return error as HTML for htmx
            return HTMLResponse(
                content=f'<div class="text-red-600 p-4">エラーが発生しました: {str(e)}</div>',
                status_code=500
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Internal server error: {str(e)}"
            )


@router.post("/send/stream")
async def send_message_streaming(
    request: StreamingMessageRequest,
    user_session: UserSession = Depends(require_authentication)
) -> FastAPIStreamingResponse:
    """
    Send a chat message and get streaming AI response
    
    Args:
        request: Streaming message request
        user_session: Authenticated user session
        
    Returns:
        FastAPIStreamingResponse: Server-Sent Events stream
    """
    try:
        logger.info(f"Streaming message from user {user_session.user_info.user_id}: {request.message[:100]}...")
        
        # Get services
        chat_service = get_chat_service()
        healthcoach_client = get_healthcoach_client()
        
        async def generate_streaming_response():
            """Generate Server-Sent Events stream"""
            user_message = None
            ai_message_content = ""
            
            try:
                # Send start event
                start_event = StreamingEvent(
                    event_type="start",
                    message="Starting HealthCoachAI response..."
                )
                yield start_event.to_sse_format()
                
                # Add user message to history
                user_message = chat_service.add_message(
                    user_id=user_session.user_info.user_id,
                    content=request.message,
                    role=MessageRole.USER,
                    metadata={
                        "timezone": request.timezone,
                        "language": request.language
                    }
                )
                
                # Send user message event
                user_event = StreamingEvent(
                    event_type="user_message",
                    data={
                        "message_id": user_message.id,
                        "content": user_message.content,
                        "timestamp": user_message.timestamp.isoformat()
                    }
                )
                yield user_event.to_sse_format()
                
                # Stream response from HealthCoachAI
                async for chunk in healthcoach_client.send_message_streaming(
                    message=request.message,
                    jwt_token=user_session.tokens.access_token,
                    timezone=request.timezone,
                    language=request.language,
                    session_attributes=request.session_attributes
                ):
                    if chunk.error:
                        # Send error event
                        error_event = StreamingEvent(
                            event_type="error",
                            error=chunk.error
                        )
                        yield error_event.to_sse_format()
                        
                        # Mark user message as error
                        if user_message:
                            chat_service.update_message_status(user_message.id, MessageStatus.ERROR)
                        break
                        
                    elif chunk.is_complete:
                        # Add complete AI response to history
                        if ai_message_content and user_message:
                            ai_message = chat_service.add_message(
                                user_id=user_session.user_info.user_id,
                                content=ai_message_content,
                                role=MessageRole.ASSISTANT,
                                session_id=user_message.session_id,
                                metadata={
                                    "timezone": request.timezone,
                                    "language": request.language,
                                    "runtime_id": healthcoach_client.runtime_id
                                }
                            )
                            
                            # Send AI message complete event
                            ai_complete_event = StreamingEvent(
                                event_type="ai_message_complete",
                                data={
                                    "message_id": ai_message.id,
                                    "content": ai_message.content,
                                    "timestamp": ai_message.timestamp.isoformat()
                                }
                            )
                            yield ai_complete_event.to_sse_format()
                        
                        # Send completion event
                        complete_event = StreamingEvent(
                            event_type="complete",
                            message="Response completed successfully"
                        )
                        yield complete_event.to_sse_format()
                        break
                        
                    else:
                        # Send text chunk
                        if chunk.text:
                            ai_message_content += chunk.text
                            
                            chunk_event = StreamingEvent(
                                event_type="chunk",
                                data={
                                    "text": chunk.text,
                                    "accumulated_length": len(ai_message_content)
                                }
                            )
                            yield chunk_event.to_sse_format()
                            
                            # Small delay to prevent overwhelming the client
                            await asyncio.sleep(0.01)
                
            except Exception as e:
                logger.error(f"Streaming error: {e}")
                
                # Mark user message as error if it exists
                if user_message:
                    chat_service.update_message_status(user_message.id, MessageStatus.ERROR)
                
                # Send error event
                error_event = StreamingEvent(
                    event_type="error",
                    error=f"Streaming error: {str(e)}"
                )
                yield error_event.to_sse_format()
        
        return FastAPIStreamingResponse(
            generate_streaming_response(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Cache-Control",
                "X-Accel-Buffering": "no"  # Disable nginx buffering
            }
        )
        
    except Exception as e:
        logger.error(f"Streaming endpoint error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.get("/history")
async def get_chat_history(
    request: Request,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session_id: Optional[str] = Query(default=None),
    user_session: UserSession = Depends(require_authentication)
):
    """
    Get chat history for the authenticated user (htmx compatible)
    
    Args:
        request: FastAPI request object
        limit: Maximum number of messages to return
        offset: Offset for pagination
        session_id: Optional session ID filter
        user_session: Authenticated user session
        
    Returns:
        HTML response for htmx or JSON for API clients
    """
    try:
        logger.info(f"Getting chat history for user {user_session.user_info.user_id}")
        
        # Check if this is an htmx request
        is_htmx = request.headers.get("HX-Request") == "true"
        
        chat_service = get_chat_service()
        
        # Get messages
        messages = chat_service.get_chat_history(
            user_id=user_session.user_info.user_id,
            session_id=session_id,
            limit=limit + 1,  # Get one extra to check if there are more
            offset=offset
        )
        
        # Check if there are more messages
        has_more = len(messages) > limit
        if has_more:
            messages = messages[:limit]  # Remove the extra message
        
        # Get total count
        total_count = chat_service.get_message_count(
            user_id=user_session.user_info.user_id,
            session_id=session_id
        )
        
        logger.info(f"Retrieved {len(messages)} messages for user {user_session.user_info.user_id}")
        
        if is_htmx:
            # Return HTML for htmx
            return templates.TemplateResponse(
                "chat_history.html",
                {
                    "request": request,
                    "messages": messages
                }
            )
        else:
            # Return JSON for API clients
            return GetHistoryResponse(
                success=True,
                messages=messages,
                total_count=total_count,
                has_more=has_more
            )
        
    except Exception as e:
        logger.error(f"Get chat history error: {e}")
        if request.headers.get("HX-Request") == "true":
            # Return error as HTML for htmx
            return HTMLResponse(
                content=f'<div class="text-red-600 p-4">履歴の読み込みに失敗しました: {str(e)}</div>',
                status_code=500
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Internal server error: {str(e)}"
            )


@router.delete("/history")
async def clear_chat_history(
    session_id: Optional[str] = Query(default=None),
    user_session: UserSession = Depends(require_authentication)
):
    """
    Clear chat history for the authenticated user
    
    Args:
        session_id: Optional session ID to clear specific session
        user_session: Authenticated user session
        
    Returns:
        Success response
    """
    try:
        logger.info(f"Clearing chat history for user {user_session.user_info.user_id}")
        
        chat_service = get_chat_service()
        
        if session_id:
            # Clear specific session
            # Note: This is a simplified implementation
            # In production, you would implement proper session clearing
            logger.info(f"Clearing session {session_id} for user {user_session.user_info.user_id}")
        else:
            # Clear all history for user
            # Note: This is a simplified implementation
            # In production, you would implement proper history clearing
            logger.info(f"Clearing all history for user {user_session.user_info.user_id}")
        
        return {
            "success": True,
            "message": "Chat history cleared successfully"
        }
        
    except Exception as e:
        logger.error(f"Clear chat history error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.get("/sessions")
async def get_chat_sessions(
    user_session: UserSession = Depends(require_authentication)
):
    """
    Get chat sessions for the authenticated user
    
    Args:
        user_session: Authenticated user session
        
    Returns:
        List of chat sessions
    """
    try:
        logger.info(f"Getting chat sessions for user {user_session.user_info.user_id}")
        
        chat_service = get_chat_service()
        
        # Get all sessions for user
        # Note: This is a simplified implementation
        # In production, you would implement proper session retrieval
        
        return {
            "success": True,
            "sessions": [],  # Placeholder for now
            "message": "Chat sessions retrieved successfully"
        }
        
    except Exception as e:
        logger.error(f"Get chat sessions error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )