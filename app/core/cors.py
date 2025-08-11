"""
CORS Configuration for MySunshineTales Backend
"""
import os
import re
from typing import List

def get_allowed_origins() -> List[str]:
    """
    Get list of allowed origins for CORS
    """
    # Default allowed origins
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
    
    # Add origins from environment variable
    env_origins = os.getenv("ALLOWED_ORIGINS", "")
    if env_origins:
        additional = [o.strip() for o in env_origins.split(",") if o.strip()]
        origins.extend(additional)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_origins = []
    for origin in origins:
        if origin not in seen:
            seen.add(origin)
            unique_origins.append(origin)
    
    return unique_origins

def is_vercel_preview_deployment(origin: str) -> bool:
    """
    Check if origin is a Vercel preview deployment
    """
    if not origin:
        return False
    
    # Pattern for Vercel preview deployments
    patterns = [
        r"https://my-sunshine-stories-frontend-[a-z0-9]+-aerware-ai\.vercel\.app",
        r"https://mysunshinestories-[a-z0-9]+-aerware-ai\.vercel\.app",
        r"https://[a-z0-9-]+-aerware-ai\.vercel\.app"
    ]
    
    for pattern in patterns:
        if re.match(pattern, origin):
            return True
    
    return False

def should_allow_origin(origin: str, allowed_origins: List[str]) -> bool:
    """
    Check if an origin should be allowed
    """
    if not origin:
        return False
    
    # Check exact match
    if origin in allowed_origins:
        return True
    
    # Check if it's a Vercel preview deployment
    if is_vercel_preview_deployment(origin):
        return True
    
    # Check for development mode (allow all in dev)
    if os.getenv("ENVIRONMENT", "production").lower() == "development":
        return True
    
    return False

# CORS configuration
CORS_CONFIG = {
    "allow_credentials": True,
    "allow_methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    "allow_headers": ["*"],
    "expose_headers": ["*"],
    "max_age": 3600
}