import uvicorn
import os
from dotenv import load_dotenv

if __name__ == "__main__":
    load_dotenv()
    
    # Validate environment
    required_vars = ["OPENAI_API_KEY"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"Error: Missing required environment variables: {', '.join(missing_vars)}")
        print("Please check your .env file")
        exit(1)
    
    print("Starting LucianTales API server...")
    print("Make sure to copy .env.example to .env and add your OpenAI API key")
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0", 
        port=int(os.getenv("PORT", 8000)),
        reload=True
    )
