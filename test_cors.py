#!/usr/bin/env python3
"""
Test CORS configuration for the FastAPI backend
"""
import requests
import json

# Test URLs
BACKEND_URL = "https://luciantales-production.up.railway.app"
TEST_ORIGINS = [
    "https://my-sunshine-stories-frontend-ojb3dgk92-aerware-ai.vercel.app",
    "https://mysunshinestories.com",
    "https://my-sunshine-stories-frontend.vercel.app",
    "http://localhost:5173"
]

def test_cors_endpoint(origin):
    """Test the CORS test endpoint"""
    print(f"\n🔍 Testing CORS from origin: {origin}")
    
    try:
        # Test GET request
        response = requests.get(
            f"{BACKEND_URL}/api/v1/cors-test",
            headers={"Origin": origin}
        )
        
        print(f"  Status: {response.status_code}")
        print(f"  CORS Headers:")
        for header in ["Access-Control-Allow-Origin", "Access-Control-Allow-Credentials"]:
            value = response.headers.get(header, "NOT SET")
            print(f"    {header}: {value}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"  Response: {json.dumps(data, indent=2)}")
    except Exception as e:
        print(f"  ❌ Error: {e}")

def test_options_request(origin):
    """Test OPTIONS preflight request"""
    print(f"\n🔧 Testing OPTIONS to /api/v1/auth/oauth/exchange from: {origin}")
    
    try:
        response = requests.options(
            f"{BACKEND_URL}/api/v1/auth/oauth/exchange",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type"
            }
        )
        
        print(f"  Status: {response.status_code}")
        print(f"  CORS Headers:")
        for header in [
            "Access-Control-Allow-Origin",
            "Access-Control-Allow-Methods",
            "Access-Control-Allow-Headers",
            "Access-Control-Allow-Credentials"
        ]:
            value = response.headers.get(header, "NOT SET")
            print(f"    {header}: {value}")
    except Exception as e:
        print(f"  ❌ Error: {e}")

def main():
    print("=" * 60)
    print("CORS Configuration Test for MySunshineTales Backend")
    print("=" * 60)
    
    # Test health endpoint first
    print(f"\n✅ Testing backend health at: {BACKEND_URL}")
    try:
        response = requests.get(f"{BACKEND_URL}/api/v1/health")
        print(f"  Backend is {'UP' if response.status_code == 200 else 'DOWN'}")
    except:
        print("  ❌ Backend is not reachable")
        return
    
    # Test CORS from different origins
    for origin in TEST_ORIGINS:
        test_cors_endpoint(origin)
        test_options_request(origin)
    
    print("\n" + "=" * 60)
    print("Test complete!")

if __name__ == "__main__":
    main()