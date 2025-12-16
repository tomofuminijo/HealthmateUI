"""
Streaming API endpoints for real-time chat
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse as FastAPIStreamingResponse
from typing import Optional
import asyncio

from ..auth import require_authentication
from ..models.auth import UserSession
from ..models.chat import StreamingMessageRequest, StreamingEvent
from ..services import get_chat_service, get_streaming_service
from ..healthcoach import get_healthcoach_client
from ..utils.logger import setup_logger

logger = setup_logger(__name__)
router = APIRouter(prefix="/api/streaming", tags=["streaming"])


@router.get("/connect")
async def connect_streaming(
    user_session: UserSession = Depends(require_authentication)
) -> FastAPIStreamingResponse:
    """
    Connect to streaming service for real-time updates
    
    Args:
        user_session: Authenticated user session
        
    Returns:
        FastAPIStreamingResponse: Server-Sent Events stream
    """
    try:
        logger.info(f"Connecting streaming for user {user_session.user_info.user_id}")
        
        # Get streaming service
        streaming_service = get_streaming_service()
        
        # Create streaming connection
        connection = streaming_service.create_connection(user_session.user_info.user_id)
        
        async def generate_stream():
            """Generate the streaming connection"""
            try:
                # Send initial connection event
                connection_event = StreamingEvent(
                    event_type="connected",
                    data={
                        "connection_id": connection.connection_id,
                        "user_id": user_session.user_info.user_id
                    },
                    message="Streaming connection established"
                )
                yield connection_event.to_sse_format()
                
                # Keep connection alive with periodic heartbeat
                while True:
                    try:
                        # Send heartbeat every 30 seconds
                        await asyncio.sleep(30)
                        
                        heartbeat_event = StreamingEvent(
                            event_type="heartbeat",
                            data={
                                "timestamp": asyncio.get_event_loop().time(),
                                "connection_id": connection.connection_id
                            },
                            message="Connection alive"
                        )
                        yield heartbeat_event.to_sse_format()
                        
                    except asyncio.CancelledError:
                        logger.info(f"Streaming connection cancelled for user {user_session.user_info.user_id}")
                        break
                    except Exception as e:
                        logger.error(f"Heartbeat error: {e}")
                        break
                        
            except Exception as e:
                logger.error(f"Streaming connection error: {e}")
                
                # Send error event
                error_event = StreamingEvent(
                    event_type="error",
                    error=f"Connection error: {str(e)}"
                )
                yield error_event.to_sse_format()
                
            finally:
                # Clean up connection
                await streaming_service.remove_connection(connection.connection_id)
                
                # Send disconnection event
                disconnect_event = StreamingEvent(
                    event_type="disconnected",
                    message="Streaming connection closed"
                )
                yield disconnect_event.to_sse_format()
        
        return FastAPIStreamingResponse(
            generate_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Cache-Control",
                "X-Accel-Buffering": "no",  # Disable nginx buffering
                "X-Connection-ID": connection.connection_id
            }
        )
        
    except Exception as e:
        logger.error(f"Streaming connect error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.post("/chat")
async def start_streaming_chat(
    request: StreamingMessageRequest,
    user_session: UserSession = Depends(require_authentication)
) -> FastAPIStreamingResponse:
    """
    Start a streaming chat session with HealthCoachAI
    
    Args:
        request: Streaming message request
        user_session: Authenticated user session
        
    Returns:
        FastAPIStreamingResponse: Server-Sent Events stream
    """
    try:
        logger.info(f"Starting streaming chat for user {user_session.user_info.user_id}")
        
        # Get services
        streaming_service = get_streaming_service()
        chat_service = get_chat_service()
        healthcoach_client = get_healthcoach_client()
        
        # Create streaming connection
        connection = streaming_service.create_connection(user_session.user_info.user_id)
        
        async def generate_stream():
            """Generate the streaming response"""
            try:
                # Send initial connection event
                connection_event = StreamingEvent(
                    event_type="connected",
                    data={
                        "connection_id": connection.connection_id,
                        "user_id": user_session.user_info.user_id
                    },
                    message="Streaming connection established"
                )
                yield connection_event.to_sse_format()
                
                # Process the message and stream response
                user_message = None
                ai_message_content = ""
                
                try:
                    # Use chat_session_id from request, fallback to session_attributes
                    chat_session_id = request.chat_session_id
                    if not chat_session_id and request.session_attributes:
                        chat_session_id = request.session_attributes.get("session_id")
                    
                    logger.info(f"Processing message for user {user_session.user_info.user_id}, chat_session_id: {chat_session_id}, auth_session: {user_session.auth_session_id}")
                    
                    # Add user message to history
                    user_message = chat_service.add_message(
                        user_id=user_session.user_info.user_id,
                        content=request.message,
                        role="user",
                        session_id=chat_session_id,  # This is the chat session ID
                        metadata={
                            "timezone": request.timezone,
                            "language": request.language,
                            "connection_id": connection.connection_id,
                            "auth_session_id": user_session.auth_session_id  # Store auth session for reference
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
                    
                    # Send AI thinking event
                    thinking_event = StreamingEvent(
                        event_type="ai_thinking",
                        message="HealthCoachAI is processing your message..."
                    )
                    yield thinking_event.to_sse_format()
                    
                    # Prepare session attributes for HealthCoachAI
                    # HealthCoachAI expects session_id in sessionState.sessionAttributes.session_id
                    session_attributes = {
                        "session_id": chat_session_id,  # HealthCoachAI expects this key
                        "chat_session_id": chat_session_id,  # Keep for compatibility
                        "user_id": user_session.user_info.user_id,
                        "auth_session_id": user_session.auth_session_id,
                        "timezone": request.timezone,
                        "language": request.language
                    }
                    
                    # Add any additional session attributes from request
                    if request.session_attributes:
                        session_attributes.update(request.session_attributes)
                    
                    logger.info(f"Sending to HealthCoachAI with session_attributes: {session_attributes}")
                    
                    # Stream response from HealthCoachAI
                    async for chunk in healthcoach_client.send_message_streaming(
                        message=request.message,
                        jwt_token=user_session.tokens.access_token,
                        timezone=request.timezone,
                        language=request.language,
                        session_attributes=session_attributes
                    ):
                        if chunk.error:
                            # Send error event
                            error_event = StreamingEvent(
                                event_type="error",
                                error=chunk.error
                            )
                            yield error_event.to_sse_format()
                            break
                            
                        elif chunk.is_complete:
                            # Add complete AI response to history
                            if ai_message_content and user_message:
                                ai_message = chat_service.add_message(
                                    user_id=user_session.user_info.user_id,
                                    content=ai_message_content,
                                    role="assistant",
                                    session_id=user_message.session_id,
                                    metadata={
                                        "timezone": request.timezone,
                                        "language": request.language,
                                        "runtime_id": healthcoach_client.runtime_id,
                                        "connection_id": connection.connection_id
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
                                    event_type="ai_chunk",
                                    data={
                                        "text": chunk.text,
                                        "accumulated_length": len(ai_message_content)
                                    }
                                )
                                logger.debug(f"Sending ai_chunk event: {chunk.text}")
                                yield chunk_event.to_sse_format()
                                
                                # Small delay to prevent overwhelming
                                await asyncio.sleep(0.01)
                
                except Exception as stream_error:
                    logger.error(f"Streaming processing error: {stream_error}")
                    
                    # Send error event
                    error_event = StreamingEvent(
                        event_type="error",
                        error=f"Processing error: {str(stream_error)}"
                    )
                    yield error_event.to_sse_format()
                
                finally:
                    # Send disconnection event
                    disconnect_event = StreamingEvent(
                        event_type="disconnected",
                        message="Streaming session ended"
                    )
                    yield disconnect_event.to_sse_format()
                    
                    # Clean up connection
                    await streaming_service.remove_connection(connection.connection_id)
                    
            except Exception as e:
                logger.error(f"Stream generation error: {e}")
                
                # Send final error event
                final_error_event = StreamingEvent(
                    event_type="error",
                    error=f"Stream error: {str(e)}"
                )
                yield final_error_event.to_sse_format()
                
                # Clean up connection
                await streaming_service.remove_connection(connection.connection_id)
        
        return FastAPIStreamingResponse(
            generate_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Cache-Control",
                "X-Accel-Buffering": "no",  # Disable nginx buffering
                "X-Connection-ID": connection.connection_id
            }
        )
        
    except Exception as e:
        logger.error(f"Streaming chat error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.get("/status")
async def get_streaming_status(
    user_session: UserSession = Depends(require_authentication)
):
    """
    Get streaming service status
    
    Args:
        user_session: Authenticated user session
        
    Returns:
        Streaming service status
    """
    try:
        streaming_service = get_streaming_service()
        
        user_connections = streaming_service.get_user_connections(user_session.user_info.user_id)
        
        return {
            "success": True,
            "user_id": user_session.user_info.user_id,
            "active_connections": len(user_connections),
            "connection_ids": list(user_connections),
            "total_connections": streaming_service.get_connection_count(),
            "total_users": streaming_service.get_user_count()
        }
        
    except Exception as e:
        logger.error(f"Streaming status error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.delete("/connections/{connection_id}")
async def close_streaming_connection(
    connection_id: str,
    user_session: UserSession = Depends(require_authentication)
):
    """
    Close a specific streaming connection
    
    Args:
        connection_id: Connection ID to close
        user_session: Authenticated user session
        
    Returns:
        Success response
    """
    try:
        streaming_service = get_streaming_service()
        
        # Verify the connection belongs to the user
        connection = streaming_service.get_connection(connection_id)
        if not connection or connection.user_id != user_session.user_info.user_id:
            raise HTTPException(
                status_code=404,
                detail="Connection not found or access denied"
            )
        
        # Close the connection
        await streaming_service.remove_connection(connection_id)
        
        return {
            "success": True,
            "message": f"Connection {connection_id} closed successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Close connection error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )