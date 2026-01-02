"""
OAuth utility functions for MailTask application.
Handles OAuth token storage and retrieval for Gmail API.
"""
import json
from typing import Optional
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from utils.db_utils import get_db_connection


def save_oauth_token(provider: str, creds: Credentials):
    """
    Save OAuth token to database.
    
    Args:
        provider (str): OAuth provider name (e.g., 'gmail')
        creds (Credentials): Google OAuth2 credentials object
    """
    connection = get_db_connection()
    cursor = connection.cursor()
    token_dict = {
        'token': creds.token,
        'refresh_token': creds.refresh_token,
        'token_uri': creds.token_uri,
        'client_id': creds.client_id,
        'client_secret': creds.client_secret,
        'scopes': json.dumps(creds.scopes) if creds.scopes else '[]'
    }
    cursor.execute("""
        INSERT INTO oauth_tokens (provider, token, refresh_token, token_uri, client_id, client_secret, scopes, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(provider) DO UPDATE SET
            token = excluded.token,
            refresh_token = excluded.refresh_token,
            token_uri = excluded.token_uri,
            client_id = excluded.client_id,
            client_secret = excluded.client_secret,
            scopes = excluded.scopes,
            updated_at = datetime('now')
    """, (provider, token_dict['token'], token_dict['refresh_token'], token_dict['token_uri'],
          token_dict['client_id'], token_dict['client_secret'], token_dict['scopes']))
    connection.commit()
    cursor.close()
    connection.close()


def load_oauth_token(provider: str) -> Optional[Credentials]:
    """
    Load OAuth token from database and refresh if expired.
    
    Args:
        provider (str): OAuth provider name (e.g., 'gmail')
    
    Returns:
        Optional[Credentials]: Google OAuth2 credentials object, or None if not found or invalid
    """
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM oauth_tokens WHERE provider = ?", (provider,))
    row = cursor.fetchone()
    cursor.close()
    connection.close()
    
    if not row:
        return None
    
    try:
        scopes = json.loads(row['scopes']) if row['scopes'] else []
        creds = Credentials(
            token=row['token'],
            refresh_token=row['refresh_token'],
            token_uri=row['token_uri'] or 'https://oauth2.googleapis.com/token',
            client_id=row['client_id'],
            client_secret=row['client_secret'],
            scopes=scopes
        )
        
        # Refresh token if expired
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                save_oauth_token(provider, creds)
            except Exception as refresh_error:
                error_str = str(refresh_error)
                # If refresh token is invalid/revoked, clear the token from database
                if 'invalid_grant' in error_str.lower() or 'token has been expired' in error_str.lower() or 'revoked' in error_str.lower():
                    print(f"OAuth token refresh failed (token expired/revoked): {refresh_error}")
                    # Clear the invalid token from database
                    cleanup_connection = None
                    cleanup_cursor = None
                    try:
                        cleanup_connection = get_db_connection()
                        cleanup_cursor = cleanup_connection.cursor()
                        cleanup_cursor.execute("DELETE FROM oauth_tokens WHERE provider = ?", (provider,))
                        cleanup_connection.commit()
                    except Exception as cleanup_error:
                        print(f"Error cleaning up OAuth token: {cleanup_error}")
                    finally:
                        if cleanup_cursor:
                            cleanup_cursor.close()
                        if cleanup_connection:
                            cleanup_connection.close()
                raise refresh_error
        
        return creds
    except Exception as e:
        print(f"Error loading OAuth token: {e}")
        return None

