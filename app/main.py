from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
import os

from app.core.database import engine, Base

# Create database tables
Base.metadata.create_all(bind=engine)

# Create FastAPI app
app = FastAPI(
    title="LucianTales API",
    description="Backend API for generating personalized children's stories with AI illustrations",
    version="2.0.0"
)

# CORS Configuration - CRITICAL: Must be added BEFORE routes
origins = [
    # Local development
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:4173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:4173",
    
    # Railway backend (self-reference for testing)
    "https://luciantales-production.up.railway.app",
    
    # Production domains - PRIMARY
    "https://mysunshinestories.com",
    "https://www.mysunshinestories.com",
    
    # Vercel deployments
    "https://my-sunshine-stories-frontend-ojb3dgk92-aerware-ai.vercel.app",
    "https://my-sunshine-stories-frontend.vercel.app",
    "https://mysunshinestories.vercel.app",
    
    # Legacy domains (if still in use)
    "https://mysunshinestory.ai",
    "https://www.mysunshinestory.ai",
    
    # Additional Railway deployments
    "https://steadfast-inspiration-production.up.railway.app",
]

# Add additional origins from environment if provided
env_origins = os.getenv("ALLOWED_ORIGINS", "")
if env_origins:
    for origin in env_origins.split(","):
        origin = origin.strip()
        if origin and origin not in origins:
            origins.append(origin)

# Apply CORS middleware with explicit configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # Explicit list of allowed origins
    allow_credentials=True,  # Allow cookies/auth headers
    allow_methods=["*"],     # Allow all methods including OPTIONS
    allow_headers=["*"],     # Allow all headers
    expose_headers=["*"],    # Expose all headers to the browser
    max_age=3600,           # Cache preflight requests for 1 hour
)

# Create a second middleware for Vercel preview deployments and error handling
@app.middleware("http")
async def add_cors_and_handle_errors(request: Request, call_next):
    """
    Middleware to handle Vercel preview deployments and ensure CORS headers on errors
    """
    origin = request.headers.get("origin")
    
    try:
        # Process the request
        response = await call_next(request)
        
        # Add CORS headers for Vercel preview deployments
        if origin and "vercel.app" in origin and "my-sunshine" in origin:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Methods"] = "*"
            response.headers["Access-Control-Allow-Headers"] = "*"
        
        # Ensure CORS headers are present for OAuth endpoints even on errors
        if "/auth/oauth" in str(request.url) and origin:
            if origin in origins or ("vercel.app" in origin and "my-sunshine" in origin):
                response.headers["Access-Control-Allow-Origin"] = origin
                response.headers["Access-Control-Allow-Credentials"] = "true"
        
        return response
        
    except Exception as e:
        # If an error occurs, create a proper response with CORS headers
        import traceback
        error_detail = str(e) if str(e) else "Internal server error"
        
        # Log the error
        print(f"Error in request {request.url}: {error_detail}")
        print(traceback.format_exc())
        
        # Create error response with CORS headers
        response = JSONResponse(
            status_code=500,
            content={"detail": error_detail}
        )
        
        # Add CORS headers to error response
        if origin and (origin in origins or ("vercel.app" in origin and "my-sunshine" in origin)):
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Methods"] = "*"
            response.headers["Access-Control-Allow-Headers"] = "*"
        
        return response

# Serve static files
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Root endpoint
@app.get("/")
async def root():
    """API Information"""
    return {
        "message": "LucianTales Backend API",
        "status": "operational",
        "version": "2.0.0",
        "cors_enabled": True,
        "documentation": "/docs"
    }

# CORS test endpoint
@app.get("/api/v1/cors-test")
async def cors_test(request: Request):
    """Test CORS configuration"""
    origin = request.headers.get("origin", "No origin header")
    
    return JSONResponse(
        content={
            "origin": origin,
            "allowed": origin in origins or ("vercel.app" in origin and "my-sunshine" in origin),
            "configured_origins_count": len(origins),
            "cors_enabled": True,
            "message": "CORS is working",
            "test_time": os.environ.get("DEPLOYMENT_TIME", "unknown")
        }
    )

# Health check endpoint
@app.get("/api/v1/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "cors_configured": True,
        "origins_count": len(origins)
    }

# Import and include routers AFTER CORS middleware
# print("DEBUG: Starting router imports...")
try:
    from app.api.routes import auth, sunshine, story, subscription, story_v2, story_enhanced, health
    # print(f"DEBUG: Successfully imported sunshine module. Router type: {type(sunshine.router)}")
except Exception as e:
    print(f"ERROR: Failed to import routers: {e}")
    import traceback
    traceback.print_exc()

# Include all routers
# print("DEBUG: Including routers...")
app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["authentication"])
# print(f"DEBUG: About to include sunshine router. Has {len(sunshine.router.routes)} routes")
app.include_router(sunshine.router, prefix="/api/v1/sunshines", tags=["sunshines"])
# print("DEBUG: Sunshine router included")
app.include_router(story.router, prefix="/api/v1", tags=["stories"])
app.include_router(subscription.router, prefix="/api/v1/subscription", tags=["subscription"])
app.include_router(story_v2.router, prefix="/api/v2/stories", tags=["stories-v2"])
app.include_router(story_enhanced.router, prefix="/api/v3/stories", tags=["stories-enhanced"])

# Debug endpoint to test POST directly
@app.post("/api/v1/sunshines/debug")
async def debug_sunshine_post():
    """Debug POST endpoint to verify routing works"""
    return JSONResponse(content={"message": "Direct POST handler works", "endpoint": "/api/v1/sunshines/debug"}, status_code=200)

# Explicit OPTIONS handlers for critical endpoints
@app.options("/api/v1/sunshines")
async def handle_sunshines_preflight():
    """Explicit OPTIONS handler for sunshines endpoint"""
    return JSONResponse(content={"status": "ok", "methods": ["GET", "POST", "OPTIONS"]}, status_code=200)

@app.options("/api/v1/auth/oauth/exchange")
async def handle_oauth_exchange_preflight():
    """Explicit OPTIONS handler for OAuth exchange endpoint"""
    return JSONResponse(content={"status": "ok"}, status_code=200)

@app.options("/api/v1/auth/oauth/login")
async def handle_oauth_login_preflight():
    """Explicit OPTIONS handler for OAuth login endpoint"""
    return JSONResponse(content={"status": "ok"}, status_code=200)

@app.options("/api/v1/{path:path}")
async def handle_all_options(path: str):
    """Catch-all OPTIONS handler for API v1 endpoints"""
    return JSONResponse(content={"status": "ok", "path": path}, status_code=200)


# Debug: Print all registered routes at startup
# Commented out to prevent deployment issues
# print("\n=== REGISTERED ROUTES AT STARTUP ===")
# for route in app.routes:
#     if hasattr(route, 'methods') and hasattr(route, 'path'):
#         print(f"Route: {route.methods} {route.path}")
#         if "sunshines" in route.path:
#             print(f"  ^^ SUNSHINE ROUTE FOUND: {route.methods} {route.path}")

# # Specific check for sunshine POST routes
# sunshine_post_routes = [r for r in app.routes if hasattr(r, 'path') and '/sunshines' in r.path and hasattr(r, 'methods') and 'POST' in r.methods]
# print(f"\nTotal sunshine POST routes found: {len(sunshine_post_routes)}")
# for route in sunshine_post_routes:
#     print(f"  - {route.path}")
# print("=== END ROUTE DEBUG ===\n")


# Routes verified - endpoints working correctly

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
