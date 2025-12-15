"""
Chat service for managing chat history and sessions
"""
import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

from ..utils.logger import setup_logger
from ..models.chat import (
    ChatMessage, ChatHistory, ChatSession, MessageRole, MessageStatus
)

logger = setup_logger(__name__)


class ChatService:
    """Service for managing chat history and sessions"""
    
    def __init__(self):
        """Initialize chat service"""
        # In-memory storage for development
        # In production, this should be replaced with DynamoDB or Redis
        self._chat_histories: Dict[str, ChatHistory] = {}
        self._chat_sessions: Dict[str, ChatSession] = {}
        
    def create_session(self, user_id: str) -> ChatSession:
        """
        Create a new chat session
        
        Args:
            user_id: User ID
            
        Returns:
            ChatSession: New chat session
        """
        try:
            session_id = str(uuid.uuid4())
            
            session = ChatSession(
                session_id=session_id,
                user_id=user_id
            )
            
            self._chat_sessions[session_id] = session
            
            # Initialize chat history for this session
            history = ChatHistory(
                user_id=user_id,
                session_id=session_id
            )
            self._chat_histories[f"{user_id}:{session_id}"] = history
            
            logger.info(f"Created chat session {session_id} for user {user_id}")
            return session
            
        except Exception as e:
            logger.error(f"Failed to create chat session: {e}")
            raise
    
    def get_session(self, session_id: str) -> Optional[ChatSession]:
        """
        Get chat session by ID
        
        Args:
            session_id: Session ID
            
        Returns:
            Optional[ChatSession]: Session or None if not found
        """
        return self._chat_sessions.get(session_id)
    
    def get_or_create_session(self, user_id: str, session_id: Optional[str] = None) -> ChatSession:
        """
        Get existing session or create new one
        
        Args:
            user_id: User ID
            session_id: Optional session ID
            
        Returns:
            ChatSession: Existing or new session
        """
        if session_id:
            session = self.get_session(session_id)
            if session and session.user_id == user_id:
                session.update_activity()
                return session
        
        # Create new session
        return self.create_session(user_id)
    
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
        try:
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
            if history_key not in self._chat_histories:
                self._chat_histories[history_key] = ChatHistory(
                    user_id=user_id,
                    session_id=session.session_id
                )
            
            history = self._chat_histories[history_key]
            history.add_message(message)
            
            # Update session
            session.message_count += 1
            session.update_activity()
            
            logger.info(f"Added {role} message to session {session.session_id}")
            return message
            
        except Exception as e:
            logger.error(f"Failed to add message: {e}")
            raise
    
    def get_chat_history(
        self, 
        user_id: str, 
        session_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        since: Optional[datetime] = None
    ) -> List[ChatMessage]:
        """
        Get chat history for user
        
        Args:
            user_id: User ID
            session_id: Optional session ID
            limit: Maximum number of messages
            offset: Offset for pagination
            since: Optional timestamp filter
            
        Returns:
            List[ChatMessage]: Chat messages
        """
        try:
            if session_id:
                # Get history for specific session
                history_key = f"{user_id}:{session_id}"
                history = self._chat_histories.get(history_key)
                if not history:
                    return []
                
                messages = history.messages
            else:
                # Get history across all sessions for user
                messages = []
                for key, history in self._chat_histories.items():
                    if key.startswith(f"{user_id}:"):
                        messages.extend(history.messages)
                
                # Sort by timestamp
                messages.sort(key=lambda m: m.timestamp)
            
            # Apply filters
            if since:
                messages = [m for m in messages if m.timestamp >= since]
            
            # Apply pagination
            start_idx = offset
            end_idx = offset + limit
            
            return messages[start_idx:end_idx]
            
        except Exception as e:
            logger.error(f"Failed to get chat history: {e}")
            return []
    
    def get_message_count(self, user_id: str, session_id: Optional[str] = None) -> int:
        """
        Get total message count for user
        
        Args:
            user_id: User ID
            session_id: Optional session ID
            
        Returns:
            int: Total message count
        """
        try:
            if session_id:
                history_key = f"{user_id}:{session_id}"
                history = self._chat_histories.get(history_key)
                return history.total_count if history else 0
            else:
                total = 0
                for key, history in self._chat_histories.items():
                    if key.startswith(f"{user_id}:"):
                        total += history.total_count
                return total
                
        except Exception as e:
            logger.error(f"Failed to get message count: {e}")
            return 0
    
    def update_message_status(
        self, 
        message_id: str, 
        status: MessageStatus
    ) -> bool:
        """
        Update message status
        
        Args:
            message_id: Message ID
            status: New status
            
        Returns:
            bool: True if updated successfully
        """
        try:
            for history in self._chat_histories.values():
                for message in history.messages:
                    if message.id == message_id:
                        message.status = status
                        logger.info(f"Updated message {message_id} status to {status}")
                        return True
            
            logger.warning(f"Message {message_id} not found for status update")
            return False
            
        except Exception as e:
            logger.error(f"Failed to update message status: {e}")
            return False
    
    def cleanup_old_sessions(self, max_age_hours: int = 24):
        """
        Clean up old inactive sessions
        
        Args:
            max_age_hours: Maximum age in hours
        """
        try:
            cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
            
            # Find old sessions
            old_sessions = []
            for session_id, session in self._chat_sessions.items():
                if session.last_activity < cutoff_time:
                    old_sessions.append(session_id)
            
            # Remove old sessions and their histories
            for session_id in old_sessions:
                session = self._chat_sessions.pop(session_id, None)
                if session:
                    history_key = f"{session.user_id}:{session_id}"
                    self._chat_histories.pop(history_key, None)
                    logger.info(f"Cleaned up old session {session_id}")
            
            if old_sessions:
                logger.info(f"Cleaned up {len(old_sessions)} old sessions")
                
        except Exception as e:
            logger.error(f"Failed to cleanup old sessions: {e}")


# Global chat service instance
_chat_service: Optional[ChatService] = None


def get_chat_service() -> ChatService:
    """Get global chat service instance"""
    global _chat_service
    if _chat_service is None:
        _chat_service = ChatService()
    return _chat_service