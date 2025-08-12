"""
Minimal sunshine router for testing
"""
from fastapi import APIRouter

print("Loading sunshine_minimal.py...")

router = APIRouter()

@router.get("/")
async def list_sunshines():
    """List endpoint"""
    return {"message": "GET works"}

@router.post("/")
async def create_sunshine():
    """Create endpoint"""
    return {"message": "POST works"}

@router.post("/test")
async def test_post():
    """Test POST endpoint"""
    return {"message": "Test POST works"}

print(f"sunshine_minimal router created with {len(router.routes)} routes")
for route in router.routes:
    if hasattr(route, 'methods'):
        print(f"  - {route.methods} {route.path}")