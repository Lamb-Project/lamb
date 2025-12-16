import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Server Configuration
DEV_MODE = os.getenv('DEV_MODE', 'false').lower() == 'false'

# LAMB Host Configuration
# LAMB_WEB_HOST: External/public URL for browser-side requests (e.g., https://lamb.yourdomain.com in production)
# LAMB_BACKEND_HOST: Internal loopback URL for server-side requests (e.g., http://localhost:9099)
# PIPELINES_HOST: Legacy variable, falls back to LAMB_WEB_HOST for backward compatibility
LAMB_WEB_HOST = os.getenv('LAMB_WEB_HOST') or os.getenv('PIPELINES_HOST')
if not LAMB_WEB_HOST:
    raise ValueError("LAMB_WEB_HOST or PIPELINES_HOST environment variable is required")
LAMB_BACKEND_HOST = os.getenv('LAMB_BACKEND_HOST')
if not LAMB_BACKEND_HOST:
    raise ValueError("LAMB_BACKEND_HOST environment variable is required")
LAMB_HOST = LAMB_WEB_HOST  # Legacy alias for backward compatibility

# Get the token from environment and strip any whitespace
# LAMB_BEARER_TOKEN is the new variable name, PIPELINES_BEARER_TOKEN is kept for backward compatibility
lamb_token = os.getenv('LAMB_BEARER_TOKEN') or os.getenv('PIPELINES_BEARER_TOKEN')
if not lamb_token:
    raise ValueError("LAMB_BEARER_TOKEN or PIPELINES_BEARER_TOKEN environment variable is required")
lamb_token = lamb_token.strip()

LAMB_BEARER_TOKEN = lamb_token
PIPELINES_BEARER_TOKEN = lamb_token  # Legacy alias for backward compatibility
PIPELINES_DIR = os.getenv("PIPELINES_DIR", "./lamb_assistants")
 
API_KEY = lamb_token
# Ollama Configuration

OLLAMA_BASE_URL = os.getenv('OLLAMA_BASE_URL', 'http://host.docker.internal:11434')

OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'nomic-embed-text')

# OpenAI Configuration
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_BASE_URL = os.getenv('OPENAI_BASE_URL')
if not OPENAI_BASE_URL:
    raise ValueError("OPENAI_BASE_URL environment variable is required")
OPENAI_MODEL = os.getenv('OPENAI_MODEL')
if not OPENAI_MODEL:
    raise ValueError("OPENAI_MODEL environment variable is required")

# Openwebui Authentication
OWI_PATH = os.getenv('OWI_PATH')
# OWI_BASE_URL: Internal URL for backend-to-OpenWebUI API calls
OWI_BASE_URL = os.getenv('OWI_BASE_URL')
if not OWI_BASE_URL:
    raise ValueError("OWI_BASE_URL environment variable is required")
# OWI_PUBLIC_BASE_URL: Public URL for browser-facing redirects and login URLs
# Falls back to OWI_BASE_URL if not explicitly set
OWI_PUBLIC_BASE_URL = os.getenv('OWI_PUBLIC_BASE_URL') or OWI_BASE_URL
CHROMA_PATH = os.path.join(OWI_PATH, "vector_db") 

# Database Configuration
LAMB_DB_PATH = os.getenv('LAMB_DB_PATH')
LAMB_DB_PREFIX = os.getenv('LAMB_DB_PREFIX', '')

# Logging Configuration
GLOBAL_LOG_LEVEL = os.getenv('GLOBAL_LOG_LEVEL', 'WARNING')

# Individual module log levels (overrides GLOBAL_LOG_LEVEL if set)
MAIN_LOG_LEVEL = os.getenv('MAIN_LOG_LEVEL') or GLOBAL_LOG_LEVEL
API_LOG_LEVEL = os.getenv('API_LOG_LEVEL') or GLOBAL_LOG_LEVEL
DB_LOG_LEVEL = os.getenv('DB_LOG_LEVEL') or GLOBAL_LOG_LEVEL
RAG_LOG_LEVEL = os.getenv('RAG_LOG_LEVEL') or GLOBAL_LOG_LEVEL
EVALUATOR_LOG_LEVEL = os.getenv('EVALUATOR_LOG_LEVEL') or GLOBAL_LOG_LEVEL
OWI_LOG_LEVEL = os.getenv('OWI_LOG_LEVEL') or GLOBAL_LOG_LEVEL


# Signup Configuration
SIGNUP_ENABLED = os.getenv('SIGNUP_ENABLED', 'false').lower() == 'true'
SIGNUP_SECRET_KEY = os.getenv('SIGNUP_SECRET_KEY')
if not SIGNUP_SECRET_KEY:
    raise ValueError("SIGNUP_SECRET_KEY environment variable is required")

# OWI Admin Configuration
OWI_ADMIN_NAME = os.getenv('OWI_ADMIN_NAME')
if not OWI_ADMIN_NAME:
    raise ValueError("OWI_ADMIN_NAME environment variable is required")
OWI_ADMIN_EMAIL = os.getenv('OWI_ADMIN_EMAIL')
if not OWI_ADMIN_EMAIL:
    raise ValueError("OWI_ADMIN_EMAIL environment variable is required")
OWI_ADMIN_PASSWORD = os.getenv('OWI_ADMIN_PASSWORD')
if not OWI_ADMIN_PASSWORD:
    raise ValueError("OWI_ADMIN_PASSWORD environment variable is required")

# Validate required environment variables
required_vars = ['LAMB_DB_PATH', 'OWI_PATH']
missing_vars = [var for var in required_vars if not os.getenv(var)]
if missing_vars:
    raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
