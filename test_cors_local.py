#!/usr/bin/env python3
"""
Test CORS locally before deploying
"""
import subprocess
import time
import requests
import sys

def start_server():
    """Start the FastAPI server in the background"""
    print("🚀 Starting FastAPI server...")
    process = subprocess.Popen(
        [sys.executable, "run.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    time.sleep(3)  # Give server time to start
    return process

def test_cors():
    """Test CORS configuration"""
    base_url = "http://localhost:8000"
    test_origins = [
        "https://my-sunshine-stories-frontend-ojb3dgk92-aerware-ai.vercel.app",
        "https://mysunshinestories.com",
        "https://www.mysunshinestories.com"
    ]
    
    print("\n" + "="*60)
    print("CORS Configuration Test")
    print("="*60)
    
    # Test health endpoint
    print(f"\n✅ Testing health endpoint...")
    try:
        response = requests.get(f"{base_url}/api/v1/health")
        print(f"  Status: {response.status_code}")
        print(f"  Response: {response.json()}")
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False
    
    # Test CORS endpoint
    print(f"\n🔍 Testing CORS endpoint...")
    for origin in test_origins:
        print(f"\n  Testing from origin: {origin}")
        try:
            response = requests.get(
                f"{base_url}/api/v1/cors-test",
                headers={"Origin": origin}
            )
            print(f"    Status: {response.status_code}")
            
            # Check CORS headers
            cors_headers = {
                "Access-Control-Allow-Origin": response.headers.get("access-control-allow-origin", "NOT SET"),
                "Access-Control-Allow-Credentials": response.headers.get("access-control-allow-credentials", "NOT SET")
            }
            
            for header, value in cors_headers.items():
                status = "✅" if value != "NOT SET" else "❌"
                print(f"    {status} {header}: {value}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"    Response: Allowed={data.get('allowed')}, Message={data.get('message')}")
        except Exception as e:
            print(f"    ❌ Error: {e}")
    
    # Test OPTIONS request
    print(f"\n🔧 Testing OPTIONS requests...")
    test_endpoints = [
        "/api/v1/auth/oauth/exchange",
        "/api/v1/auth/oauth/login",
        "/api/v1/auth/me"
    ]
    
    for endpoint in test_endpoints:
        print(f"\n  Testing OPTIONS {endpoint}")
        for origin in test_origins[:1]:  # Test with first origin only
            try:
                response = requests.options(
                    f"{base_url}{endpoint}",
                    headers={
                        "Origin": origin,
                        "Access-Control-Request-Method": "POST",
                        "Access-Control-Request-Headers": "Content-Type,Authorization"
                    }
                )
                print(f"    Origin: {origin[:50]}...")
                print(f"    Status: {response.status_code}")
                
                # Check preflight response headers
                preflight_headers = [
                    "access-control-allow-origin",
                    "access-control-allow-methods",
                    "access-control-allow-headers",
                    "access-control-allow-credentials"
                ]
                
                for header in preflight_headers:
                    value = response.headers.get(header, "NOT SET")
                    status = "✅" if value != "NOT SET" else "❌"
                    print(f"    {status} {header}: {value[:50]}..." if len(str(value)) > 50 else f"    {status} {header}: {value}")
                    
            except Exception as e:
                print(f"    ❌ Error: {e}")
    
    return True

def main():
    """Main test function"""
    # Start server
    server_process = start_server()
    
    try:
        # Run tests
        success = test_cors()
        
        if success:
            print("\n✅ CORS tests completed!")
        else:
            print("\n❌ CORS tests failed!")
    finally:
        # Stop server
        print("\n🛑 Stopping server...")
        server_process.terminate()
        server_process.wait()

if __name__ == "__main__":
    main()