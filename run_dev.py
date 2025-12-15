#!/usr/bin/env python3
"""
Development server startup script for HealthmateUI
"""
import uvicorn
import sys
import os
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def load_aws_config():
    """Load AWS configuration from CloudFormation stack"""
    print("🔧 Loading AWS configuration from CloudFormation...")
    
    try:
        # Initialize boto3 client
        region = os.getenv("AWS_REGION", "us-west-2")
        cf_client = boto3.client('cloudformation', region_name=region)
        
        # Get stack name from environment or use default
        stack_name = os.getenv("HEALTH_STACK_NAME", "healthmate-stack")
        
        print(f"   📋 Checking CloudFormation stack: {stack_name}")
        
        # Get stack outputs
        try:
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
            
            configured_vars = []
            for cf_key, env_var in config_mapping.items():
                if cf_key in outputs:
                    os.environ[env_var] = outputs[cf_key]
                    # Mask sensitive values in logs
                    display_value = outputs[cf_key]
                    if 'client_id' in env_var.lower():
                        display_value = f"{display_value[:8]}..."
                    configured_vars.append(f"{env_var}={display_value}")
            
            if configured_vars:
                print("   ✅ Configured from CloudFormation:")
                for var in configured_vars:
                    print(f"      {var}")
            else:
                print("   ⚠️  No matching outputs found in CloudFormation stack")
                
        except ClientError as e:
            if e.response['Error']['Code'] == 'ValidationError':
                print(f"   ⚠️  CloudFormation stack '{stack_name}' not found")
                print("   💡 You can set HEALTH_STACK_NAME environment variable to specify a different stack")
            else:
                print(f"   ❌ CloudFormation error: {e}")
        
        
        # Try to get AWS Account ID if not set
        if not os.getenv("AWS_ACCOUNT_ID"):
            try:
                sts_client = boto3.client('sts', region_name=region)
                identity = sts_client.get_caller_identity()
                account_id = identity['Account']
                os.environ["AWS_ACCOUNT_ID"] = account_id
                print(f"   ✅ AWS Account ID: {account_id}")
            except Exception as e:
                print(f"   ⚠️  Could not get AWS Account ID: {e}")
        
        # Get Cognito Client Secret using AWS CLI
        if not os.getenv("COGNITO_CLIENT_SECRET"):
            user_pool_id = os.getenv("COGNITO_USER_POOL_ID")
            client_id = os.getenv("COGNITO_CLIENT_ID")
            
            if user_pool_id and client_id:
                try:
                    cognito_client = boto3.client('cognito-idp', region_name=region)
                    response = cognito_client.describe_user_pool_client(
                        UserPoolId=user_pool_id,
                        ClientId=client_id
                    )
                    
                    client_secret = response['UserPoolClient'].get('ClientSecret')
                    if client_secret:
                        os.environ["COGNITO_CLIENT_SECRET"] = client_secret
                        print(f"   ✅ Cognito Client Secret: {client_secret[:8]}...")
                    else:
                        print("   ⚠️  Cognito Client has no secret (public client)")
                        
                except Exception as e:
                    print(f"   ⚠️  Could not get Cognito Client Secret: {e}")
            else:
                print("   ⚠️  Cannot get Client Secret: User Pool ID or Client ID missing")
        
        # Try to get HealthCoachAI Runtime ID from Bedrock AgentCore Control API
        if not os.getenv("HEALTH_COACH_AI_RUNTIME_ID"):
            try:
                agentcore_client = boto3.client('bedrock-agentcore-control', region_name=region)
                
                # List all agent runtimes
                response = agentcore_client.list_agent_runtimes()
                runtimes = response.get('agentRuntimes', [])
                
                # Look for health_coach_ai runtime
                for runtime in runtimes:
                    runtime_name = runtime.get('agentRuntimeName', '')
                    runtime_id = runtime.get('agentRuntimeId', '')
                    if 'health_coach_ai' in runtime_name.lower():
                        os.environ["HEALTH_COACH_AI_RUNTIME_ID"] = runtime_id
                        print(f"   ✅ HealthCoachAI Runtime ID: {runtime_id}")
                        break
                else:
                    print("   ⚠️  No HealthCoachAI runtime found in AgentCore")
                    if runtimes:
                        runtime_info = []
                        for r in runtimes[:3]:
                            name = r.get('agentRuntimeName', 'unnamed')
                            rid = r.get('agentRuntimeId', 'no-id')
                            runtime_info.append(f"{name}({rid})")
                        print(f"   📋 Available runtimes: {runtime_info}")
                    
            except ClientError as e:
                error_code = e.response['Error']['Code']
                if error_code == 'UnauthorizedOperation':
                    print("   ⚠️  No permission to list AgentCore runtimes")
                elif error_code == 'ServiceUnavailable':
                    print("   ⚠️  Bedrock AgentCore service unavailable in this region")
                else:
                    print(f"   ⚠️  AgentCore API error: {error_code}")
            except Exception as e:
                print(f"   ⚠️  Could not get HealthCoachAI Runtime ID: {e}")
                
                # Fallback to agentcore CLI if available
                try:
                    import subprocess
                    result = subprocess.run(
                        ['agentcore', 'list', '--format', 'json'],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    if result.returncode == 0:
                        import json
                        runtimes = json.loads(result.stdout)
                        for runtime in runtimes:
                            if 'health_coach_ai' in runtime.get('name', '').lower():
                                runtime_id = runtime.get('name')
                                os.environ["HEALTH_COACH_AI_RUNTIME_ID"] = runtime_id
                                print(f"   ✅ HealthCoachAI Runtime ID (CLI): {runtime_id}")
                                break
                    else:
                        print("   ⚠️  AgentCore CLI also failed")
                except FileNotFoundError:
                    print("   ⚠️  AgentCore CLI not installed")
                except Exception as cli_e:
                    print(f"   ⚠️  AgentCore CLI error: {cli_e}")
                
    except NoCredentialsError:
        print("   ⚠️  AWS credentials not configured")
        print("   💡 Run 'aws configure' or set AWS environment variables")
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'UnauthorizedOperation':
            print("   ⚠️  Insufficient AWS permissions")
            print("   💡 Ensure your AWS user has CloudFormation, Cognito, and AgentCore permissions")
        else:
            print(f"   ❌ AWS API error: {error_code} - {e.response['Error']['Message']}")
    except Exception as e:
        print(f"   ❌ Unexpected error loading AWS config: {e}")
    
    print()


def check_env_file():
    """Check if .env file exists and load it"""
    env_file = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_file):
        print("📄 Loading configuration from .env file...")
        try:
            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        # Only set if not already in environment
                        if key not in os.environ:
                            os.environ[key] = value
            print("   ✅ .env file loaded")
        except Exception as e:
            print(f"   ⚠️  Error loading .env file: {e}")
    else:
        print("   ℹ️  No .env file found (optional)")
    print()


