#!/usr/bin/env python3
"""
End-to-End HealthCoachAI Integration Test
Complete test: Test Program -> FastAPI -> HealthCoachAI

This test starts a FastAPI server, creates a demo user session,
and tests the full integration through FastAPI endpoints.
"""
import asyncio
import uuid
import boto3
import hashlib
import hmac
import base64
import json
import sys
import os
import httpx
import threading
import time
import uvicorn
import requests
from datetime import datetime
from botocore.exceptions import ClientError

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))


def load_configuration():
    """Load configuration using the same logic as run_dev.py"""
    print("🔧 Loading configuration...")
    
    # Load .env file if exists
    env_file = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_file):
        print("   📄 Loading .env file...")
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    if key not in os.environ:
                        os.environ[key] = value
    
    # Load AWS configuration (same as run_dev.py)
    try:
        region = os.getenv("AWS_REGION", "us-west-2")
        cf_client = boto3.client('cloudformation', region_name=region)
        stack_name = os.getenv("HEALTH_STACK_NAME", "HealthManagerMCPStack")
        
        print(f"   📋 Checking CloudFormation stack: {stack_name}")
        
        # Get stack outputs
        response = cf_client.describe_stacks(StackName=stack_name)
        stack = response['Stacks'][0]
        outputs = {output['OutputKey']: output['OutputValue'] for output in stack.get('Outputs', [])}
        
        # Set environment variables from CloudFormation outputs
        config_mapping = {
            'UserPoolId': 'COGNITO_USER_POOL_ID',
            'UserPoolClientId': 'COGNITO_CLIENT_ID',
            'HealthCoachAIRuntimeId': 'HEALTH_COACH_AI_RUNTIME_ID',
            'AccountId': 'AWS_ACCOUNT_ID'
        }
        
        for cf_key, env_var in config_mapping.items():
            if cf_key in outputs and not os.getenv(env_var):
                os.environ[env_var] = outputs[cf_key]
                print(f"   ✅ {env_var}: {outputs[cf_key][:10]}...")
        
        # Get AWS Account ID if not set
        if not os.getenv("AWS_ACCOUNT_ID"):
            sts_client = boto3.client('sts', region_name=region)
            identity = sts_client.get_caller_identity()
            os.environ["AWS_ACCOUNT_ID"] = identity['Account']
            print(f"   ✅ AWS Account ID: {identity['Account']}")
        
        # Get Cognito Client Secret
        if not os.getenv("COGNITO_CLIENT_SECRET"):
            user_pool_id = os.getenv("COGNITO_USER_POOL_ID")
            client_id = os.getenv("COGNITO_CLIENT_ID")
            
            if user_pool_id and client_id:
                cognito_client = boto3.client('cognito-idp', region_name=region)
                response = cognito_client.describe_user_pool_client(
                    UserPoolId=user_pool_id,
                    ClientId=client_id
                )
                client_secret = response['UserPoolClient'].get('ClientSecret')
                if client_secret:
                    os.environ["COGNITO_CLIENT_SECRET"] = client_secret
                    print(f"   ✅ Cognito Client Secret: {client_secret[:10]}...")
        
        # Get HealthCoachAI Runtime ID
        if not os.getenv("HEALTH_COACH_AI_RUNTIME_ID"):
            agentcore_client = boto3.client('bedrock-agentcore-control', region_name=region)
            response = agentcore_client.list_agent_runtimes()
            runtimes = response.get('agentRuntimes', [])
            
            for runtime in runtimes:
                runtime_name = runtime.get('agentRuntimeName', '')
                runtime_id = runtime.get('agentRuntimeId', '')
                if 'health_coach_ai' in runtime_name.lower():
                    os.environ["HEALTH_COACH_AI_RUNTIME_ID"] = runtime_id
                    print(f"   ✅ HealthCoachAI Runtime ID: {runtime_id}")
                    break
        
        print("   ✅ Configuration loaded successfully")
        
    except Exception as e:
        print(f"   ⚠️  Configuration loading error: {e}")
        print("   💡 Some tests may fail if required environment variables are not set")


# Load configuration before importing config
load_configuration()

from app.utils.config import get_config

# Test configuration
config = get_config()


