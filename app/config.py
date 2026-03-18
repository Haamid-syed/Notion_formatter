import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key')
    NOTION_CLIENT_ID = os.environ.get('NOTION_CLIENT_ID')
    NOTION_CLIENT_SECRET = os.environ.get('NOTION_CLIENT_SECRET')
    NOTION_REDIRECT_URI = os.environ.get('NOTION_REDIRECT_URI')
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY')
