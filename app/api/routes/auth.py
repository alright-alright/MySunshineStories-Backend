"""
Authentication API routes
"""
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, status, Depends, Response, Request
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr

from app.core.dependencies import DatabaseSession, CurrentUser
from app.core.security import create_tokens, create_access_token, decode_token
from app.services.user_service import UserService
from app.services.oauth_service import OAuthService
from app.schemas.user import UserCreate, User as UserSchema, UserWithSubscription

router = APIRouter()

# Add explicit OPTIONS handler for OAuth exchange endpoint
@router.options("/oauth/exchange")
async def oauth_exchange_options():
    """Handle OPTIONS preflight for OAuth exchange endpoint"""
    return JSONResponse(
        content={"message": "OK"},
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Allow-Credentials": "true"
        }
    )


# Request/Response models
class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserSchema


class OAuthLoginRequest(BaseModel):
    token: str
    provider: str  # "google" or "apple"


class OAuthCodeExchangeRequest(BaseModel):
    code: str
    provider: str  # "google" or "apple"
    redirect_uri: str


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str = ""


class RefreshTokenRequest(BaseModel):
    refresh_token: str


@router.post("/register", response_model=LoginResponse)
async def register(
    request: RegisterRequest,
    db: DatabaseSession
):
    """
    Register a new user with email/password
    """
    try:
        # Create user
        user_data = UserCreate(
            email=request.email,
            password=request.password,
            full_name=request.full_name
        )
        user = UserService.create_user(db, user_data)
        
        # Generate tokens
        tokens = create_tokens(user.id, user.email)
        
        return LoginResponse(
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            user=UserSchema.model_validate(user)
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    db: DatabaseSession
):
    """
    Login with email/password
    """
    user = UserService.authenticate_user(db, request.email, request.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Generate tokens
    tokens = create_tokens(user.id, user.email)
    
    return LoginResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        user=UserSchema.model_validate(user)
    )


@router.post("/oauth/login", response_model=LoginResponse)
async def oauth_login(
    request: OAuthLoginRequest,
    db: DatabaseSession
):
    """
    Login with OAuth token (Google or Apple)
    """
    # Demo mode for development
    if request.token == "demo_token":
        # Create or get demo user
        from app.models.user import User
        demo_email = "demo@mysunshinestory.ai"
        user = db.query(User).filter(User.email == demo_email).first()
        
        if not user:
            user = User(
                email=demo_email,
                username="demo_user",
                full_name="Demo User",
                is_verified=True,
                is_active=True,
                oauth_provider=request.provider,
                oauth_provider_id="demo_id"
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        
        # Generate tokens
        tokens = create_tokens(user.id, user.email)
        
        return LoginResponse(
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            user=UserSchema.model_validate(user)
        )
    
    # Verify the OAuth token
    if request.provider.lower() == "google":
        user_data = await OAuthService.verify_google_token(request.token)
    elif request.provider.lower() == "apple":
        user_data = await OAuthService.verify_apple_token(request.token)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OAuth provider"
        )
    
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid OAuth token"
        )
    
    # Create or update user
    user = UserService.create_oauth_user(db, user_data)
    
    # Generate tokens
    tokens = create_tokens(user.id, user.email)
    
    return LoginResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        user=UserSchema.model_validate(user)
    )