def main():
    """Start the development server"""
    print("🚀 Starting HealthmateUI Development Server")
    print("=" * 50)
    
    # Load configuration
    check_env_file()
    load_aws_config()
    
    # Import config after environment variables are set
    from app.utils.config import get_config
    
    try:
        config = get_config()
        config.validate_required_config()
        
        print("✅ Configuration validated successfully")
        print(f"Environment: {config.__class__.__name__}")
        print(f"Debug Mode: {config.DEBUG}")
        print(f"AWS Region: {config.AWS_REGION}")
        print(f"Server: http://localhost:8000")
        print("Press Ctrl+C to stop the server")
        print("-" * 50)
        
        uvicorn.run(
            "app.main:app",
            host="0.0.0.0",
            port=8000,
            reload=True,
            reload_dirs=["app", "templates", "static"],
            log_level="debug" if config.DEBUG else "info",
            access_log=True
        )
        
    except ValueError as e:
        print(f"❌ Configuration Error: {e}")
        print("\n💡 Troubleshooting:")
        print("   1. Ensure AWS credentials are configured: aws configure")
        print("   2. Deploy HealthManagerMCP stack: cd ../HealthManagerMCP && cdk deploy")
        print("   3. Deploy HealthCoachAI: cd ../HealthCoachAI && ./deploy_to_aws.sh")
        print("   4. Set HEALTH_STACK_NAME if using a different stack name")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n👋 Server stopped by user")
    except Exception as e:
        print(f"❌ Server error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()