#!/usr/bin/env python3
"""
Licensing Server Configuration

Supports environment-based configuration for dev/prod deployment.
Uses environment variables with sensible defaults.

Environment Variables:
    LICENSING_ENV: dev | prod (default: dev)
    LICENSING_API_KEY: API key for authentication (default: dev-key-12345)
    LICENSING_DATABASE_URL: Database connection string (default: SQLite local)
    LICENSING_SERVER_HOST: Server host (default: 127.0.0.1)
    LICENSING_SERVER_PORT: Server port (default: 8000)
    LICENSING_SECRET_KEY: HMAC-SHA256 secret for PQTI licenses (default: dev-secret)
    LICENSING_LOG_LEVEL: DEBUG | INFO | WARNING | ERROR (default: INFO)
"""

import os
import logging
from pathlib import Path
from enum import Enum


class Environment(str, Enum):
    DEV = "dev"
    PROD = "prod"


# ============================================================================
# Configuration
# ============================================================================

# Environment
ENV = Environment(os.getenv("LICENSING_ENV", "dev").lower())
IS_PRODUCTION = ENV == Environment.PROD
IS_DEVELOPMENT = ENV == Environment.DEV

# Server
SERVER_HOST = os.getenv("LICENSING_SERVER_HOST", "127.0.0.1")
SERVER_PORT = int(os.getenv("LICENSING_SERVER_PORT", "8000"))

# Database
DATABASE_URL = os.getenv("LICENSING_DATABASE_URL", None)
if not DATABASE_URL:
    # Default to SQLite in user's home directory
    db_dir = Path.home() / ".silver_wizard"
    db_name = "licensing_prod.db" if IS_PRODUCTION else "licensing_test.db"
    DATABASE_URL = f"sqlite:///{db_dir / db_name}"

# Authentication
LICENSING_API_KEY = os.getenv("LICENSING_API_KEY", "dev-key-12345")

# PQTI License Signing
PQTI_SECRET_KEY = os.getenv("LICENSING_SECRET_KEY", "dev-secret-key-change-in-production")

# Logging
LOG_LEVEL = os.getenv("LICENSING_LOG_LEVEL", "INFO" if IS_PRODUCTION else "DEBUG")

# Feature Trial Defaults (per-feature duration)
# Maps feature_idx to default trial duration in days
DEFAULT_TRIAL_DURATIONS = {
    0: 0,      # VIDEO_RECORDING: no trial
    1: 0,      # OFFLINE_STORAGE: no trial
    2: 30,     # MUTATION_TESTING: 30-day trial
    3: 14,     # REMOTE_EXECUTION: 14-day trial
    4: 14,     # SESSION_RECORDING: 14-day trial
}

# ============================================================================
# Logging Setup
# ============================================================================

def configure_logging():
    """Configure Python logging."""
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)


logger = configure_logging()


# ============================================================================
# Configuration Validation & Display
# ============================================================================

def validate_config():
    """Validate configuration and warn about insecure settings."""
    if IS_PRODUCTION:
        if PQTI_SECRET_KEY == "dev-secret-key-change-in-production":
            logger.warning("⚠️  PRODUCTION MODE: Using default PQTI secret key! Set LICENSING_SECRET_KEY env var")
        if LICENSING_API_KEY == "dev-key-12345":
            logger.warning("⚠️  PRODUCTION MODE: Using default API key! Set LICENSING_API_KEY env var")
        if SERVER_HOST == "127.0.0.1":
            logger.warning("⚠️  PRODUCTION MODE: Server only listening on localhost! Set LICENSING_SERVER_HOST")
    logger.info(f"Licensing Server Configuration")
    logger.info(f"  Environment: {ENV.value}")
    logger.info(f"  Server: {SERVER_HOST}:{SERVER_PORT}")
    logger.info(f"  Database: {DATABASE_URL}")
    logger.info(f"  API Key: {LICENSING_API_KEY[:10]}...")
    logger.info(f"  Log Level: {LOG_LEVEL}")


if __name__ == "__main__":
    print("Licensing Server Configuration")
    print("=" * 60)
    print(f"Environment: {ENV.value}")
    print(f"Server: {SERVER_HOST}:{SERVER_PORT}")
    print(f"Database: {DATABASE_URL}")
    print(f"API Key (first 10 chars): {LICENSING_API_KEY[:10]}...")
    print(f"Log Level: {LOG_LEVEL}")
    print(f"Is Production: {IS_PRODUCTION}")
    print(f"Is Development: {IS_DEVELOPMENT}")
    print("=" * 60)
