"""
Chat service for managing chat history and sessions
Simplified in-memory implementation for development
"""
import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime

from ..utils.logger import setup_logger
from ..models.chat import (
    ChatMessage, ChatHistory, ChatSession, MessageRole, MessageStatus
)

logger = setup_logger(__name__)


class ChatService:
    """Simplified service for managing chat history and sessions"""
    
    def __init__(self):
        """Initialize chat service with in-memory storage"""
        self._chat_histories: Dict[str, ChatHistory] = {}
        self._chat_sessions: Dict[str, ChatSession] = {}
        
    def get_or_create_session(self, user_id: str, session_id: Optional[str] = None) -> ChatSession:
        """
        Get existing session or create new one
        
        Args:
            user_id: User ID
            session_id: Optional session ID
            
        Returns:
            ChatSession: Existing or new session
        """
        # If session_id provided, try to get it
        if session_id and session_id in self._chat_sessions:
            session = self._chat_sessions[session_id]
            if session.user_id == user_id:
                session.update_activity()
                return session
        
        # Create new session
        new_session_id = session_id or str(uuid.uuid4())
        session = ChatSession(
            session_id=new_session_id,
            user_id=user_id
        )
        
        self._chat_sessions[new_session_id] = session
        
        # Initialize chat history
        history_key = f"{user_id}:{new_session_id}"
        self._chat_histories[history_key] = ChatHistory(
            user_id=user_id,
            session_id=new_session_id
        )
        
        logger.info(f"Created chat session {new_session_id} for user {user_id}")
        return session
    
    def add_message(
        self, 
        user_id: str, 
        content: str, 
        role: MessageRole,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ChatMessage:
        """
        Add a message to chat history
        
        Args:
            user_id: User ID
            content: Message content
            role: Message role
            session_id: Optional session ID
            metadata: Optional metadata
            
        Returns:
            ChatMessage: Added message
        """
        # Get or create session
        session = self.get_or_create_session(user_id, session_id)
        
        # Create message
        message = ChatMessage(
            id=str(uuid.uuid4()),
            role=role,
            content=content,
            user_id=user_id,
            session_id=session.session_id,
            metadata=metadata
        )
        
        # Add to history
        history_key = f"{user_id}:{session.session_id}"
        history = self._chat_histories[history_key]
        history.add_message(message)
        
        # Update session
        session.message_count += 1
        session.update_activity()
        
        logger.info(f"Added {role} message to session {session.session_id}")
        return message
    
    def get_chat_history(
        self, 
        user_id: str, 
        session_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[ChatMessage]:
        """
        Get chat history for user
        
        Args:
            user_id: User ID
            session_id: Optional session ID
            limit: Maximum number of messages
            offset: Offset for pagination
            
        Returns:
            List[ChatMessage]: Chat messages
        """
        if session_id:
            # Get history for specific session
            history_key = f"{user_id}:{session_id}"
            history = self._chat_histories.get(history_key)
            messages = history.messages if history else []
        else:
            # Get history across all sessions for user
            messages = []
            for key, history in self._chat_histories.items():
                if key.startswith(f"{user_id}:"):
                    messages.extend(history.messages)
            
            # Sort by timestamp
            messages.sort(key=lambda m: m.timestamp)
        
        # Apply pagination
        return messages[offset:offset + limit]
    
    def get_message_count(self, user_id: str, session_id: Optional[str] = None) -> int:
        """
        Get total message count for user
        
        Args:
            user_id: User ID
            session_id: Optional session ID
            
        Returns:
            int: Total message count
        """
        if session_id:
            history_key = f"{user_id}:{session_id}"
            history = self._chat_histories.get(history_key)
            return history.total_count if history else 0
        
        # Count across all sessions
        total = 0
        for key, history in self._chat_histories.items():
            if key.startswith(f"{user_id}:"):
                total += history.total_count
        return total
    
    def update_message_status(self, message_id: str, status: MessageStatus) -> bool:
        """
        Update message status
        
        Args:
            message_id: Message ID
            status: New status
            
        Returns:
            bool: True if updated successfully
        """
        for history in self._chat_histories.values():
            for message in history.messages:
                if message.id == message_id:
                    message.status = status
                    logger.info(f"Updated message {message_id} status to {status}")
                    return True
        
        logger.warning(f"Message {message_id} not found")
        return False


# Global chat service instance
_chat_service: Optional[ChatService] = None


def get_chat_service() -> ChatService:
    """Get global chat service instance"""
    global _chat_service
    if _chat_service is None:
        _chat_service = ChatService()
    return _chat_service