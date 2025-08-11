from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
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

# CORS middleware
# Configure allowed origins based on environment
allowed_origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:4173",
    "https://luciantales-production.up.railway.app",
    "https://mysunshinestory.ai",
    "https://www.mysunshinestory.ai"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"]
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
