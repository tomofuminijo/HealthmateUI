#!/usr/bin/env python3
"""
Direct chat test without authentication for development
"""
import asyncio
import json
import sys
import os

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.services.chat_service import get_chat_service
from app.models.chat import MessageRole


async def test_chat_functionality():
    """Test chat functionality directly"""
    print("=== Testing Chat Functionality ===")
    
    # Get chat service
    chat_service = get_chat_service()
    
    # Test user ID
    test_user_id = "test-user-123"
    test_session_id = "healthmate-chat-test-session-123"
    
    print(f"Test User ID: {test_user_id}")
    print(f"Test Session ID: {test_session_id}")
    
    # Add a test user message
    print("\n1. Adding user message...")
    user_message = chat_service.add_message(
        user_id=test_user_id,
        content="こんにちは！健康について相談したいです。",
        role=MessageRole.USER,
        session_id=test_session_id,
        metadata={
            "timezone": "Asia/Tokyo",
            "language": "ja"
        }
    )
    print(f"User message added: {user_message.id}")
    
    # Add a test AI response
    print("\n2. Adding AI response...")
    ai_message = chat_service.add_message(
        user_id=test_user_id,
        content="こんにちは！健康に関するご相談、喜んでお手伝いします。\n\nどのような健康目標をお持ちですか？",
        role=MessageRole.ASSISTANT,
        session_id=test_session_id,
        metadata={
            "timezone": "Asia/Tokyo",
            "language": "ja"
        }
    )
    print(f"AI message added: {ai_message.id}")
    
    # Get chat history
    print("\n3. Retrieving chat history...")
    messages = chat_service.get_chat_history(
        user_id=test_user_id,
        session_id=test_session_id,
        limit=10
    )
    
    print(f"Retrieved {len(messages)} messages:")
    for i, msg in enumerate(messages, 1):
        print(f"  {i}. [{msg.role}] {msg.content[:50]}...")
        print(f"     Session: {msg.session_id}")
        print(f"     Timestamp: {msg.timestamp}")
    
    # Test message count
    print("\n4. Testing message count...")
    total_count = chat_service.get_message_count(
        user_id=test_user_id,
        session_id=test_session_id
    )
    print(f"Total message count: {total_count}")
    
    # Test different session
    print("\n5. Testing different session...")
    different_session_id = "healthmate-chat-different-session-456"
    
    different_message = chat_service.add_message(
        user_id=test_user_id,
        content="これは別のセッションのメッセージです。",
        role=MessageRole.USER,
        session_id=different_session_id
    )
    print(f"Different session message added: {different_message.id}")
    
    # Get history for original session (should not include different session message)
    original_session_messages = chat_service.get_chat_history(
        user_id=test_user_id,
        session_id=test_session_id,
        limit=10
    )
    print(f"Original session messages: {len(original_session_messages)}")
    
    # Get history for different session
    different_session_messages = chat_service.get_chat_history(
        user_id=test_user_id,
        session_id=different_session_id,
        limit=10
    )
    print(f"Different session messages: {len(different_session_messages)}")
    
    print("\n=== Chat Functionality Test Complete ===")
    
    return {
        "user_message": user_message,
        "ai_message": ai_message,
        "original_session_messages": original_session_messages,
        "different_session_messages": different_session_messages,
        "total_count": total_count
    }


if __name__ == "__main__":
    result = asyncio.run(test_chat_functionality())
    print(f"\nTest completed successfully!")
    print(f"Results: {json.dumps({
        'user_message_id': result['user_message'].id,
        'ai_message_id': result['ai_message'].id,
        'original_session_count': len(result['original_session_messages']),
        'different_session_count': len(result['different_session_messages']),
        'total_count': result['total_count']
    }, indent=2)}")