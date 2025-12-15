#!/usr/bin/env python3
"""
Simple authentication test
Test basic JWT processing without full verification
"""
import asyncio
import httpx
import base64
import json


async def test_simple_jwt_processing():
    """Test simple JWT processing"""
    print("🧪 Testing Simple JWT Processing")
    print("=" * 50)
    
    # Create a simple mock JWT token
    header = {"alg": "RS256", "typ": "JWT", "kid": "test-key"}
    payload = {
        "sub": "test-user-123",
        "email": "test@example.com",
        "username": "testuser",
        "email_verified": True,
        "exp": 9999999999,  # Far future
        "iat": 1640995200,
        "token_use": "access"
    }
    
    # Encode (without signature for testing)
    header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip('=')
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip('=')
    mock_jwt = f"{header_b64}.{payload_b64}.mock-signature"
    
    print(f"Mock JWT: {mock_jwt[:50]}...")
    
    # Test FastAPI endpoint with mock JWT
    try:
        headers = {
            "Authorization": f"Bearer {mock_jwt}",
            "Content-Type": "application/json"
        }
        
        chat_request = {
            "message": "Hello, this is a simple test",
            "timezone": "Asia/Tokyo",
            "language": "ja"
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "http://localhost:8000/api/chat/send",
                json=chat_request,
                headers=headers
            )
            
            print(f"Response status: {response.status_code}")
            print(f"Response headers: {dict(response.headers)}")
            
            if response.status_code == 401:
                print("❌ Still getting 401 - authentication middleware issue")
                try:
                    error_data = response.json()
                    print(f"Error details: {error_data}")
                except:
                    print(f"Error text: {response.text}")
            elif response.status_code == 200:
                print("✅ Authentication passed!")
                data = response.json()
                print(f"Response: {data}")
            else:
                print(f"⚠️  Unexpected status: {response.status_code}")
                print(f"Response: {response.text}")
                
    except Exception as e:
        print(f"❌ Request error: {e}")


async def test_direct_middleware():
    """Test middleware directly"""
    print("\n🔧 Testing Middleware Directly")
    print("=" * 50)
    
    try:
        # Import and test middleware components
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))
        
        from app.auth.middleware import AuthenticationMiddleware
        from app.auth.cognito import get_cognito_client
        
        print("✅ Middleware imports successful")
        
        # Test cognito client
        cognito_client = get_cognito_client()
        print(f"✅ Cognito client created: {type(cognito_client)}")
        
        # Test JWT decode (without verification)
        test_jwt = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6InRlc3Qta2V5In0.eyJzdWIiOiJ0ZXN0LXVzZXItMTIzIiwiZW1haWwiOiJ0ZXN0QGV4YW1wbGUuY29tIiwidXNlcm5hbWUiOiJ0ZXN0dXNlciIsImVtYWlsX3ZlcmlmaWVkIjp0cnVlLCJleHAiOjk5OTk5OTk5OTksImlhdCI6MTY0MDk5NTIwMCwidG9rZW5fdXNlIjoiYWNjZXNzIn0.mock-signature"
        
        decoded = cognito_client.decode_jwt_payload(test_jwt)
        print(f"✅ JWT decode test: {decoded}")
        
    except Exception as e:
        print(f"❌ Middleware test error: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Main test function"""
    await test_direct_middleware()
    await test_simple_jwt_processing()


if __name__ == "__main__":
    asyncio.run(main())