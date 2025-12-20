#!/usr/bin/env python3
"""
Development server startup script for HealthmateUI
Dynamically loads configuration from AWS services
"""
import uvicorn
import sys
import os
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def load_aws_config():
    """Load AWS configuration dynamically from CloudFormation and AWS services"""
    print("🔧 Loading AWS configuration...")
    
    try:
        region = os.getenv("AWS_REGION", "us-west-2")
        
        # Load from CloudFormation stack
        _load_from_cloudformation(region)
        
        # Load AWS Account ID if not set
        _load_aws_account_id(region)
        
        # Load HealthCoachAI Runtime ID if not set
        _load_healthcoach_runtime_id(region)
        
    except NoCredentialsError:
        print("   ⚠️  AWS credentials not configured. Run 'aws configure'")
    except Exception as e:
        print(f"   ⚠️  AWS configuration error: {e}")
    
    print()


def _load_from_cloudformation(region: str):
    """Load configuration from CloudFormation stack"""
    stack_name = os.getenv("HEALTH_STACK_NAME", "Healthmate-CoreStack")
    
    try:
        cf_client = boto3.client('cloudformation', region_name=region)
        response = cf_client.describe_stacks(StackName=stack_name)
        stack = response['Stacks'][0]
        outputs = {output['OutputKey']: output['OutputValue'] for output in stack.get('Outputs', [])}
        
        # Map CloudFormation outputs to environment variables
        config_mapping = {
            'UserPoolId': 'COGNITO_USER_POOL_ID',
            'UserPoolClientId': 'COGNITO_CLIENT_ID',
            'HealthCoachAIRuntimeId': 'HEALTH_COACH_AI_RUNTIME_ID',
            'AccountId': 'AWS_ACCOUNT_ID'
        }
        
        configured_count = 0
        for cf_key, env_var in config_mapping.items():
            if cf_key in outputs:
                os.environ[env_var] = outputs[cf_key]
                configured_count += 1
        
        if configured_count > 0:
            print(f"   ✅ Loaded {configured_count} variables from CloudFormation stack: {stack_name}")
        else:
            print(f"   ⚠️  No configuration found in CloudFormation stack: {stack_name}")
            
    except ClientError as e:
        if e.response['Error']['Code'] == 'ValidationError':
            print(f"   ⚠️  CloudFormation stack '{stack_name}' not found")
        else:
            print(f"   ⚠️  CloudFormation error: {e.response['Error']['Code']}")


def _load_aws_account_id(region: str):
    """Load AWS Account ID from STS"""
    if os.getenv("AWS_ACCOUNT_ID"):
        return
        
    try:
        sts_client = boto3.client('sts', region_name=region)
        identity = sts_client.get_caller_identity()
        account_id = identity['Account']
        os.environ["AWS_ACCOUNT_ID"] = account_id
        print(f"   ✅ AWS Account ID: {account_id}")
    except Exception as e:
        print(f"   ⚠️  Could not get AWS Account ID: {e}")


def _load_healthcoach_runtime_id(region: str):
    """Load HealthCoachAI Runtime ID from AgentCore"""
    if os.getenv("HEALTH_COACH_AI_RUNTIME_ID"):
        return
        
    try:
        # Try AgentCore API first
        agentcore_client = boto3.client('bedrock-agentcore-control', region_name=region)
        response = agentcore_client.list_agent_runtimes()
        runtimes = response.get('agentRuntimes', [])
        
        for runtime in runtimes:
            runtime_name = runtime.get('agentRuntimeName', '')
            runtime_id = runtime.get('agentRuntimeId', '')
            if 'healthmate_coach_ai' in runtime_name.lower():
                os.environ["HEALTH_COACH_AI_RUNTIME_ID"] = runtime_id
                print(f"   ✅ HealthCoachAI Runtime ID: {runtime_id}")
                return
        
        print("   ⚠️  HealthCoachAI runtime not found in AgentCore")
        
    except ClientError as e:
        print(f"   ⚠️  AgentCore API error: {e.response['Error']['Code']}")
        
        # Fallback to CLI if API fails
        _try_agentcore_cli()
    except Exception as e:
        print(f"   ⚠️  Could not get HealthCoachAI Runtime ID: {e}")


def _try_agentcore_cli():
    """Fallback to AgentCore CLI"""
    try:
        import subprocess
        import json
        
        result = subprocess.run(
            ['agentcore', 'list', '--format', 'json'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            runtimes = json.loads(result.stdout)
            for runtime in runtimes:
                if 'health_coach_ai' in runtime.get('name', '').lower():
                    runtime_id = runtime.get('name')
                    os.environ["HEALTH_COACH_AI_RUNTIME_ID"] = runtime_id
                    print(f"   ✅ HealthCoachAI Runtime ID (CLI): {runtime_id}")
                    return
        
        print("   ⚠️  AgentCore CLI: No HealthCoachAI runtime found")
        
    except FileNotFoundError:
        print("   ⚠️  AgentCore CLI not installed")
    except Exception as e:
        print(f"   ⚠️  AgentCore CLI error: {e}")


def check_env_file():
    """Load .env file if it exists (optional)"""
    env_file = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_file):
        print("📄 Loading .env file...")
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
    print()


def main():
    """Start the development server"""
    print("🚀 Starting HealthmateUI Development Server")
    print("=" * 50)
    
    # Load configuration
    check_env_file()
    load_aws_config()
    
    # Import and validate configuration
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
        print("   2. Deploy Healthmate-Core stack: cd ../Healthmate-Core && cdk deploy")
        print("   3. Deploy HealthCoachAI: cd ../Healthmate-CoachAI && ./deploy_to_aws.sh")
        print("   4. Set HEALTH_STACK_NAME if using a different stack name")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n👋 Server stopped by user")
    except Exception as e:
        print(f"❌ Server error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()