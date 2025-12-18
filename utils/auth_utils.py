"""
Authentication utility functions for MailTask application.
Handles user level checking and authentication.
"""
from flask import session, jsonify
from utils.db_utils import get_db_connection


def get_user_level():
    """
    Get current user's level from session.
    
    Returns:
        str or None: User level ('1', '2', '3', etc.) or None if not logged in.
                    Defaults to '1' if user exists but has no level set.
    """
    user_email = session.get('user_email')
    if not user_email:
        return None
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT level FROM users WHERE email = ?", (user_email,))
        user = cursor.fetchone()
        cursor.close()
        connection.close()
        
        if user and user['level']:
            return user['level']
        return '1'  # Default level
    except Exception as e:
        print(f"Error getting user level: {str(e)}")
        return '1'  # Default level


def check_user_level(min_level):
    """
    Check if user has required level for accessing a feature.
    
    Args:
        min_level (int or str): Minimum required level (e.g., 1, 2, 3)
    
    Returns:
        tuple: (is_allowed, response, status_code)
               - is_allowed (bool): True if user has required level, False otherwise
               - response: Flask jsonify response if error, None if allowed
               - status_code: HTTP status code (401 for not authenticated, 403 for insufficient level)
    """
    if not session.get('logged_in'):
        return False, jsonify({'error': 'Not authenticated'}), 401
    
    user_level = get_user_level()
    if not user_level or int(user_level) < int(min_level):
        return False, jsonify({'error': f'Access denied. This feature requires level {min_level} or higher.'}), 403
    
    return True, None, None

