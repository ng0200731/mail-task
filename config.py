"""
Configuration file for MailTask application.
Centralizes all configuration constants and settings.
"""
import os
from pathlib import Path
from datetime import timedelta

# Load environment variables from .env file if it exists
try:
    from dotenv import load_dotenv
    # Always load .env from the project root (same folder as this config.py)
    env_path = Path(__file__).resolve().parent / '.env'
    load_dotenv(dotenv_path=env_path, override=True)
except ImportError:
    pass  # python-dotenv not installed, use system environment variables only

# ============================================================================
# Application Settings
# ============================================================================

# Flask secret key for session management
# In production, SECRET_KEY must be set via environment variable
SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    import secrets
    SECRET_KEY = secrets.token_urlsafe(32)
    import sys
    print("WARNING: SECRET_KEY not set in environment. Generated a random key for this session.", file=sys.stderr)
    print("WARNING: This key will change on restart. Set SECRET_KEY in environment for production.", file=sys.stderr)

# Application version
VERSION = '1.0.81'

# Database path
CUSTOMER_DB_PATH = Path(__file__).resolve().parent / 'mailtask.db'

# ============================================================================
# Email Provider IMAP Configurations
# ============================================================================

GMAIL_CONFIG = {
    'imap_server': 'imap.gmail.com',
    'port': 993,
    'use_ssl': True,
    'use_tls': False,
    'username': os.environ.get('GMAIL_USERNAME', ''),
    'password': os.environ.get('GMAIL_PASSWORD', '')
}

EMAIL163_CONFIG = {
    'imap_server': 'imap.163.com',
    'port': 993,
    'use_ssl': True,
    'use_tls': False,
    'username': os.environ.get('EMAIL163_USERNAME', ''),
    'password': os.environ.get('EMAIL163_PASSWORD', '')
}

LCF_CONFIG = {
    'imap_server': 'imap.qiye.163.com',
    'port': 993,
    'use_ssl': True,
    'use_tls': False,
    'username': os.environ.get('LCF_USERNAME', ''),
    'password': os.environ.get('LCF_PASSWORD', '')
}

QQ_CONFIG = {
    'imap_server': 'imap.qq.com',
    'port': 993,
    'use_ssl': True,
    'use_tls': False,
    'username': '',
    'password': ''
}

# ============================================================================
# SMTP Configurations
# ============================================================================

SMTP_PRIMARY_CONFIG = {
    'name': '163.com SMTP (Backup)',
    'server': 'smtp.163.com',
    'port': 465,
    'use_ssl': True,
    'use_tls': False,
    'username': os.environ.get('EMAIL163_USERNAME', ''),
    'password': os.environ.get('EMAIL163_PASSWORD', ''),
    'sender_name': 'Mail Task',
    'from_address': os.environ.get('EMAIL163_USERNAME', '')
}

SMTP_BACKUP_CONFIG = {
    'name': 'Gmail SMTP (Main)',
    'server': 'smtp.gmail.com',
    'port': 587,
    'use_ssl': False,
    'use_tls': True,
    'username': os.environ.get('GMAIL_USERNAME', ''),
    'password': os.environ.get('GMAIL_PASSWORD', ''),
    'sender_name': 'Mail Task',
    'from_address': os.environ.get('GMAIL_USERNAME', '')
}

SMTP_LCF_CONFIG = {
    'name': 'LCF SMTP',
    'server': 'smtp.qiye.163.com',
    'port': 994,
    'use_ssl': True,
    'use_tls': False,
    'username': os.environ.get('LCF_USERNAME', ''),
    'password': os.environ.get('LCF_PASSWORD', ''),
    'sender_name': 'LCF',
    'from_address': os.environ.get('LCF_USERNAME', '')
}

# Default SMTP configurations list (priority order)
DEFAULT_SMTP_CONFIGS = [SMTP_LCF_CONFIG, SMTP_PRIMARY_CONFIG, SMTP_BACKUP_CONFIG]

# ============================================================================
# Gmail OAuth 2.0 Configuration
# ============================================================================

# Default Flask port (can be overridden via FLASK_PORT environment variable)
# Using 8000 as default for test server
FLASK_PORT = int(os.environ.get('FLASK_PORT', 8000))

GMAIL_OAUTH_CONFIG = {
    'client_id': os.environ.get('GMAIL_CLIENT_ID', ''),
    'client_secret': os.environ.get('GMAIL_CLIENT_SECRET', ''),
    'redirect_uri': os.environ.get('GMAIL_REDIRECT_URI', f'http://localhost:{FLASK_PORT}/oauth2callback'),
    'scopes': ['https://www.googleapis.com/auth/gmail.readonly']
}

# ============================================================================
# Security & Verification Settings
# ============================================================================

# Verification code expiry time
VERIFICATION_CODE_EXPIRY = timedelta(minutes=10)

# SSL/TLS verification settings
# Set to False only for testing with self-signed certificates or enterprise servers
# In production, should be True for security
VERIFY_SSL_CERTIFICATES = os.environ.get('VERIFY_SSL_CERTIFICATES', 'true').lower() == 'true'

