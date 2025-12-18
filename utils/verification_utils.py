"""
Verification code utility functions for MailTask application.
Handles verification code generation, storage, and validation.
"""
import random
import threading
from datetime import datetime
from config import VERIFICATION_CODE_EXPIRY

# Verification code storage (in-memory, expires after configured time)
verification_codes = {}
verification_lock = threading.Lock()


def generate_verification_code() -> str:
    """
    Generate a random 6-digit numeric verification code.
    
    Returns:
        str: 6-digit numeric code (e.g., "123456")
    """
    return str(random.randint(100000, 999999))


def store_verification_code(email: str, code: str):
    """
    Store verification code with expiration time.
    
    Args:
        email (str): Email address (will be normalized to lowercase)
        code (str): Verification code to store
    """
    with verification_lock:
        verification_codes[email.lower()] = {
            'code': code,
            'expires_at': datetime.now() + VERIFICATION_CODE_EXPIRY
        }


def verify_code(email: str, code: str) -> bool:
    """
    Verify the code for the given email.
    Removes the code after successful verification or expiration.
    
    Args:
        email (str): Email address (will be normalized to lowercase)
        code (str): Verification code to verify
    
    Returns:
        bool: True if code is valid and not expired, False otherwise
    """
    email_lower = email.lower()
    with verification_lock:
        if email_lower not in verification_codes:
            return False
        
        stored_data = verification_codes[email_lower]
        if datetime.now() > stored_data['expires_at']:
            # Code expired, remove it
            del verification_codes[email_lower]
            return False
        
        if stored_data['code'] == code:
            # Code verified, remove it
            del verification_codes[email_lower]
            return True
        
        return False


def cleanup_expired_codes():
    """
    Remove expired verification codes from storage.
    Should be called periodically to clean up old codes.
    """
    with verification_lock:
        now = datetime.now()
        expired_emails = [
            email for email, data in verification_codes.items()
            if now > data['expires_at']
        ]
        for email in expired_emails:
            del verification_codes[email]