@router.post("/oauth/exchange", response_model=LoginResponse)
async def oauth_code_exchange(
    request: OAuthCodeExchangeRequest,
    db: DatabaseSession
):
    """
    Exchange OAuth authorization code for tokens and login
    """
    try:
        # Log the request for debugging
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"OAuth exchange request: provider={request.provider}, redirect_uri={request.redirect_uri}")
        
        # Exchange code for tokens
        token_response = None
        user_data = None
        
        if request.provider.lower() == "google":
            try:
                token_response = await OAuthService.exchange_google_code(
                    request.code, 
                    request.redirect_uri
                )
                if token_response:
                    # Verify the ID token
                    user_data = await OAuthService.verify_google_token(
                        token_response.get("id_token")
                    )
            except Exception as e:
                logger.error(f"Google OAuth exchange failed: {str(e)}")
                # For now, return a more graceful error
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="OAuth service temporarily unavailable. Please try again."
                )
                
        elif request.provider.lower() == "apple":
            try:
                token_response = await OAuthService.exchange_apple_code(
                    request.code,
                    request.redirect_uri
                )
                if token_response:
                    # Verify the ID token
                    user_data = await OAuthService.verify_apple_token(
                        token_response.get("id_token")
                    )
            except Exception as e:
                logger.error(f"Apple OAuth exchange failed: {str(e)}")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="OAuth service temporarily unavailable. Please try again."
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid OAuth provider"
            )
        
        # If OAuth service is not configured, use demo mode
        if not user_data:
            # Check if we're in demo mode
            if not token_response:
                # Demo mode - create a demo user
                logger.info("OAuth not configured, using demo mode")
                from app.models.user import User
                demo_email = f"demo_{request.provider}@mysunshinestories.com"
                
                # Check if demo user exists
                user = db.query(User).filter(User.email == demo_email).first()
                if not user:
                    user = User(
                        email=demo_email,
                        username=f"demo_{request.provider}_user",
                        full_name="Demo User",
                        is_verified=True,
                        is_active=True,
                        oauth_provider=request.provider,
                        oauth_provider_id=f"demo_{request.provider}_id"
                    )
                    db.add(user)
                    db.commit()
                    db.refresh(user)
                
                # Generate tokens for demo user
                tokens = create_tokens(user.id, user.email)
                
                return LoginResponse(
                    access_token=tokens["access_token"],
                    refresh_token=tokens["refresh_token"],
                    user=UserSchema.model_validate(user)
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="OAuth authentication failed"
                )
        
        # Create or update user
        user = UserService.create_oauth_user(db, user_data)
        
        # Generate tokens
        tokens = create_tokens(user.id, user.email)
        
        return LoginResponse(
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            user=UserSchema.model_validate(user)
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Log unexpected errors
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Unexpected error in OAuth exchange: {str(e)}")
        
        # Return a generic error with CORS-safe status
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during authentication"
        )


@router.post("/refresh", response_model=Dict[str, str])
async def refresh_token(
    request: RefreshTokenRequest,
    db: DatabaseSession
):
    """
    Refresh access token using refresh token
    """
    # Decode refresh token
    payload = decode_token(request.refresh_token)
    
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    user_id = payload.get("sub")
    email = payload.get("email")
    
    if not user_id or not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )
    
    # Verify user still exists
    user = UserService.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Generate new access token
    token_data = {"sub": user_id, "email": email}
    new_access_token = create_access_token(token_data)
    
    return {
        "access_token": new_access_token,
        "token_type": "bearer"
    }


@router.get("/me", response_model=UserWithSubscription)
async def get_current_user_profile(
    current_user: CurrentUser,
    db: DatabaseSession
):
    """
    Get current user profile with subscription info
    """
    # Load subscription
    db.refresh(current_user)
    
    # Build response with proper subscription handling
    from app.schemas.subscription import SubscriptionResponse
    
    user_data = {
        "id": current_user.id,
        "email": current_user.email,
        "username": current_user.username,
        "full_name": current_user.full_name,
        "is_active": current_user.is_active,
        "is_verified": current_user.is_verified,
        "is_admin": current_user.is_admin,
        "created_at": current_user.created_at,
        "updated_at": current_user.updated_at,
        "last_login": current_user.last_login,
        "subscription": SubscriptionResponse.from_orm_model(current_user.subscription) if current_user.subscription else None,
        "sunshines": current_user.sunshines
    }
    
    return UserWithSubscription(**user_data)


@router.post("/logout")
async def logout(
    current_user: CurrentUser,
    response: Response
):
    """
    Logout current user (client should remove tokens)
    """
    # In a more complex system, you might want to:
    # - Add the token to a blacklist
    # - Clear server-side sessions
    # - Log the logout event
    
    # For now, just return success
    # The client should remove the tokens from storage
    response.status_code = status.HTTP_204_NO_CONTENT
    return {"message": "Successfully logged out"}


@router.delete("/account")
async def delete_account(
    current_user: CurrentUser,
    db: DatabaseSession
):
    """
    Delete current user account
    """
    # Delete user (cascades to related records)
    db.delete(current_user)
    db.commit()
    
    return {"message": "Account successfully deleted"}