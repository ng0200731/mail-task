"""
Verification code utility functions for MailTask application.
HHandles verification code generation, storage, and validation using a persistent SQLite backend.
"""
import random
from datetime import datetime, timezone
from config import VERIFICATION_CODE_EXPIRY
from .db_utils import get_db_connection

def generate_verification_code() -> str:
    """
    Generate a random 6-digit numeric verification code.
    
    Returns:
        str: 6-digit numeric code (e.g., "123456")
    """
    return str(random.randint(100000, 999999))

def store_verification_code(email: str, code: str):
    """
    Store verification code in the database with an expiration time.
    Uses INSERT OR REPLACE to handle existing codes for the same email.
    
    Args:
        email (str): Email address (will be normalized to lowercase)
        code (str): Verification code to store
    """
    expires_at = datetime.now(timezone.utc) + VERIFICATION_CODE_EXPIRY
    expires_at_str = expires_at.strftime('%Y-%m-%d %H:%M:%S')
    email_lower = email.lower()
    
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("""
            INSERT INTO verification_codes (email, code, expires_at)
            VALUES (?, ?, ?)
            ON CONFLICT(email) DO UPDATE SET
                code = excluded.code,
                expires_at = excluded.expires_at
        """, (email_lower, code, expires_at_str))
        connection.commit()
    except Exception as e:
        print(f"Error storing verification code in database: {e}")
        if connection:
            connection.rollback()
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

def verify_code(email: str, code: str) -> bool:
    """
    Verify the code for the given email from the database.
    Removes the code after successful verification or if it's expired.
    
    Args:
        email (str): Email address (will be normalized to lowercase)
        code (str): Verification code to verify
    
    Returns:
        bool: True if code is valid and not expired, False otherwise
    """
    email_lower = email.lower()
    now_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        cursor.execute("SELECT code, expires_at FROM verification_codes WHERE email = ?", (email_lower,))
        row = cursor.fetchone()
        
        if not row:
            return False
            
        stored_code = row['code']
        expires_at_str = row['expires_at']
        
        # Check for expiration
        if now_str > expires_at_str:
            # Code expired, remove it
            cursor.execute("DELETE FROM verification_codes WHERE email = ?", (email_lower,))
            connection.commit()
            return False
        
        # Check if code matches
        if stored_code == code:
            # Code verified, remove it
            cursor.execute("DELETE FROM verification_codes WHERE email = ?", (email_lower,))
            connection.commit()
            return True
        
        return False
    except Exception as e:
        print(f"Error verifying code from database: {e}")
        return False
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

def cleanup_expired_codes():
    """
    Remove expired verification codes from the database.
    """
    now_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("DELETE FROM verification_codes WHERE expires_at < ?", (now_str,))
        connection.commit()
    except Exception as e:
        print(f"Error cleaning up expired codes from database: {e}")
        if connection:
            connection.rollback()
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()
