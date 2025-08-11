# MySunshineTales Backend

🚀 FastAPI backend for MySunshineTales - AI-powered personalized children's story generator.

## 📦 Tech Stack

- **Framework**: FastAPI
- **Database**: PostgreSQL with SQLAlchemy ORM
- **AI**: OpenAI API (GPT-4, DALL-E 3)
- **Authentication**: JWT with OAuth support
- **Payments**: Stripe API
- **File Storage**: Local/S3 compatible
- **Task Queue**: Background tasks for story generation

## 🛠️ Setup & Installation

### Prerequisites

- Python 3.11+
- PostgreSQL 14+ (or SQLite for development)
- OpenAI API key
- Stripe account (optional)
- OAuth credentials (optional)

### Local Development

1. Clone the repository:
```bash
git clone https://github.com/alright-alright/MySunshineStories-Backend.git
cd MySunshineStories-Backend
```

2. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create `.env` file:
```bash
cp .env.example .env
```

5. Configure environment variables:
```env
# Database
DATABASE_URL=postgresql://user:pass@localhost/mysunshinestories
# Or for SQLite: sqlite:///./app.db

# Security
SECRET_KEY=your-secret-key-generate-with-openssl
JWT_ALGORITHM=HS256
JWT_EXPIRATION_DAYS=7

# OpenAI
OPENAI_API_KEY=sk-your-openai-api-key

# Stripe (Optional)
STRIPE_SECRET_KEY=sk_test_your-stripe-key
STRIPE_WEBHOOK_SECRET=whsec_your-webhook-secret
STRIPE_PRICE_ID_MONTHLY=price_monthly
STRIPE_PRICE_ID_YEARLY=price_yearly

# OAuth (Optional)
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
APPLE_CLIENT_ID=your-apple-client-id
APPLE_CLIENT_SECRET=your-apple-client-secret

# CORS
ALLOWED_ORIGINS=http://localhost:5173,https://mysunshinestories.com
```

6. Initialize database:
```bash
alembic upgrade head
```

7. Start development server:
```bash
python run.py
```

The API will be available at `http://localhost:8000`

## 🚢 Deployment

### Railway

1. Connect your GitHub repository to Railway
2. Add PostgreSQL service
3. Configure environment variables in Railway dashboard
4. Railway will auto-deploy on push to main

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