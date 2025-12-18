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
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, use system environment variables only

# ============================================================================
# Application Settings
# ============================================================================

# Flask secret key for session management
SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

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
    'username': os.environ.get('LCF_USERNAME', 'weiwu@fuchanghk.com'),
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
    'username': os.environ.get('EMAIL163_USERNAME', '19902475292@163.com'),
    'password': os.environ.get('EMAIL163_PASSWORD', 'JDy8MigeNmsESZRa'),
    'sender_name': 'Mail Task',
    'from_address': os.environ.get('EMAIL163_USERNAME', '19902475292@163.com')
}

SMTP_BACKUP_CONFIG = {
    'name': 'Gmail SMTP (Main)',
    'server': 'smtp.gmail.com',
    'port': 587,
    'use_ssl': False,
    'use_tls': True,
    'username': os.environ.get('GMAIL_USERNAME', 'eric.brilliant@gmail.com'),
    'password': os.environ.get('GMAIL_PASSWORD', 'opqx pfna kagb bznr'),
    'sender_name': 'Mail Task',
    'from_address': os.environ.get('GMAIL_USERNAME', 'eric.brilliant@gmail.com')
}

SMTP_LCF_CONFIG = {
    'name': 'LCF SMTP',
    'server': 'smtp.qiye.163.com',
    'port': 994,
    'use_ssl': True,
    'use_tls': False,
    'username': os.environ.get('LCF_USERNAME', 'weiwu@fuchanghk.com'),
    'password': os.environ.get('LCF_PASSWORD', ''),
    'sender_name': 'LCF',
    'from_address': os.environ.get('LCF_USERNAME', 'weiwu@fuchanghk.com')
}

# Default SMTP configurations list (priority order)
DEFAULT_SMTP_CONFIGS = [SMTP_LCF_CONFIG, SMTP_PRIMARY_CONFIG, SMTP_BACKUP_CONFIG]

# ============================================================================
# Gmail OAuth 2.0 Configuration
# ============================================================================

GMAIL_OAUTH_CONFIG = {
    'client_id': os.environ.get('GMAIL_CLIENT_ID', ''),
    'client_secret': os.environ.get('GMAIL_CLIENT_SECRET', ''),
    'redirect_uri': os.environ.get('GMAIL_REDIRECT_URI', 'http://localhost:5000/oauth2callback'),
    'scopes': ['https://www.googleapis.com/auth/gmail.readonly']
}

# ============================================================================
# Security & Verification Settings
# ============================================================================

# Verification code expiry time
VERIFICATION_CODE_EXPIRY = timedelta(minutes=10)

