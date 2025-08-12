"""
OAuth service for Google and Apple authentication
"""
from typing import Optional, Dict, Any
import httpx
from google.oauth2 import id_token
from google.auth.transport import requests
import jwt
import json
from datetime import datetime

from app.core.config import settings
from app.schemas.user import UserOAuthCreate


class OAuthService:
    """Service for OAuth authentication"""
    
    @staticmethod
    async def verify_google_token(token: str) -> Optional[UserOAuthCreate]:
        """
        Verify Google OAuth token and extract user information
        
        Args:
            token: Google ID token
        
        Returns:
            UserOAuthCreate object with user data or None if invalid
        """
        try:
            # Verify the token with Google
            idinfo = id_token.verify_oauth2_token(
                token, 
                requests.Request(), 
                settings.GOOGLE_CLIENT_ID
            )
            
            # Token is valid, extract user info
            return UserOAuthCreate(
                email=idinfo.get("email"),
                google_id=idinfo.get("sub"),
                full_name=idinfo.get("name"),
                avatar_url=idinfo.get("picture"),
                username=idinfo.get("email", "").split("@")[0]
            )
            
        except ValueError as e:
            # Invalid token
            print(f"Google token verification failed: {e}")
            return None
        except Exception as e:
            print(f"Error verifying Google token: {e}")
            return None
    
    @staticmethod
    async def verify_apple_token(token: str) -> Optional[UserOAuthCreate]:
        """
        Verify Apple OAuth token and extract user information
        
        Args:
            token: Apple ID token
        
        Returns:
            UserOAuthCreate object with user data or None if invalid
        """
        try:
            # Fetch Apple's public keys
            async with httpx.AsyncClient() as client:
                response = await client.get("https://appleid.apple.com/auth/keys")
                apple_keys = response.json()["keys"]
            
            # Decode the token header to get the key ID
            header = jwt.get_unverified_header(token)
            kid = header["kid"]
            
            # Find the matching public key
            public_key = None
            for key in apple_keys:
                if key["kid"] == kid:
                    public_key = key
                    break
            
            if not public_key:
                return None
            
            # Verify and decode the token
            decoded = jwt.decode(
                token,
                public_key,
                algorithms=["RS256"],
                audience=settings.APPLE_CLIENT_ID,
                issuer="https://appleid.apple.com"
            )
            
            # Extract user info
            return UserOAuthCreate(
                email=decoded.get("email"),
                apple_id=decoded.get("sub"),
                full_name=decoded.get("name", {}).get("firstName", "") + " " + decoded.get("name", {}).get("lastName", ""),
                username=decoded.get("email", "").split("@")[0]
            )
            
        except jwt.InvalidTokenError as e:
            print(f"Apple token verification failed: {e}")
            return None
        except Exception as e:
            print(f"Error verifying Apple token: {e}")
            return None
    
    @staticmethod
    async def exchange_google_code(code: str, redirect_uri: str) -> Optional[Dict[str, Any]]:
        """
        Exchange Google authorization code for tokens
        
        Args:
            code: Authorization code from Google
            redirect_uri: Redirect URI used in the authorization request
        
        Returns:
            Dictionary with tokens or None if failed
        """
        try:
            # Check if credentials are configured
            if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
                print("WARNING: Google OAuth credentials not configured")
                print(f"Client ID exists: {bool(settings.GOOGLE_CLIENT_ID)}")
                print(f"Client Secret exists: {bool(settings.GOOGLE_CLIENT_SECRET)}")
                return None
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://oauth2.googleapis.com/token",
                    data={
                        "code": code,
                        "client_id": settings.GOOGLE_CLIENT_ID,
                        "client_secret": settings.GOOGLE_CLIENT_SECRET,
                        "redirect_uri": redirect_uri,
                        "grant_type": "authorization_code"
                    }
                )
                
                if response.status_code == 200:
                    return response.json()
                
                print(f"Google code exchange failed with status {response.status_code}: {response.text}")
                # Log more details about the error
                if response.status_code == 400:
                    error_data = response.json()
                    print(f"Error details: {error_data}")
                    if "invalid_client" in str(error_data):
                        print("CRITICAL: Invalid client credentials - check GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET")
                return None
                
        except Exception as e:
            print(f"Error exchanging Google code: {e}")
            import traceback
            print(traceback.format_exc())
            return None
    
    @staticmethod
    async def exchange_apple_code(code: str, redirect_uri: str) -> Optional[Dict[str, Any]]:
        """
        Exchange Apple authorization code for tokens
        
        Args:
            code: Authorization code from Apple
            redirect_uri: Redirect URI used in the authorization request
        
        Returns:
            Dictionary with tokens or None if failed
        """
        try:
            # Generate client secret for Apple (JWT)
            client_secret = OAuthService._generate_apple_client_secret()
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://appleid.apple.com/auth/token",
                    data={
                        "code": code,
                        "client_id": settings.APPLE_CLIENT_ID,
                        "client_secret": client_secret,
                        "redirect_uri": redirect_uri,
                        "grant_type": "authorization_code"
                    }
                )
                
                if response.status_code == 200:
                    return response.json()
                
                print(f"Apple code exchange failed: {response.text}")
                return None
                
        except Exception as e:
            print(f"Error exchanging Apple code: {e}")
            return None
    
    @staticmethod
    def _generate_apple_client_secret() -> str:
        """
        Generate Apple client secret (JWT)
        
        Apple requires a JWT as the client secret
        """
        # This would need the Apple private key
        # For now, returning a placeholder
        # In production, you'd generate this properly with your Apple private key
        return settings.APPLE_CLIENT_SECRET or ""