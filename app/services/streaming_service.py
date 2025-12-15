"""
Streaming service for managing Server-Sent Events connections
"""
import asyncio
import uuid
from typing import Dict, Set, Optional, AsyncGenerator
from datetime import datetime, timedelta

from ..utils.logger import setup_logger
from ..models.chat import StreamingEvent

logger = setup_logger(__name__)


class StreamingConnection:
    """Represents a streaming connection"""
    
    def __init__(self, connection_id: str, user_id: str):
        self.connection_id = connection_id
        self.user_id = user_id
        self.created_at = datetime.now()
        self.last_activity = datetime.now()
        self.is_active = True
        self._queue: asyncio.Queue = asyncio.Queue()
    
    async def send_event(self, event: StreamingEvent):
        """Send an event to this connection"""
        if self.is_active:
            try:
                await self._queue.put(event)
                self.last_activity = datetime.now()
            except Exception as e:
                logger.error(f"Failed to send event to connection {self.connection_id}: {e}")
                self.is_active = False
    
    async def get_events(self) -> AsyncGenerator[StreamingEvent, None]:
        """Get events from this connection's queue"""
        try:
            while self.is_active:
                try:
                    # Wait for event with timeout
                    event = await asyncio.wait_for(self._queue.get(), timeout=30.0)
                    yield event
                    self.last_activity = datetime.now()
                except asyncio.TimeoutError:
                    # Send keepalive event
                    keepalive_event = StreamingEvent(
                        event_type="keepalive",
                        message="Connection active"
                    )
                    yield keepalive_event
                    self.last_activity = datetime.now()
        except Exception as e:
            logger.error(f"Error in event stream for connection {self.connection_id}: {e}")
            self.is_active = False
    
    def close(self):
        """Close the connection"""
        self.is_active = False
        logger.info(f"Closed streaming connection {self.connection_id}")


class StreamingService:
    """Service for managing streaming connections"""
    
    def __init__(self):
        self._connections: Dict[str, StreamingConnection] = {}
        self._user_connections: Dict[str, Set[str]] = {}
        self._cleanup_task: Optional[asyncio.Task] = None
        self._start_cleanup_task()
    
    def _start_cleanup_task(self):
        """Start the cleanup task"""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
    
    async def _cleanup_loop(self):
        """Cleanup inactive connections periodically"""
        while True:
            try:
                await asyncio.sleep(60)  # Run every minute
                await self._cleanup_inactive_connections()
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
    
    async def _cleanup_inactive_connections(self):
        """Remove inactive connections"""
        try:
            cutoff_time = datetime.now() - timedelta(minutes=5)  # 5 minute timeout
            
            inactive_connections = []
            for connection_id, connection in self._connections.items():
                if not connection.is_active or connection.last_activity < cutoff_time:
                    inactive_connections.append(connection_id)
            
            for connection_id in inactive_connections:
                await self.remove_connection(connection_id)
            
            if inactive_connections:
                logger.info(f"Cleaned up {len(inactive_connections)} inactive streaming connections")
                
        except Exception as e:
            logger.error(f"Error cleaning up connections: {e}")
    
    def create_connection(self, user_id: str) -> StreamingConnection:
        """Create a new streaming connection"""
        try:
            connection_id = str(uuid.uuid4())
            connection = StreamingConnection(connection_id, user_id)
            
            self._connections[connection_id] = connection
            
            if user_id not in self._user_connections:
                self._user_connections[user_id] = set()
            self._user_connections[user_id].add(connection_id)
            
            logger.info(f"Created streaming connection {connection_id} for user {user_id}")
            return connection
            
        except Exception as e:
            logger.error(f"Failed to create streaming connection: {e}")
            raise
    
    async def remove_connection(self, connection_id: str):
        """Remove a streaming connection"""
        try:
            connection = self._connections.pop(connection_id, None)
            if connection:
                connection.close()
                
                # Remove from user connections
                user_connections = self._user_connections.get(connection.user_id, set())
                user_connections.discard(connection_id)
                
                if not user_connections:
                    self._user_connections.pop(connection.user_id, None)
                
                logger.info(f"Removed streaming connection {connection_id}")
                
        except Exception as e:
            logger.error(f"Error removing connection {connection_id}: {e}")
    
    def get_connection(self, connection_id: str) -> Optional[StreamingConnection]:
        """Get a streaming connection by ID"""
        return self._connections.get(connection_id)
    
    def get_user_connections(self, user_id: str) -> Set[str]:
        """Get all connection IDs for a user"""
        return self._user_connections.get(user_id, set()).copy()
    
    async def broadcast_to_user(self, user_id: str, event: StreamingEvent):
        """Broadcast an event to all connections for a user"""
        try:
            connection_ids = self.get_user_connections(user_id)
            
            for connection_id in connection_ids:
                connection = self.get_connection(connection_id)
                if connection and connection.is_active:
                    await connection.send_event(event)
                    
        except Exception as e:
            logger.error(f"Error broadcasting to user {user_id}: {e}")
    
    def get_connection_count(self) -> int:
        """Get total number of active connections"""
        return len([c for c in self._connections.values() if c.is_active])
    
    def get_user_count(self) -> int:
        """Get number of users with active connections"""
        return len(self._user_connections)


# Global streaming service instance
_streaming_service: Optional[StreamingService] = None


def get_streaming_service() -> StreamingService:
    """Get global streaming service instance"""
    global _streaming_service
    if _streaming_service is None:
        _streaming_service = StreamingService()
    return _streaming_service