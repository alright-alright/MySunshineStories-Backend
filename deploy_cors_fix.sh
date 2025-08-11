#!/bin/bash
# Deploy CORS fix to Railway

echo "🚀 Deploying CORS fix to Railway..."

# Commit and push changes
git add -A
git commit -m "URGENT: Complete CORS fix for FastAPI

- Completely rewrote CORS configuration
- Added CORS middleware BEFORE all routes (critical)
- Explicit OPTIONS handlers for all OAuth endpoints
- Added dynamic Vercel preview support
- Simplified configuration for reliability

Critical changes:
- Origins explicitly listed including all production domains
- CORSMiddleware with allow_methods=['*'] to handle OPTIONS
- Explicit OPTIONS route handlers as backup
- Secondary middleware for dynamic Vercel previews

This should completely fix:
- OPTIONS requests returning 400
- Missing CORS headers
- OAuth callback failures"

git push origin main

echo "✅ Changes pushed to GitHub"
echo "📦 Railway should auto-deploy within 2-3 minutes"
echo ""
echo "Test CORS after deployment with:"
echo "curl -H 'Origin: https://mysunshinestories.com' https://luciantales-production.up.railway.app/api/v1/cors-test"