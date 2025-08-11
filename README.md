# LucianTales Backend

FastAPI backend for MySunshineStories - AI-powered personalized children's story generator.

## Tech Stack
- FastAPI
- SQLAlchemy
- PostgreSQL/SQLite
- OpenAI API (GPT-4, DALL-E 3)
- Stripe API
- JWT Authentication

## Setup

### Environment Variables
Create `.env` file:
```
OPENAI_API_KEY=your_openai_key
SECRET_KEY=your_secret_key
DATABASE_URL=postgresql://user:pass@host/db
STRIPE_SECRET_KEY=your_stripe_key
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
```

### Installation
```bash
pip install -r requirements.txt
```

### Database Setup
```bash
alembic upgrade head
```

### Development
```bash
python run.py
```

### Production
```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

## API Documentation
Once running, visit `/docs` for interactive API documentation.

## Deployment to Railway

1. Connect this repository to Railway
2. Add environment variables (especially OPENAI_API_KEY)
3. Railway will auto-deploy on push to main

## API Endpoints
- `/api/v1/auth` - Authentication
- `/api/v1/sunshines` - Sunshine profiles CRUD
- `/api/v1/stories` - Story generation
- `/api/v1/subscription` - Stripe subscriptions

## CORS Configuration
Update `app/main.py` to add your frontend URL to allowed origins.