from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, Response, JSONResponse
import os

from app.api.routes import story, health, auth, sunshine, subscription, story_v2, story_enhanced
from app.core.database import engine, Base

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="LucianTales API",
    description="Backend API for generating personalized children's stories with AI illustrations",
    version="2.0.0"
)

# CORS Configuration - Simple and working
origins = [
    # Local development
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:4173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:4173",
    
    # Production domains
    "https://mysunshinestory.ai",
    "https://www.mysunshinestory.ai",
    "https://mysunshinestories.com",
    "https://www.mysunshinestories.com",
    
    # Vercel deployments
    "https://my-sunshine-stories-frontend.vercel.app",
    "https://my-sunshine-stories-frontend-ojb3dgk92-aerware-ai.vercel.app",
    
    # Railway deployments
    "https://luciantales-production.up.railway.app",
    "https://steadfast-inspiration-production.up.railway.app"
]

# Add any additional origins from environment
env_origins = os.getenv("ALLOWED_ORIGINS", "")
if env_origins:
    for origin in env_origins.split(","):
        origin = origin.strip()
        if origin and origin not in origins:
            origins.append(origin)

# Configure CORS - MUST be before any routes
# Using allow_origin_regex to support Vercel preview deployments
import re

# Create regex pattern for Vercel previews
vercel_preview_pattern = r"https://my-sunshine-stories-.*\.vercel\.app"

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=vercel_preview_pattern,  # This allows all Vercel preview deployments
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,
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
    allowed = origin in origins
    
    return JSONResponse(
        content={
            "origin": origin,
            "allowed": allowed,
            "configured_origins": origins[:5] + ["..."] if len(origins) > 5 else origins,
            "total_origins": len(origins),
            "cors_enabled": True,
            "message": "CORS is properly configured" if allowed else "Origin not in allowed list"
        }
    )

# OPTIONS handler for OAuth endpoints - explicit handler
@app.options("/api/v1/auth/oauth/exchange")
async def oauth_exchange_options():
    """Handle preflight for OAuth exchange endpoint"""
    return JSONResponse(content={"message": "OK"})

# Additional OPTIONS handler for all auth routes
@app.options("/api/v1/auth/{full_path:path}")
async def auth_options_handler():
    """Handle preflight for all auth endpoints"""
    return JSONResponse(content={"message": "OK"})

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
