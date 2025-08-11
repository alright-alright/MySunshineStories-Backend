from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, Response
import os

from app.api.routes import story, health, auth, sunshine, subscription, story_v2, story_enhanced
from app.core.database import engine, Base
from app.core.cors import get_allowed_origins, should_allow_origin, CORS_CONFIG

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="LucianTales API",
    description="Backend API for generating personalized children's stories with AI illustrations",
    version="2.0.0"
)

# Get allowed origins from configuration
allowed_origins = get_allowed_origins()

# Custom CORS middleware to handle dynamic origins (Vercel previews, etc)
@app.middleware("http")
async def custom_cors_middleware(request: Request, call_next):
    """
    Custom CORS middleware to handle dynamic origins like Vercel preview deployments
    """
    origin = request.headers.get("origin")
    
    # Handle preflight requests
    if request.method == "OPTIONS":
        response = Response()
        if should_allow_origin(origin, allowed_origins):
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Methods"] = ", ".join(CORS_CONFIG["allow_methods"])
            response.headers["Access-Control-Allow-Headers"] = "*"
            response.headers["Access-Control-Max-Age"] = str(CORS_CONFIG["max_age"])
        return response
    
    # Process the request
    response = await call_next(request)
    
    # Add CORS headers if origin is allowed
    if should_allow_origin(origin, allowed_origins):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = ", ".join(CORS_CONFIG["allow_methods"])
        response.headers["Access-Control-Allow-Headers"] = "*"
        response.headers["Access-Control-Expose-Headers"] = "*"
    
    return response

# Standard CORS middleware as fallback
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    **CORS_CONFIG
)

# Serve static files (for generated PDFs in development)
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Root endpoint - API information
@app.get("/")
async def root():
    """API Information"""
    return {
        "message": "LucianTales Backend API",
        "status": "operational",
        "documentation": "https://luciantales-production.up.railway.app/docs",
        "frontend": "Deploy frontend separately or visit https://mysunshinestory.ai",
        "endpoints": {
            "health": "/api/v1/health",
            "auth": "/api/v1/auth",
            "stories": "/api/v1/stories",
            "sunshines": "/api/v1/sunshines"
        }
    }

# CORS test endpoint
@app.get("/api/v1/cors-test")
async def cors_test(request: Request):
    """Test CORS configuration"""
    origin = request.headers.get("origin", "No origin header")
    allowed = should_allow_origin(origin, allowed_origins)
    
    return {
        "origin": origin,
        "allowed": allowed,
        "configured_origins": allowed_origins[:5] + ["..."],  # Show first 5 for security
        "total_origins": len(allowed_origins),
        "cors_enabled": True,
        "message": "CORS is properly configured" if allowed else "Origin not in allowed list"
    }

# OPTIONS handler for OAuth endpoints
@app.options("/api/v1/auth/oauth/exchange")
async def oauth_exchange_options():
    """Handle preflight for OAuth exchange endpoint"""
    return {"message": "OK"}

# Include routers
app.include_router(health.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1/auth", tags=["authentication"])
app.include_router(sunshine.router, prefix="/api/v1/sunshines", tags=["sunshines"])
app.include_router(story.router, prefix="/api/v1", tags=["stories"])
app.include_router(subscription.router, prefix="/api/v1/subscription", tags=["subscription"])
app.include_router(story_v2.router, prefix="/api/v2/stories", tags=["stories-v2"])
app.include_router(story_enhanced.router, prefix="/api/v3/stories", tags=["stories-enhanced"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
