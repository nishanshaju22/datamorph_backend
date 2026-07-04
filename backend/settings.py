import os
import dj_database_url
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Base
BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get(
    "SECRET_KEY",
    "django-insecure-rn1)^4-lg)bctp-4(zzxtr@qjm*85%)(yr@g1+x)rjkb2uv7#y"
)

DEBUG = os.environ.get("DEBUG", "True").lower() == "true"

ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

# Database — SQLite locally, PostgreSQL in production
DATABASE_URL = os.environ.get("DATABASE_URL", "")

if DATABASE_URL:
    ssl_required = "neon.tech" in DATABASE_URL

    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=600,
            ssl_require=ssl_required,
        )
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

DATABASES["default"]["CONN_HEALTH_CHECKS"] = True

# Installed apps
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "django_celery_results",
    "uploads",
    "jobs",
    "processing",
]

# Middleware
MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "backend.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "backend.wsgi.application"

# CORS
CORS_ALLOW_CREDENTIALS = True

CORS_ALLOWED_ORIGINS = [
    "https://datamorph-frontend.vercel.app",
    "http://localhost:5173",
]

CSRF_TRUSTED_ORIGINS = [
    "https://datamorph-frontend.vercel.app",
]

CORS_EXPOSE_HEADERS = ["Content-Type", "X-CSRFToken"]
CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
    "x-client-id",
]

# Sessions
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_SAMESITE = "None" 
SESSION_COOKIE_SECURE = True
SESSION_SAVE_EVERY_REQUEST = True

# Redis
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
        "TIMEOUT": 60 * 60 * 24,
        "KEY_PREFIX": "datamorph",
    }
}

LLM_CACHE_TIMEOUT = 60 * 60 * 24 * 7   # 7 days

# Only add SSL config for Upstash (rediss://) not Railway internal Redis (redis://)
if REDIS_URL.startswith("rediss://"):
    CELERY_BROKER_USE_SSL = {"ssl_cert_reqs": "none"}
    CELERY_REDIS_BACKEND_USE_SSL  = {"ssl_cert_reqs": "none"}

# Celery
CELERY_BROKER_URL            = REDIS_URL
CELERY_RESULT_BACKEND        = REDIS_URL
CELERY_ACCEPT_CONTENT        = ["json"]
CELERY_TASK_SERIALIZER       = "json"
CELERY_RESULT_SERIALIZER     = "json"
CELERY_TIMEZONE              = "UTC"
CELERY_RESULT_EXTENDED       = True
CELERY_RESULT_EXPIRES        = 60 * 60 * 24
CELERY_TASK_MAX_RETRIES      = 3
CELERY_TASK_DEFAULT_RETRY_DELAY = 5
CELERY_TASK_SOFT_TIME_LIMIT  = 60 * 30
CELERY_TASK_TIME_LIMIT       = 60 * 35

# File uploads
MEDIA_ROOT  = os.environ.get("MEDIA_ROOT", os.path.join(BASE_DIR, "media"))
UPLOAD_DIR  = os.path.join(MEDIA_ROOT, "uploads")
RESULTS_DIR = os.path.join(MEDIA_ROOT, "results")

DATA_UPLOAD_MAX_MEMORY_SIZE = 500 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 500 * 1024 * 1024

ALLOWED_UPLOAD_EXTENSIONS = [".csv", ".xlsx", ".xls"]

# LLM
HUGGINGFACE_API_KEY = os.environ.get("HUGGINGFACE_API_KEY", "")
MODEL = os.environ.get("HUGGINGFACE_MODEL", "meta-llama/Llama-3.1-8B-Instruct")

# Static files
STATIC_URL  = "/static/"
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Internationalisation
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"