class E2EHealthCoachTest:
    """End-to-End HealthCoachAI integration test"""
    
    def __init__(self):
        self.config = config
        # Use default AWS session which should have credentials
        session = boto3.Session()
        self.cognito_client = session.client('cognito-idp', region_name=self.config.AWS_REGION)
        self.cfn_client = session.client('cloudformation', region_name=self.config.AWS_REGION)
        self.test_username = None
        self.jwt_token = None
        self.session_cookie = None
        self.fastapi_base_url = "http://localhost:8001"  # Use different port for testing
        self.server_thread = None
        self.server = None
        
    def _get_client_secret(self) -> str:
        """Get Cognito Client Secret from configuration"""
        print("🔑 Using configured Cognito Client Secret...")
        client_secret = self.config.COGNITO_CLIENT_SECRET
        if not client_secret:
            raise ValueError("COGNITO_CLIENT_SECRET not configured")
        print(f"   ✅ Client Secret: {client_secret[:10]}...")
        return client_secret
    
    def _calculate_secret_hash(self, username: str) -> str:
        """Calculate Cognito Client Secret Hash"""
        client_secret = self.config.COGNITO_CLIENT_SECRET
        message = username + self.config.COGNITO_CLIENT_ID
        dig = hmac.new(
            client_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).digest()
        return base64.b64encode(dig).decode()
    
    async def setup_test_user(self):
        """Setup test user using demo login (simplified for testing)"""
        try:
            print("🔐 Setting up test user using demo login...")
            
            # Use demo login to get session
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.fastapi_base_url}/auth/demo",
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code != 200:
                    raise Exception(f"Demo login failed: {response.status_code} - {response.text}")
                
                result = response.json()
                if not result.get("success"):
                    raise Exception(f"Demo login failed: {result.get('error', 'Unknown error')}")
                
                # Extract session cookie
                session_cookie = None
                if hasattr(response, 'cookies'):
                    # httpx response cookies
                    for cookie_name, cookie_value in response.cookies.items():
                        if cookie_name == "healthmate_session":
                            session_cookie = cookie_value
                            break
                
                if not session_cookie:
                    raise Exception("No session cookie received from demo login")
                
                self.session_cookie = session_cookie
                print(f"   ✅ Demo login successful, session: {session_cookie[:20]}...")
                
                # Create a mock JWT token for HealthCoachAI (demo mode)
                self.jwt_token = "demo-jwt-token-for-testing"
                self.test_username = "demo_user"
                
                return True
            
            self.jwt_token = auth_response['AuthenticationResult']['AccessToken']
            
            print(f"   ✅ User created and authenticated")
            print(f"   JWT Token: {self.jwt_token[:50]}...")
            
            # Decode JWT to show user info
            payload = self._decode_jwt_payload(self.jwt_token)
            user_id = payload.get('sub')
            print(f"   User ID (sub): {user_id}")
            
            return True
            
        except Exception as e:
            print(f"   ❌ Test user setup failed: {e}")
            return False
    
    def _decode_jwt_payload(self, jwt_token: str) -> dict:
        """Decode JWT token payload (without signature verification)"""
        try:
            parts = jwt_token.split('.')
            if len(parts) != 3:
                raise ValueError("Invalid JWT format")
            
            payload = parts[1]
            padding = 4 - (len(payload) % 4)
            if padding != 4:
                payload += '=' * padding
            
            decoded_bytes = base64.urlsafe_b64decode(payload)
            payload_data = json.loads(decoded_bytes.decode('utf-8'))
            
            return payload_data
            
        except Exception as e:
            print(f"JWT decode error: {e}")
            return {}
    
    def start_test_server(self):
        """Start FastAPI server in a separate thread for testing"""
        try:
            print("🚀 Starting test FastAPI server...")
            
            # Import the FastAPI app
            from app.main import app
            
            # Configure uvicorn server
            config = uvicorn.Config(
                app,
                host="127.0.0.1",
                port=8001,
                log_level="warning",  # Reduce log noise during testing
                access_log=False
            )
            
            self.server = uvicorn.Server(config)
            
            # Start server in a separate thread
            def run_server():
                asyncio.run(self.server.serve())
            
            self.server_thread = threading.Thread(target=run_server, daemon=True)
            self.server_thread.start()
            
            # Wait for server to start
            max_wait = 10  # seconds
            wait_time = 0
            while wait_time < max_wait:
                try:
                    # Test if server is responding
                    import requests
                    response = requests.get(f"{self.fastapi_base_url}/health", timeout=1)
                    if response.status_code == 200:
                        print(f"   ✅ Test server started on {self.fastapi_base_url}")
                        return True
                except:
                    pass
                
                time.sleep(0.5)
                wait_time += 0.5
            
            print(f"   ❌ Test server failed to start within {max_wait} seconds")
            return False
            
        except Exception as e:
            print(f"   ❌ Error starting test server: {e}")
            return False
    
    def stop_test_server(self):
        """Stop the test FastAPI server"""
        try:
            if self.server:
                print("🛑 Stopping test server...")
                self.server.should_exit = True
                
                # Wait for server thread to finish
                if self.server_thread and self.server_thread.is_alive():
                    self.server_thread.join(timeout=5)
                
                print("   ✅ Test server stopped")
            
        except Exception as e:
            print(f"   ⚠️  Error stopping test server: {e}")
    
    async def cleanup_test_user(self):
        """Clean up test user (demo mode - no cleanup needed)"""
        if self.test_username:
            print(f"   ✅ Demo user session ended: {self.test_username}")
        else:
            print("   ℹ️  No cleanup needed for demo mode")
    
    async def test_fastapi_health(self):
        """Test FastAPI health endpoint"""
        try:
            print("\n🏥 Testing FastAPI health endpoint...")
            
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.fastapi_base_url}/health")
                
                if response.status_code == 200:
                    data = response.json()
                    print(f"   ✅ Health check passed: {data['status']}")
                    return True
                else:
                    print(f"   ❌ Health check failed: {response.status_code}")
                    return False
                    
        except Exception as e:
            print(f"   ❌ Health check error: {e}")
            return False
    
    async def test_fastapi_chat_endpoint(self):
        """Test FastAPI chat endpoint with session cookie"""
        try:
            print("\n💬 Testing FastAPI chat endpoint...")
            
            # Prepare form data
            form_data = {
                "message": "Hello, this is an E2E test message. Please respond briefly.",
                "timezone": "Asia/Tokyo",
                "language": "ja"
            }
            
            print(f"   Sending message: {form_data['message']}")
            
            # Use session cookie for authentication
            cookies = {"healthmate_session": self.session_cookie}
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.fastapi_base_url}/api/chat/send",
                    data=form_data,
                    cookies=cookies
                )
                
                print(f"   Response status: {response.status_code}")
                
                if response.status_code == 200:
                    # Check if response is HTML (htmx) or JSON
                    content_type = response.headers.get('content-type', '')
                    if 'text/html' in content_type:
                        # HTML response from htmx
                        html_content = response.text
                        print(f"   ✅ Chat HTML response received")
                        print(f"   HTML length: {len(html_content)} characters")
                        # Check if HTML contains expected message structure
                        if 'flex items-start space-x-3' in html_content:
                            print(f"   ✅ HTML contains chat messages")
                            return True
                        else:
                            print(f"   ❌ HTML does not contain expected chat structure")
                            return False
                    else:
                        # JSON response
                        data = response.json()
                        if data.get('success'):
                            print(f"   ✅ Chat response received")
                            print(f"   User message ID: {data.get('message_id')}")
                            if data.get('ai_response'):
                                ai_content = data['ai_response'].get('content', '')
                                print(f"   AI response: {ai_content[:100]}...")
                            return True
                        else:
                            print(f"   ❌ Chat failed: {data.get('error')}")
                            return False
                elif response.status_code == 401:
                    print(f"   ❌ Authentication failed - JWT token may be invalid")
                    return False
                else:
                    print(f"   ❌ Chat request failed: {response.status_code}")
                    try:
                        error_data = response.json()
                        print(f"   Error details: {error_data}")
                    except:
                        print(f"   Error text: {response.text}")
                    return False
                    
        except Exception as e:
            print(f"   ❌ Chat endpoint test error: {e}")
            return False
    
    async def test_fastapi_streaming_endpoint(self):
        """Test FastAPI streaming endpoint"""
        try:
            print("\n📡 Testing FastAPI streaming endpoint...")
            
            # Prepare request
            streaming_request = {
                "message": "Hello, this is a streaming test. Please respond with a short message.",
                "timezone": "Asia/Tokyo", 
                "language": "ja"
            }
            
            headers = {
                "Content-Type": "application/json",
                "Accept": "text/event-stream"
            }
            
            # Use session cookie for authentication
            cookies = {"healthmate_session": self.session_cookie}
            
            print(f"   Sending streaming message: {streaming_request['message']}")
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                async with client.stream(
                    "POST",
                    f"{self.fastapi_base_url}/api/streaming/chat",
                    json=streaming_request,
                    headers=headers,
                    cookies=cookies
                ) as response:
                    
                    print(f"   Streaming response status: {response.status_code}")
                    
                    if response.status_code == 200:
                        events_received = 0
                        ai_text_chunks = []
                        
                        async for line in response.aiter_lines():
                            if line.startswith("data: "):
                                try:
                                    event_data = json.loads(line[6:])  # Remove "data: " prefix
                                    event_type = event_data.get('type')
                                    
                                    events_received += 1
                                    
                                    if event_type == 'connected':
                                        print(f"   📡 Connected: {event_data.get('message')}")
                                    elif event_type == 'user_message':
                                        print(f"   👤 User message processed")
                                    elif event_type == 'ai_thinking':
                                        print(f"   🤔 AI thinking...")
                                    elif event_type == 'ai_chunk':
                                        # Text is directly in event_data, not nested in 'data'
                                        text = event_data.get('text', '')
                                        if text:  # Only append non-empty text
                                            ai_text_chunks.append(text)
                                            print(f"{text}", end='', flush=True)
                                    elif event_type == 'ai_message_complete':
                                        print(f"\n   ✅ AI message complete")
                                    elif event_type == 'complete':
                                        print(f"   🎉 Streaming complete")
                                        break
                                    elif event_type == 'error':
                                        print(f"   ❌ Streaming error: {event_data.get('error')}")
                                        return False
                                    else:
                                        # Log unknown event types for debugging
                                        print(f"\n   🔍 Unknown event: {event_type}")
                                        
                                except json.JSONDecodeError:
                                    continue
                        
                        complete_ai_response = ''.join(ai_text_chunks)
                        print(f"\n   Events received: {events_received}")
                        print(f"   AI text chunks: {len(ai_text_chunks)}")
                        print(f"   Complete AI response: {complete_ai_response[:100]}...")
                        
                        # Success if we received events and have AI response text
                        success = events_received > 0 and len(complete_ai_response) > 0
                        if success:
                            print(f"   ✅ Streaming test successful!")
                        else:
                            print(f"   ❌ Streaming test failed - no AI response text")
                        
                        return success
                    else:
                        print(f"   ❌ Streaming failed: {response.status_code}")
                        return False
                        
        except Exception as e:
            print(f"   ❌ Streaming endpoint test error: {e}")
            return False
    
    async def test_chat_history_endpoint(self):
        """Test chat history endpoint"""
        try:
            print("\n📚 Testing chat history endpoint...")
            
            # Use session cookie for authentication
            cookies = {"healthmate_session": self.session_cookie}
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.fastapi_base_url}/api/chat/history",
                    cookies=cookies
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('success'):
                        messages = data.get('messages', [])
                        print(f"   ✅ Chat history retrieved: {len(messages)} messages")
                        return True
                    else:
                        print(f"   ❌ History retrieval failed: {data.get('error')}")
                        return False
                else:
                    print(f"   ❌ History request failed: {response.status_code}")
                    return False
                    
        except Exception as e:
            print(f"   ❌ Chat history test error: {e}")
            return False
    
    async def run_e2e_tests(self):
        """Run all end-to-end tests"""
        print("🧪 End-to-End HealthCoachAI Integration Test")
        print("=" * 60)
        print("Testing: Test Program -> FastAPI -> HealthCoachAI")
        print()
        
        # Start test server
        if not self.start_test_server():
            print("❌ Failed to start test server. Aborting tests.")
            return False
        
        try:
            # Setup
            setup_success = await self.setup_test_user()
            if not setup_success:
                print("❌ Test setup failed. Aborting tests.")
                return False
            
            # Run tests
            test_results = []
            
            test_results.append(await self.test_fastapi_health())
            test_results.append(await self.test_fastapi_chat_endpoint())
            test_results.append(await self.test_fastapi_streaming_endpoint())
            test_results.append(await self.test_chat_history_endpoint())
            
            # Summary
            passed_tests = sum(test_results)
            total_tests = len(test_results)
            
            print(f"\n📊 E2E Test Results:")
            print(f"   Passed: {passed_tests}/{total_tests}")
            print(f"   Success Rate: {(passed_tests/total_tests)*100:.1f}%")
            
            print(f"\n📋 Test Status:")
            print(f"   - FastAPI Health: {'✅' if test_results[0] else '❌'}")
            print(f"   - Chat Endpoint: {'✅' if test_results[1] else '❌'}")
            print(f"   - Streaming Endpoint: {'✅' if test_results[2] else '❌'}")
            print(f"   - Chat History: {'✅' if test_results[3] else '❌'}")
            
            if passed_tests == total_tests:
                print("\n🎉 All E2E tests passed!")
                print("✅ HealthCoachAI integration is working correctly!")
            else:
                print("\n⚠️  Some E2E tests failed")
                print("🔧 Check the error messages above for details")
            
            return passed_tests == total_tests
            
        finally:
            # Cleanup
            print(f"\n🧹 Cleaning up test user...")
            await self.cleanup_test_user()
            
            # Stop test server
            self.stop_test_server()


async def main():
    """Main test function"""
    print("🚀 Starting End-to-End HealthCoachAI Integration Test")
    print("📋 Prerequisites:")
    print("   - HealthCoachAI deployed and accessible via AgentCore")
    print("   - Cognito User Pool configured")
    print("   - AWS credentials configured")
    print("   - Test will start its own FastAPI server")
    print()
    
    test_suite = E2EHealthCoachTest()
    success = await test_suite.run_e2e_tests()
    
    if success:
        print("\n🚀 E2E integration test completed successfully!")
        print("✅ Ready to proceed with frontend implementation!")
    else:
        print("\n🔧 E2E integration test failed.")
        print("❌ Please check the configuration and try again.")
    
    return success


if __name__ == "__main__":
    try:
        result = asyncio.run(main())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n\n👋 Test interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)