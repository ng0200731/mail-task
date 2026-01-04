from flask import Flask, render_template, jsonify, request, redirect, session, url_for, send_file
from functools import wraps
import imaplib
import email
from email.header import decode_header
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, date, timedelta
from typing import Optional
import ssl
import smtplib
import re
import os
import json
import base64
from pathlib import Path
import sqlite3
import random
import threading
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Import configuration from centralized config file
from config import (
    SECRET_KEY,
    VERSION,
    CUSTOMER_DB_PATH,
    GMAIL_CONFIG,
    EMAIL163_CONFIG,
    LCF_CONFIG,
    QQ_CONFIG,
    SMTP_PRIMARY_CONFIG,
    SMTP_BACKUP_CONFIG,
    SMTP_LCF_CONFIG,
    DEFAULT_SMTP_CONFIGS,
    GMAIL_OAUTH_CONFIG,
    VERIFICATION_CODE_EXPIRY,
    FLASK_PORT
)

# Import database utilities
from utils.db_utils import get_db_connection, initialize_database

# Import authentication utilities
from utils.auth_utils import get_user_level, check_user_level

# Import email parsing utilities
from utils.email_parser import decode_mime_words, strip_html_tags, build_sequence_code

# Import SMTP utilities
from utils.smtp_utils import build_smtp_config_list, send_email_with_configs

# Import OAuth utilities
from utils.oauth_utils import save_oauth_token, load_oauth_token

# Import verification utilities
from utils.verification_utils import generate_verification_code, store_verification_code, verify_code, cleanup_expired_codes

# Import export utilities
from utils.export_utils import export_customers_to_excel, export_tasks_to_excel

# Import email fetching utilities
from utils.email_fetcher import fetch_gmail_api, fetch_emails

# Import email model
from models.email_model import save_emails

# Import customer model
from models.customer_model import insert_customer, fetch_customers

app = Flask(__name__)
app.config['VERSION'] = VERSION
app.secret_key = SECRET_KEY


def validate_email(email_str):
    """
    Validate email address format using regex.
    
    Args:
        email_str (str): Email address to validate
    
    Returns:
        bool: True if valid, False otherwise
    """
    if not email_str or not isinstance(email_str, str):
        return False
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(email_pattern, email_str.strip()))


@app.route('/login')
def login():
    """Login page"""
    return render_template('login.html')


@app.route('/favicon.ico')
def favicon():
    """Serve favicon"""
    # Return a simple 204 No Content to prevent 404 errors
    # You can replace this with an actual favicon file if needed
    return '', 204


@app.route('/')
def index():
    """Main page - requires login"""
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    user_email = session.get('user_email', '')
    
    # Get user level from database
    user_level = '1'  # Default level
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT level FROM users WHERE email = ?", (user_email,))
        user = cursor.fetchone()
        if user and user['level']:
            user_level = user['level']
    except Exception as e:
        print(f"Error getting user level: {str(e)}")
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()
    
    return render_template('index.html', version=app.config['VERSION'], user_email=user_email, user_level=user_level)


@app.route('/api/send-verification-code', methods=['POST'])
def send_verification_code():
    """Send verification code to user's email"""
    data = request.json or {}
    email = data.get('email', '').strip()
    
    if not email or not validate_email(email):
        return jsonify({'error': 'Valid email address is required'}), 400
    
    # Clean up expired codes
    cleanup_expired_codes()
    
    # Generate verification code
    code = generate_verification_code()
    store_verification_code(email, code)
    
    # Send email using 163.com SMTP (primary)
    subject = 'Your Login Verification Code'
    body = f'''
    <html>
    <body style="font-family: Arial, sans-serif; padding: 20px;">
        <h2>Login Verification Code</h2>
        <p>Your verification code is:</p>
        <h1 style="color: #007bff; font-size: 32px; letter-spacing: 5px;">{code}</h1>
        <p>This code will expire in 10 minutes.</p>
        <p>If you did not request this code, please ignore this email.</p>
    </body>
    </html>
    '''
    
    # Try to use configured SMTP configs: Gmail (main) first, then 163.com (backup)
    configs_to_try = []
    
    # First priority: Gmail SMTP (main)
    if SMTP_BACKUP_CONFIG.get('username') and SMTP_BACKUP_CONFIG.get('password'):
        configs_to_try.append(SMTP_BACKUP_CONFIG)
    
    # Second priority: 163.com SMTP (backup)
    if SMTP_PRIMARY_CONFIG.get('username') and SMTP_PRIMARY_CONFIG.get('password'):
        configs_to_try.append(SMTP_PRIMARY_CONFIG)
    
    # Third priority: Try LCF if available (from DEFAULT_SMTP_CONFIGS)
    for config in DEFAULT_SMTP_CONFIGS:
        if config.get('username') and config.get('password'):
            # Avoid duplicates - only add if not already in list
            is_duplicate = any(
                c.get('server') == config.get('server') and 
                c.get('username') == config.get('username')
                for c in configs_to_try
            )
            if not is_duplicate:
                configs_to_try.append(config)
    
    # If no configs have credentials, return error
    if not configs_to_try:
        return jsonify({
            'error': 'SMTP server not configured. Please set email credentials in environment variables (.env file).',
            'details': ['No SMTP credentials available. Required: GMAIL_USERNAME and GMAIL_PASSWORD (main), or EMAIL163_USERNAME and EMAIL163_PASSWORD (backup)']
        }), 500
    
    result = send_email_with_configs(
        configs_to_try,  # Try Gmail first, then 163.com as backup
        subject,
        body,
        [email],
        is_html=True,
        sender_name='Mail Task'
    )
    
    if result.get('success'):
        return jsonify({'success': True, 'message': 'Verification code sent to your email'})
    else:
        return jsonify({
            'error': 'Failed to send verification code',
            'details': result.get('errors', [])
        }), 500


@app.route('/api/verify-code', methods=['POST'])
def verify_verification_code():
    """Verify the code and log in the user"""
    data = request.json or {}
    email = data.get('email', '').strip()
    code = data.get('code', '').strip()
    
    if not email or not code:
        return jsonify({'error': 'Email and code are required'}), 400
    
    if verify_code(email, code):
        session['logged_in'] = True
        session['user_email'] = email
        
        # Record login in users table
        connection = None
        cursor = None
        try:
            connection = get_db_connection()
            cursor = connection.cursor()
            now_iso = datetime.utcnow().isoformat()
            
            # Check if user exists
            cursor.execute("SELECT id, login_count FROM users WHERE email = ?", (email,))
            user = cursor.fetchone()
            
            if user:
                # Update existing user
                cursor.execute("""
                    UPDATE users 
                    SET last_login = ?, login_count = login_count + 1
                    WHERE email = ?
                """, (now_iso, email))
            else:
                # Create new user
                cursor.execute("""
                    INSERT INTO users (email, level, status, created_at, last_login, login_count)
                    VALUES (?, '1', 'active', ?, ?, 1)
                """, (email, now_iso, now_iso))
            
            connection.commit()
        except Exception as e:
            if connection:
                connection.rollback()
            print(f"Error recording login: {str(e)}")
            # Don't fail login if recording fails
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()
        
        return jsonify({'success': True, 'message': 'Login successful'})
    else:
        return jsonify({'error': 'Invalid or expired verification code'}), 401


@app.route('/api/logout', methods=['POST'])
def logout():
    """Log out the user"""
    session.clear()
    return jsonify({'success': True, 'message': 'Logged out successfully'})


@app.route('/api/users', methods=['GET'])
def get_users():
    """Get all users with login history, including users who created records but haven't logged in"""
    if not session.get('logged_in'):
        return jsonify({'error': 'Not authenticated'}), 401
    
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Get all users from users table (those who have logged in)
        cursor.execute("""
            SELECT id, email, level, status, created_at, last_login, login_count
            FROM users
        """)
        users_rows = cursor.fetchall()
        
        # Get all unique created_by emails from customers, emails, and tasks tables
        cursor.execute("""
            SELECT DISTINCT created_by as email
            FROM customers
            WHERE created_by IS NOT NULL AND created_by != ''
            UNION
            SELECT DISTINCT created_by as email
            FROM emails
            WHERE created_by IS NOT NULL AND created_by != ''
            UNION
            SELECT DISTINCT created_by as email
            FROM tasks
            WHERE created_by IS NOT NULL AND created_by != ''
        """)
        created_by_rows = cursor.fetchall()
        
        # Create a dictionary of existing users from users table
        users_dict = {}
        for row in users_rows:
            email = row['email']
            users_dict[email] = {
                'id': row['id'],
                'email': email,
                'level': row['level'] or '1',
                'status': row['status'] or 'active',
                'created_at': row['created_at'],
                'last_login': row['last_login'],
                'login_count': row['login_count'] or 0
            }
        
        # Add users who created records but haven't logged in
        for row in created_by_rows:
            email = row['email']
            if email and email not in users_dict:
                # Find the earliest created_at from any table for this user
                cursor.execute("""
                    SELECT MIN(created_at) as earliest_created FROM (
                        SELECT created_at FROM customers WHERE created_by = ?
                        UNION ALL
                        SELECT fetched_at as created_at FROM emails WHERE created_by = ?
                        UNION ALL
                        SELECT created_at FROM tasks WHERE created_by = ?
                    )
                """, (email, email, email))
                earliest = cursor.fetchone()
                earliest_created = earliest['earliest_created'] if earliest and earliest['earliest_created'] else None
                
                users_dict[email] = {
                    'id': None,  # No user record yet
                    'email': email,
                    'level': '1',  # Default level
                    'status': 'active',  # Default status
                    'created_at': earliest_created,
                    'last_login': None,  # Never logged in
                    'login_count': 0
                }
        
        # Convert to list and sort
        users = list(users_dict.values())
        users.sort(key=lambda x: (
            x['last_login'] if x['last_login'] else '',
            x['created_at'] if x['created_at'] else ''
        ), reverse=True)
        
        return jsonify({'users': users})
    except Exception as exc:
        if connection:
            connection.rollback()
        return jsonify({'error': f'Database error: {str(exc)}'}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@app.route('/api/users/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    """Update user level and status"""
    if not session.get('logged_in'):
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.json or {}
    level = (data.get('level') or '').strip()
    status = (data.get('status') or '').strip()
    
    if not level or level not in ['1', '2', '3']:
        return jsonify({'error': 'Invalid level. Must be 1, 2, or 3'}), 400
    
    if not status or status not in ['active', 'suspended']:
        return jsonify({'error': 'Invalid status. Must be active or suspended'}), 400
    
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("""
            UPDATE users 
            SET level = ?, status = ?
            WHERE id = ?
        """, (level, status, user_id))
        connection.commit()
        updated = cursor.rowcount > 0
        
        if not updated:
            return jsonify({'error': 'User not found'}), 404
        
        return jsonify({'success': True, 'message': 'User updated successfully'})
    except Exception as exc:
        if connection:
            connection.rollback()
        return jsonify({'error': f'Database error: {str(exc)}'}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@app.route('/api/users/by-email', methods=['PUT'])
def update_user_by_email():
    """Update user level and status by email (for users who haven't logged in yet)"""
    if not session.get('logged_in'):
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.json or {}
    email = (data.get('email') or '').strip()
    level = (data.get('level') or '').strip()
    status = (data.get('status') or '').strip()
    
    if not email:
        return jsonify({'error': 'Email is required'}), 400
    
    if not level or level not in ['1', '2', '3']:
        return jsonify({'error': 'Invalid level. Must be 1, 2, or 3'}), 400
    
    if not status or status not in ['active', 'suspended']:
        return jsonify({'error': 'Invalid status. Must be active or suspended'}), 400
    
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Check if user exists
        cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()
        
        if user:
            # Update existing user
            cursor.execute("""
                UPDATE users 
                SET level = ?, status = ?
                WHERE email = ?
            """, (level, status, email))
        else:
            # Create new user record
            now_iso = datetime.utcnow().isoformat()
            # Find earliest created_at from any table
            cursor.execute("""
                SELECT MIN(created_at) as earliest_created FROM (
                    SELECT created_at FROM customers WHERE created_by = ?
                    UNION ALL
                    SELECT fetched_at as created_at FROM emails WHERE created_by = ?
                    UNION ALL
                    SELECT created_at FROM tasks WHERE created_by = ?
                )
            """, (email, email, email))
            earliest = cursor.fetchone()
            created_at = earliest['earliest_created'] if earliest and earliest['earliest_created'] else now_iso
            
            cursor.execute("""
                INSERT INTO users (email, level, status, created_at, last_login, login_count)
                VALUES (?, ?, ?, ?, NULL, 0)
            """, (email, level, status, created_at))
        
        connection.commit()
        return jsonify({'success': True, 'message': 'User updated successfully'})
    except Exception as exc:
        if connection:
            connection.rollback()
        return jsonify({'error': f'Database error: {str(exc)}'}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@app.route('/api/export/customers', methods=['GET'])
def export_customers():
    """Export customers to Excel - requires level 2+"""
    has_access, error_response, status_code = check_user_level(2)
    if not has_access:
        return error_response, status_code
    
    user_email = session.get('user_email')
    if not user_email:
        return jsonify({'error': 'Not authenticated'}), 401
    
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("""
            SELECT name, email_suffix, country, website, remark, company_name, tel, source, address, business_type, created_at, created_by
            FROM customers
            WHERE created_by = ?
            ORDER BY datetime(created_at) DESC
        """, (user_email,))
        rows = cursor.fetchall()
        
        # Generate Excel file using utility function
        output, filename = export_customers_to_excel(rows)
        return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 
                        as_attachment=True, download_name=filename)
    except Exception as e:
        if connection:
            connection.rollback()
        return jsonify({'error': f'Export error: {str(e)}'}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@app.route('/api/export/tasks', methods=['GET'])
def export_tasks():
    """Export tasks to Excel - requires level 2+"""
    has_access, error_response, status_code = check_user_level(2)
    if not has_access:
        return error_response, status_code
    
    user_email = session.get('user_email')
    if not user_email:
        return jsonify({'error': 'Not authenticated'}), 401
    
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Check if email column exists
        cursor.execute("PRAGMA table_info(tasks)")
        columns = [col[1] for col in cursor.fetchall()]
        has_email_column = 'email' in columns
        
        # Try to add email column if it doesn't exist
        if not has_email_column:
            try:
                cursor.execute("ALTER TABLE tasks ADD COLUMN email TEXT")
                connection.commit()
                has_email_column = True
            except sqlite3.OperationalError:
                connection.rollback()
                pass
        
        # Get tasks with related customer info - use query that handles missing email column
        if has_email_column:
            cursor.execute("""
                SELECT 
                    t.sequence,
                    t.customer,
                    COALESCE(t.email, 
                        (SELECT c.email_suffix FROM customers c 
                         WHERE t.customer IS NOT NULL AND c.name = t.customer
                         ORDER BY c.id
                         LIMIT 1)
                    ) AS email,
                    t.catalogue,
                    t.template,
                    t.attachments,
                    t.deadline,
                    t.created_at,
                    t.updated_at,
                    t.created_by,
                    (SELECT company_name FROM customers c 
                     WHERE (t.email IS NOT NULL AND c.email_suffix = t.email) 
                        OR (t.customer IS NOT NULL AND c.name = t.customer)
                     ORDER BY CASE WHEN t.email IS NOT NULL AND c.email_suffix = t.email THEN 1 ELSE 2 END, c.id
                     LIMIT 1) AS company_name,
                    (SELECT source FROM customers c 
                     WHERE (t.email IS NOT NULL AND c.email_suffix = t.email) 
                        OR (t.customer IS NOT NULL AND c.name = t.customer)
                     ORDER BY CASE WHEN t.email IS NOT NULL AND c.email_suffix = t.email THEN 1 ELSE 2 END, c.id
                     LIMIT 1) AS source,
                    (SELECT business_type FROM customers c 
                     WHERE (t.email IS NOT NULL AND c.email_suffix = t.email) 
                        OR (t.customer IS NOT NULL AND c.name = t.customer)
                     ORDER BY CASE WHEN t.email IS NOT NULL AND c.email_suffix = t.email THEN 1 ELSE 2 END, c.id
                     LIMIT 1) AS business_type
                FROM tasks t
                WHERE t.created_by = ?
                ORDER BY datetime(t.created_at) DESC
            """, (user_email,))
        else:
            # Fallback query without email column references in subqueries
            cursor.execute("""
                SELECT 
                    t.sequence,
                    t.customer,
                    (SELECT c.email_suffix FROM customers c 
                     WHERE t.customer IS NOT NULL AND c.name = t.customer
                     ORDER BY c.id
                     LIMIT 1) AS email,
                    t.catalogue,
                    t.template,
                    t.attachments,
                    t.deadline,
                    COALESCE(t.status, 'open') AS status,
                    t.created_at,
                    t.updated_at,
                    t.created_by,
                    (SELECT company_name FROM customers c 
                     WHERE t.customer IS NOT NULL AND c.name = t.customer
                     ORDER BY c.id
                     LIMIT 1) AS company_name,
                    (SELECT source FROM customers c 
                     WHERE t.customer IS NOT NULL AND c.name = t.customer
                     ORDER BY c.id
                     LIMIT 1) AS source,
                    (SELECT business_type FROM customers c 
                     WHERE t.customer IS NOT NULL AND c.name = t.customer
                     ORDER BY c.id
                     LIMIT 1) AS business_type
                FROM tasks t
                WHERE t.created_by = ?
                ORDER BY datetime(t.created_at) DESC
            """, (user_email,))
        rows = cursor.fetchall()
        
        # Generate Excel file using utility function
        output, filename = export_tasks_to_excel(rows)
        return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 
                        as_attachment=True, download_name=filename)
    except Exception as e:
        if connection:
            connection.rollback()
        return jsonify({'error': f'Export error: {str(e)}'}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@app.route('/api/gmail-auth', methods=['GET'])
def gmail_auth():
    """Start Gmail OAuth flow - requires level 2+"""
    has_access, error_response, status_code = check_user_level(2)
    if not has_access:
        return error_response, status_code
    
    data = request.args
    client_id = (data.get('client_id') or GMAIL_OAUTH_CONFIG.get('client_id') or '').strip()
    client_secret = (data.get('client_secret') or GMAIL_OAUTH_CONFIG.get('client_secret') or '').strip()
    redirect_uri = (data.get('redirect_uri') or GMAIL_OAUTH_CONFIG.get('redirect_uri') or f'http://localhost:{FLASK_PORT}/oauth2callback').strip()
    
    if not client_id or not client_secret:
        return jsonify({'error': 'Gmail OAuth client_id and client_secret are required. Please enter them in the Settings page.'}), 400
    
    # Validate Client ID format
    if not client_id.endswith('.apps.googleusercontent.com'):
        return jsonify({'error': f'Invalid Client ID format. Should end with .apps.googleusercontent.com. Got: {client_id[:50]}...'}), 400
    
    # Validate Client Secret format
    if not client_secret.startswith('GOCSPX-'):
        return jsonify({'error': f'Invalid Client Secret format. Should start with GOCSPX-. Please check your Google Cloud Console.'}), 400
    
    try:
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [redirect_uri]
                }
            },
            scopes=GMAIL_OAUTH_CONFIG['scopes'],
            redirect_uri=redirect_uri
        )
        
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'
        )
        
        # Store state in both session and database for reliability
        session['oauth_state'] = state
        session['oauth_client_id'] = client_id
        session['oauth_client_secret'] = client_secret
        session['oauth_redirect_uri'] = redirect_uri
        
        # Also store in database as backup (in case session is lost)
        try:
            connection = get_db_connection()
            cursor = connection.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO oauth_states (state, client_id, client_secret, redirect_uri, created_at)
                VALUES (?, ?, ?, ?, datetime('now'))
            """, (state, client_id, client_secret, redirect_uri))
            connection.commit()
            cursor.close()
            connection.close()
        except Exception as e:
            print(f"Warning: Could not store OAuth state in database: {e}")
        
        return jsonify({'auth_url': authorization_url})
    except Exception as e:
        error_msg = str(e)
        # Provide more helpful error messages
        if 'invalid_client' in error_msg.lower():
            return jsonify({
                'error': f'Invalid Client ID or Client Secret. Please verify:\n'
                        f'1. Client ID: {client_id[:30]}...\n'
                        f'2. Client Secret: {client_secret[:10]}...\n'
                        f'3. Make sure they match the credentials from Google Cloud Console\n'
                        f'4. Ensure the OAuth client type is "Web application" (not Desktop)'
            }), 400
        return jsonify({'error': f'OAuth setup error: {error_msg}'}), 500


@app.route('/oauth2callback')
def oauth2callback():
    """OAuth 2.0 callback handler"""
    code = request.args.get('code')
    state = request.args.get('state')
    
    if not code:
        return '<html><body><h1>Authentication Failed</h1><p>No authorization code received.</p><script>setTimeout(() => window.close(), 3000);</script></body></html>', 400
    
    if not state:
        return '<html><body><h1>Authentication Failed</h1><p>No state parameter received.</p><script>setTimeout(() => window.close(), 3000);</script></body></html>', 400
    
    # Try to get credentials from session first
    client_id = session.get('oauth_client_id')
    client_secret = session.get('oauth_client_secret')
    redirect_uri = session.get('oauth_redirect_uri')
    session_state = session.get('oauth_state')
    
    # If session state doesn't match, try to get from database
    if state != session_state:
        connection = None
        cursor = None
        try:
            connection = get_db_connection()
            cursor = connection.cursor()
            cursor.execute("""
                SELECT client_id, client_secret, redirect_uri 
                FROM oauth_states 
                WHERE state = ? AND datetime(created_at) > datetime('now', '-10 minutes')
            """, (state,))
            row = cursor.fetchone()
            if row:
                client_id = row['client_id']
                client_secret = row['client_secret']
                redirect_uri = row['redirect_uri']
                # Delete used state
                cursor.execute("DELETE FROM oauth_states WHERE state = ?", (state,))
                connection.commit()
        except Exception as e:
            print(f"Error checking OAuth state in database: {e}")
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()
    
    # Final validation
    if state != session_state and not client_id:
        return '<html><body><h1>Authentication Failed</h1><p>Invalid state parameter. Please try authenticating again.</p><script>setTimeout(() => window.close(), 3000);</script></body></html>', 400
    
    if not client_id or not client_secret:
        return '<html><body><h1>Authentication Failed</h1><p>OAuth credentials not found. Please try authenticating again.</p><script>setTimeout(() => window.close(), 3000);</script></body></html>', 400
    
    if not redirect_uri:
        redirect_uri = GMAIL_OAUTH_CONFIG.get('redirect_uri', f'http://localhost:{FLASK_PORT}/oauth2callback')
    
    try:
        
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [redirect_uri]
                }
            },
            scopes=GMAIL_OAUTH_CONFIG['scopes'],
            redirect_uri=redirect_uri,
            state=state
        )
        
        flow.fetch_token(code=code)
        creds = flow.credentials
        
        # Save credentials
        save_oauth_token('gmail', creds)
        
        return '<html><body><h1>Authentication Successful!</h1><p>You can close this window and return to the app.</p><script>setTimeout(() => window.close(), 2000);</script></body></html>'
    except Exception as e:
        error_msg = str(e)
        error_html = '<html><body style="font-family: Arial, sans-serif; padding: 20px;"><h1 style="color: #dc3545;">Authentication Error</h1>'
        
        if 'invalid_client' in error_msg.lower():
            error_html += f'''
            <div style="background-color: #f8d7da; border: 1px solid #dc3545; padding: 15px; border-radius: 4px; margin: 15px 0;">
                <h2 style="color: #721c24; margin-top: 0;">Invalid Client ID or Client Secret</h2>
                <p style="color: #721c24;"><strong>This error means your Client ID and Client Secret don't match.</strong></p>
                <ol style="color: #721c24;">
                    <li>Go to <a href="https://console.cloud.google.com/apis/credentials" target="_blank">Google Cloud Console Credentials</a></li>
                    <li>Find your OAuth client: <code style="background: #fff; padding: 2px 5px;">{client_id[:50]}...</code></li>
                    <li>Click on it to view details</li>
                    <li>Copy the <strong>Client ID</strong> and <strong>Client Secret</strong> again</li>
                    <li>Make sure you're copying from a <strong>"Web application"</strong> type client (not Desktop)</li>
                    <li>Paste them in the Settings page and try again</li>
                </ol>
                <p style="color: #721c24; margin-bottom: 0;"><strong>Note:</strong> Client Secret starts with "GOCSPX-" and you can only see it once when you create the client.</p>
            </div>
            '''
        else:
            error_html += f'<p style="color: #721c24;">{error_msg}</p>'
        
        error_html += '<p><button onclick="window.close()">Close Window</button></p>'
        error_html += '<script>setTimeout(() => window.close(), 10000);</script></body></html>'
        return error_html, 500


@app.route('/api/gmail-status', methods=['GET'])
def gmail_status():
    """Check Gmail OAuth authentication status"""
    creds = load_oauth_token('gmail')
    if creds:
        try:
            # Try to verify token is valid
            service = build('gmail', 'v1', credentials=creds)
            profile = service.users().getProfile(userId='me').execute()
            return jsonify({
                'authenticated': True,
                'email': profile.get('emailAddress', ''),
                'messages_total': profile.get('messagesTotal', 0)
            })
        except Exception as e:
            return jsonify({
                'authenticated': False,
                'error': f'Token invalid: {str(e)}',
                'needs_auth': True
            })
    return jsonify({
        'authenticated': False,
        'needs_auth': True,
        'message': 'Gmail OAuth not configured. Please set up OAuth credentials in Settings.'
    })


@app.route('/api/fetch-gmail', methods=['POST'])
def fetch_gmail():
    """Fetch emails from Gmail using Gmail API - requires level 2+"""
    has_access, error_response, status_code = check_user_level(2)
    if not has_access:
        return error_response, status_code
    
    data = request.json or {}
    limit = data.get('limit', 50)
    days_back = data.get('days_back', 1)
    try:
        limit = max(1, int(limit))
    except (TypeError, ValueError):
        limit = 50
    try:
        days_back = max(0, int(days_back))
    except (TypeError, ValueError):
        days_back = 1
    
    # Check if OAuth is configured
    creds = load_oauth_token('gmail')
    if not creds:
        return jsonify({
            'error': 'Gmail OAuth not authenticated. Please:\n1. Go to Settings\n2. Enter OAuth Client ID and Client Secret\n3. Click "Authenticate Gmail"\n4. Complete the OAuth flow',
            'needs_auth': True,
            'setup_url': 'https://console.cloud.google.com/'
        }), 401
    
    # Fetch emails for requested time window
    result = fetch_gmail_api(limit=limit, days_back=days_back)
    
    if 'error' in result:
        # If authentication is needed, return 401 status
        if result.get('needs_auth'):
            return jsonify(result), 401
        return jsonify(result), 500
    
    # Save emails to SQL database
    try:
        save_emails('gmail', result.get('emails', []))
    except Exception as exc:
        print(f"Error saving Gmail emails: {exc}")
    
    return jsonify(result)


@app.route('/api/fetch-qq', methods=['POST'])
def fetch_qq():
    """Fetch emails from QQ - requires level 2+"""
    has_access, error_response, status_code = check_user_level(2)
    if not has_access:
        return error_response, status_code
    """Fetch emails from QQ"""
    data = request.json
    username = data.get('username', '')
    password = data.get('password', '')
    
    if not username or not password:
        return jsonify({'error': 'QQ username and password are required'}), 400
    
    limit = data.get('limit', 50)
    result = fetch_emails(
        data.get('imap_server', QQ_CONFIG['imap_server']),
        data.get('port', QQ_CONFIG['port']),
        username,
        password,
        data.get('use_ssl', QQ_CONFIG.get('use_ssl', True)),
        data.get('use_tls', QQ_CONFIG.get('use_tls', False)),
        limit,
        days_back=1
    )
    try:
        save_emails('qq', result.get('emails', []))
    except Exception as exc:
        print(f"Error saving QQ emails: {exc}")
    return jsonify(result)


@app.route('/api/fetch-lcf', methods=['POST'])
def fetch_lcf():
    """Fetch emails from LCF account - requires level 2+"""
    has_access, error_response, status_code = check_user_level(2)
    if not has_access:
        return error_response, status_code

    data = request.json or {}
    # For LCF, requirement is: each fetch must load ALL emails for *today*.
    # We therefore ignore any client-provided limit and use limit = 0, which
    # in the IMAP helper means "no trimming" of the IDs returned by the server.
    limit = 0

    config = {
        'imap_server': data.get('imap_server', LCF_CONFIG['imap_server']),
        'port': data.get('port', LCF_CONFIG['port']),
        'username': data.get('username', LCF_CONFIG['username']),
        'password': data.get('password', LCF_CONFIG['password']),
        'use_ssl': data.get('use_ssl', LCF_CONFIG.get('use_ssl', True)),
        'use_tls': data.get('use_tls', LCF_CONFIG.get('use_tls', False))
    }

    # Always fetch only today's emails for LCF (days_back = 0), and with
    # limit = 0 (all messages returned by the IMAP SINCE search). The IMAP
    # helper will further filter by today's date, so even if the server
    # returns older messages for the SINCE search, only today's messages
    # are kept.
    result = fetch_emails(
        config['imap_server'],
        config['port'],
        config['username'],
        config['password'],
        config['use_ssl'],
        config['use_tls'],
        limit,
        days_back=0
    )

    try:
        save_emails('lcf', result.get('emails', []))
    except Exception as exc:
        print(f"Error saving LCF emails: {exc}")
    return jsonify(result)


@app.route('/api/fetch-sendbox', methods=['POST'])
def fetch_sendbox():
    """Fetch sent emails from LCF account Send Items folder - visible to all users"""
    data = request.json or {}
    # For Send Box, requirement is: each fetch must load ALL sent emails for *today*.
    # We therefore ignore any client-provided limit and use limit = 0, which
    # in the IMAP helper means "no trimming" of the IDs returned by the server.
    limit = 0

    config = {
        'imap_server': data.get('imap_server', LCF_CONFIG['imap_server']),
        'port': data.get('port', LCF_CONFIG['port']),
        'username': data.get('username', LCF_CONFIG['username']),
        'password': data.get('password', LCF_CONFIG['password']),
        'use_ssl': data.get('use_ssl', LCF_CONFIG.get('use_ssl', True)),
        'use_tls': data.get('use_tls', LCF_CONFIG.get('use_tls', False))
    }

    # Always fetch only today's sent emails for Send Box (days_back = 0), and with
    # limit = 0 (all messages returned by the IMAP SINCE search). The IMAP
    # helper will further filter by today's date, so even if the server
    # returns older messages for the SINCE search, only today's messages
    # are kept.
    result = fetch_emails(
        config['imap_server'],
        config['port'],
        config['username'],
        config['password'],
        config['use_ssl'],
        config['use_tls'],
        limit,
        days_back=0,
        folder='Sent Items'
    )

    try:
        save_emails('sendbox', result.get('emails', []))
    except Exception as exc:
        print(f"Error saving Send Box emails: {exc}")
    return jsonify(result)


@app.route('/api/fetch-163', methods=['POST'])
def fetch_163():
    """Fetch emails from 163.com - requires level 2+"""
    has_access, error_response, status_code = check_user_level(2)
    if not has_access:
        return error_response, status_code
    """Fetch emails from 163.com"""
    data = request.json or {}
    limit = data.get('limit', 50)
    
    # Use provided config or default
    config = {
        'imap_server': data.get('imap_server', EMAIL163_CONFIG['imap_server']),
        'port': data.get('port', EMAIL163_CONFIG['port']),
        'username': data.get('username', EMAIL163_CONFIG['username']),
        'password': data.get('password', EMAIL163_CONFIG['password']),
        'use_ssl': data.get('use_ssl', EMAIL163_CONFIG.get('use_ssl', True)),
        'use_tls': data.get('use_tls', EMAIL163_CONFIG.get('use_tls', False))
    }
    
    result = fetch_emails(
        config['imap_server'],
        config['port'],
        config['username'],
        config['password'],
        config['use_ssl'],
        config['use_tls'],
        limit,
        days_back=1
    )
    try:
        save_emails('163', result.get('emails', []))
    except Exception as exc:
        print(f"Error saving 163 emails: {exc}")
    return jsonify(result)


@app.route('/api/send-email', methods=['POST'])
def send_email():
    """Send email - requires level 2+"""
    has_access, error_response, status_code = check_user_level(2)
    if not has_access:
        return error_response, status_code
    """Send email using configured SMTP servers with automatic fallback."""
    data = request.json or {}
    recipients_raw = data.get('to') or data.get('recipients')

    if not recipients_raw:
        return jsonify({'error': 'Recipient email address is required'}), 400

    if isinstance(recipients_raw, list):
        recipients = [addr.strip() for addr in recipients_raw if isinstance(addr, str) and addr.strip()]
    else:
        recipients = [addr.strip() for addr in re.split(r'[;,]', str(recipients_raw)) if addr.strip()]

    if not recipients:
        return jsonify({'error': 'Recipient email address is required'}), 400

    configs_payload = data.get('configs') or []
    configs = build_smtp_config_list(configs_payload)
    if not configs:
        configs = build_smtp_config_list(DEFAULT_SMTP_CONFIGS)

    attachments = data.get('attachments', [])
    
    result = send_email_with_configs(
        configs,
        data.get('subject', ''),
        data.get('body', ''),
        recipients,
        bool(data.get('is_html')),
        data.get('sender_name'),
        attachments
    )

    if result.get('success'):
        return jsonify({'status': 'sent', 'provider': result.get('provider')})

    return jsonify({
        'error': 'Unable to send email via configured SMTP servers',
        'details': result.get('errors', [])
    }), 500


@app.route('/api/customers', methods=['GET', 'POST'])
def customers_endpoint():
    if request.method == 'GET':
        try:
            customers = fetch_customers()
            return jsonify({'customers': customers})
        except Exception as exc:
            return jsonify({'error': f'Database error: {str(exc)}'}), 500

    data = request.json or {}
    name = (data.get('name') or '').strip()
    # Support both email_address (new) and email_suffix (old) for backward compatibility
    email_address = (data.get('email_address') or '').strip()
    suffix = (data.get('email_suffix') or '').strip()
    country = (data.get('country') or '').strip() or None
    website = (data.get('website') or '').strip() or None
    source = (data.get('source') or '').strip() or None
    address = (data.get('address') or '').strip() or None
    business_type = (data.get('business_type') or '').strip() or None
    rank = (data.get('rank') or '').strip() or None
    remark = (data.get('remark') or '').strip() or None
    attachments = data.get('attachments') or None
    company_name = (data.get('company_name') or '').strip() or None
    tel = (data.get('tel') or '').strip() or None

    if not name:
        return jsonify({'error': 'Customer name is required'}), 400
    
    # If email_address is provided, validate and save full email address
    if email_address:
        # Validate email format
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email_address):
            return jsonify({'error': 'Invalid email address format'}), 400
        # Save full email address (prefix + suffix)
        full_email = email_address
    elif suffix:
        # Backward compatibility: handle old email_suffix format
        if '@' in suffix:
            # If it already contains @, treat as full email
            full_email = suffix
        else:
            # Old format: just domain, convert to @domain format for backward compatibility
            if not re.match(r'^[a-zA-Z0-9._-]+\.[a-zA-Z]{2,}$', suffix):
                return jsonify({'error': 'Invalid email suffix format'}), 400
            full_email = '@' + suffix
    else:
        return jsonify({'error': 'Email address is required'}), 400

    try:
        user_email = session.get('user_email')
        if not user_email:
            return jsonify({'error': 'Not authenticated'}), 401
        customer_id = insert_customer(name, full_email, country, website, remark, attachments, company_name, tel, source, address, business_type, rank, user_email)
        return jsonify({
            'id': customer_id,
            'name': name,
            'email_suffix': full_email,
            'country': country,
            'tel': tel,
            'website': website,
            'source': source,
            'remark': remark,
            'attachments': attachments,
            'company_name': company_name,
            'address': address,
            'business_type': business_type,
            'rank': rank
        }), 201
    except Exception as exc:
        return jsonify({'error': f'Database error: {str(exc)}'}), 500


@app.route('/api/customers/<int:customer_id>', methods=['PUT', 'DELETE'])
def update_or_delete_customer(customer_id):
    """Update or delete a customer by ID"""
    if request.method == 'PUT':
        try:
            data = request.json or {}
            name = (data.get('name') or '').strip()
            email_address = (data.get('email_address') or '').strip()
            country = (data.get('country') or '').strip() or None
            website = (data.get('website') or '').strip() or None
            source = (data.get('source') or '').strip() or None
            remark = (data.get('remark') or '').strip() or None
            attachments = data.get('attachments') or None
            company_name = (data.get('company_name') or '').strip() or None
            tel = (data.get('tel') or '').strip() or None
            address = (data.get('address') or '').strip() or None
            business_type = (data.get('business_type') or '').strip() or None
            rank = (data.get('rank') or '').strip() or None
            
            if not name:
                return jsonify({'error': 'Customer name is required'}), 400
            
            if email_address:
                email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
                if not re.match(email_pattern, email_address):
                    return jsonify({'error': 'Invalid email address format'}), 400
                full_email = email_address
            else:
                return jsonify({'error': 'Email address is required'}), 400
            
            user_email = session.get('user_email')
            if not user_email:
                return jsonify({'error': 'Not authenticated'}), 401
            
            connection = get_db_connection()
            cursor = connection.cursor()
            # Check if customer exists and belongs to user
            cursor.execute("SELECT id FROM customers WHERE id = ? AND created_by = ?", (customer_id, user_email))
            if not cursor.fetchone():
                cursor.close()
                connection.close()
                return jsonify({'error': 'Customer not found or access denied'}), 404
            
            cursor.execute("""
                UPDATE customers 
                SET name = ?, email_suffix = ?, country = ?, website = ?, source = ?, remark = ?, attachments = ?, company_name = ?, tel = ?, address = ?, business_type = ?, rank = ?
                WHERE id = ? AND created_by = ?
            """, (name, full_email, country, website, source, remark, attachments, company_name, tel, address, business_type, rank, customer_id, user_email))
            connection.commit()
            updated = cursor.rowcount > 0
            cursor.close()
            connection.close()
            
            if updated:
                return jsonify({
                    'id': customer_id,
                    'name': name,
                    'email_suffix': full_email,
                    'country': country,
                    'tel': tel,
                    'website': website,
                    'source': source,
                    'remark': remark,
                    'attachments': attachments,
                    'company_name': company_name,
                    'address': address,
                    'business_type': business_type,
                    'rank': rank,
                    'status': 'updated'
                })
            else:
                return jsonify({'error': 'Customer not found'}), 404
        except Exception as exc:
            return jsonify({'error': f'Database error: {str(exc)}'}), 500
    
    elif request.method == 'DELETE':
        try:
            user_email = session.get('user_email')
            if not user_email:
                return jsonify({'error': 'Not authenticated'}), 401
            
            connection = get_db_connection()
            cursor = connection.cursor()
            cursor.execute("DELETE FROM customers WHERE id = ? AND created_by = ?", (customer_id, user_email))
            connection.commit()
            deleted = cursor.rowcount > 0
            cursor.close()
            connection.close()
            
            if deleted:
                return jsonify({'status': 'deleted', 'id': customer_id})
            else:
                return jsonify({'error': 'Customer not found'}), 404
        except Exception as exc:
            return jsonify({'error': f'Database error: {str(exc)}'}), 500


@app.route('/api/emails', methods=['GET', 'POST'])
def handle_emails():
    if request.method == 'GET':
        provider = (request.args.get('provider') or '').strip().lower()
        if not provider:
            return jsonify({'error': 'Provider query parameter is required'}), 400
        
        # Optional days parameter (number of days back to include)
        days_param = request.args.get('days')
        # By default, return all days (0 = no time filter). Clients can still
        # pass a positive "days" value to limit the range.
        default_days = 0
        if days_param is None or days_param == '':
            days = default_days
        else:
            try:
                days = max(0, int(days_param))
            except (TypeError, ValueError):
                return jsonify({'error': 'Invalid days parameter'}), 400

        # Pagination parameters
        try:
            limit = int(request.args.get('limit', 200))
            offset = int(request.args.get('offset', 0))
        except (TypeError, ValueError):
            limit = 200
            offset = 0

        # Build SQL query with optional date filter
        user_email = session.get('user_email')
        if not user_email:
            return jsonify({'error': 'Not authenticated'}), 401
        
        connection = get_db_connection()
        cursor = connection.cursor()
        # For list view performance, return summary fields by default.
        # Clients can request full bodies via /api/email (single email endpoint).
        query = """
            SELECT provider, email_uid, subject, from_addr, to_addr, date, preview, sequence, attachments, fetched_at, created_by
            FROM emails
            WHERE provider = ? AND created_by = ?
        """
        params = [provider, user_email]
        if days > 0:
            query += " AND datetime(fetched_at) >= datetime('now', ?)"
            params.append(f'-{days} days')
        query += " ORDER BY datetime(date) DESC, datetime(fetched_at) DESC"
        query += " LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()
        cursor.close()
        connection.close()

        emails = []
        for row in rows:
            attachments = []
            try:
                attachments = json.loads(row[8] or '[]')
            except (TypeError, ValueError):
                attachments = []

            # In list view we only return light fields; full bodies are fetched on-demand
            emails.append({
                'id': row[1],
                'subject': row[2],
                'from': row[3],
                'to': row[4],
                'date': row[5],
                'preview': row[6],
                'sequence': row[7],
                'attachments': attachments,
                'fetched_at': row[9],
                'created_by': row[10] if len(row) > 10 else None,
                'has_body': False
            })

        return jsonify({'provider': provider, 'emails': emails, 'limit': limit, 'offset': offset, 'returned': len(emails)})
    
    elif request.method == 'POST':
        data = request.json or {}
        provider = (data.get('provider') or '').strip().lower()
        emails = data.get('emails') or []

        if not provider:
            return jsonify({'error': 'Provider is required'}), 400

        if not isinstance(emails, list):
            return jsonify({'error': 'Emails must be a list'}), 400

        save_emails(provider, emails)
        return jsonify({'status': 'saved', 'count': len(emails)})


@app.route('/api/email', methods=['GET'])
def get_email_detail():
    """Get one email with full body/attachments by provider + id (email_uid)."""
    provider = (request.args.get('provider') or '').strip().lower()
    email_uid = (request.args.get('id') or '').strip()
    if not provider or not email_uid:
        return jsonify({'error': 'provider and id are required'}), 400

    user_email = session.get('user_email')
    if not user_email:
        return jsonify({'error': 'Not authenticated'}), 401

    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT provider, email_uid, subject, from_addr, to_addr, date, preview,
               plain_body, html_body, sequence, attachments, fetched_at, created_by
        FROM emails
        WHERE provider = ? AND email_uid = ? AND created_by = ?
        LIMIT 1
        """,
        (provider, email_uid, user_email)
    )
    row = cursor.fetchone()
    cursor.close()
    connection.close()

    if not row:
        return jsonify({'error': 'Email not found'}), 404

    attachments = []
    try:
        attachments = json.loads(row[10] or '[]')
    except (TypeError, ValueError):
        attachments = []

    return jsonify({
        'provider': row[0],
        'id': row[1],
        'subject': row[2],
        'from': row[3],
        'to': row[4],
        'date': row[5],
        'preview': row[6],
        'plain_body': row[7],
        'html_body': row[8],
        'sequence': row[9],
        'attachments': attachments,
        'fetched_at': row[11],
        'created_by': row[12] if len(row) > 12 else None,
        'has_body': True
    })


@app.route('/api/emails/by-customer', methods=['GET'])
def get_emails_by_customer():
    """Get all emails for a customer by email address"""
    customer_email = (request.args.get('email') or '').strip()
    if not customer_email:
        return jsonify({'error': 'Email query parameter is required'}), 400
    
    connection = get_db_connection()
    cursor = connection.cursor()
    
    user_email = session.get('user_email')
    if not user_email:
        return jsonify({'error': 'Not authenticated'}), 401
    
    # Search for emails where the customer email appears in from_addr or to_addr
    # AND the email was created by the logged-in user
    query = """
        SELECT provider, email_uid, subject, from_addr, to_addr, date, preview, plain_body, html_body, sequence, attachments, fetched_at, created_by
        FROM emails
        WHERE (from_addr LIKE ? OR to_addr LIKE ?) AND created_by = ?
        ORDER BY datetime(date) DESC, datetime(fetched_at) DESC
    """
    # Use LIKE with % wildcards to match email addresses
    email_pattern = f'%{customer_email}%'
    cursor.execute(query, (email_pattern, email_pattern, user_email))
    rows = cursor.fetchall()
    cursor.close()
    connection.close()
    
    emails = []
    for row in rows:
        attachments = []
        try:
            attachments = json.loads(row[10] or '[]')
        except (TypeError, ValueError):
            attachments = []
        emails.append({
            'id': row[1],
            'subject': row[2],
            'from': row[3],
            'to': row[4],
            'date': row[5],
            'preview': row[6],
            'plain_body': row[7],
            'html_body': row[8],
            'sequence': row[9],
            'attachments': attachments,
            'fetched_at': row[11],
            'created_by': row[12] if len(row) > 12 else None
        })
    
    return jsonify({'customer_email': customer_email, 'emails': emails})


@app.route('/api/version', methods=['GET'])
def get_version():
    """Get application version"""
    return jsonify({'version': app.config['VERSION']})


@app.route('/api/tasks', methods=['GET', 'POST'])
def handle_tasks():
    """Handle task creation and retrieval"""
    if request.method == 'GET':
        try:
            connection = get_db_connection()
            cursor = connection.cursor()
            
            # Always try to add email column if it doesn't exist (idempotent)
            try:
                cursor.execute("ALTER TABLE tasks ADD COLUMN email TEXT")
                connection.commit()
                # Force schema refresh by querying table info
                cursor.execute("PRAGMA table_info(tasks)")
            except sqlite3.OperationalError:
                connection.rollback()  # Column already exists, rollback any partial changes
                pass
            
            user_email = session.get('user_email')
            if not user_email:
                return jsonify({'error': 'Not authenticated'}), 401
            
            # Try the query with email column first
            try:
                cursor.execute("""
                    SELECT 
                        t.id,
                        t.sequence,
                        t.customer,
                        COALESCE(t.email, 
                            (SELECT c.email_suffix FROM customers c 
                             WHERE t.customer IS NOT NULL AND c.name = t.customer
                             ORDER BY c.id
                             LIMIT 1)
                        ) AS email,
                        t.catalogue,
                        t.template,
                        t.attachments,
                        t.deadline,
                        COALESCE(t.status, 'open') AS status,
                        t.created_at,
                        t.updated_at,
                        t.created_by,
                        (SELECT company_name FROM customers c 
                         WHERE (t.email IS NOT NULL AND c.email_suffix = t.email) 
                            OR (t.customer IS NOT NULL AND c.name = t.customer)
                         ORDER BY CASE WHEN t.email IS NOT NULL AND c.email_suffix = t.email THEN 1 ELSE 2 END, c.id
                         LIMIT 1) AS company_name,
                        (SELECT source FROM customers c 
                         WHERE (t.email IS NOT NULL AND c.email_suffix = t.email) 
                            OR (t.customer IS NOT NULL AND c.name = t.customer)
                         ORDER BY CASE WHEN t.email IS NOT NULL AND c.email_suffix = t.email THEN 1 ELSE 2 END, c.id
                         LIMIT 1) AS customer_source,
                        (SELECT business_type FROM customers c 
                         WHERE (t.email IS NOT NULL AND c.email_suffix = t.email) 
                            OR (t.customer IS NOT NULL AND c.name = t.customer)
                         ORDER BY CASE WHEN t.email IS NOT NULL AND c.email_suffix = t.email THEN 1 ELSE 2 END, c.id
                         LIMIT 1) AS customer_business_type
                    FROM tasks t
                    WHERE t.created_by = ?
                    ORDER BY datetime(t.created_at) DESC
                """, (user_email,))
            except sqlite3.OperationalError as e:
                # If email column still doesn't exist, use fallback query
                if 'no such column' in str(e).lower() and 'email' in str(e).lower():
                    cursor.execute("""
                        SELECT 
                            t.id,
                            t.sequence,
                            t.customer,
                            (SELECT c.email_suffix FROM customers c 
                             WHERE t.customer IS NOT NULL AND c.name = t.customer
                             ORDER BY c.id
                             LIMIT 1) AS email,
                            t.catalogue,
                            t.template,
                            t.attachments,
                            t.deadline,
                            t.created_at,
                            t.updated_at,
                            t.created_by,
                            (SELECT company_name FROM customers c 
                             WHERE c.name = t.customer
                             ORDER BY c.id
                             LIMIT 1) AS company_name,
                            (SELECT source FROM customers c 
                             WHERE c.name = t.customer
                             ORDER BY c.id
                             LIMIT 1) AS customer_source,
                            (SELECT business_type FROM customers c 
                             WHERE c.name = t.customer
                             ORDER BY c.id
                             LIMIT 1) AS customer_business_type
                        FROM tasks t
                        WHERE t.created_by = ?
                        ORDER BY datetime(t.created_at) DESC
                    """, (user_email,))
                else:
                    raise  # Re-raise if it's a different error
            rows = cursor.fetchall()
            cursor.close()
            connection.close()
            
            tasks = []
            for row in rows:
                attachments = []
                try:
                    attachments = json.loads(row[6] or '[]')
                except (TypeError, ValueError):
                    attachments = []
                
                try:
                    created_by = row['created_by']
                except (KeyError, IndexError):
                    created_by = None
                
                try:
                    status = row['status'] if 'status' in row.keys() else 'open'
                except (KeyError, IndexError):
                    status = 'open'
                
                tasks.append({
                    'id': row['id'],
                    'sequence': row['sequence'],
                    'customer': row['customer'],
                    'email': row['email'],
                    'catalogue': row['catalogue'],
                    'template': row['template'],
                    'attachments': attachments,
                    'deadline': row['deadline'],
                    'status': status,
                    'created_at': row['created_at'],
                    'updated_at': row['updated_at'],
                    'created_by': created_by,
                    'company_name': row['company_name'],
                    'source': row['customer_source'],
                    'business_type': row['customer_business_type']
                })
            
            # Filter to only show latest task per company_name + customer combination
            # Group tasks by company_name and customer, keep only the one with latest updated_at
            task_groups = {}
            for task in tasks:
                company = task.get('company_name') or ''
                customer = task.get('customer') or ''
                key = f"{company}|||{customer}"
                
                if key not in task_groups:
                    task_groups[key] = task
                else:
                    # Compare updated_at timestamps
                    current_updated = task.get('updated_at') or task.get('created_at') or ''
                    existing_updated = task_groups[key].get('updated_at') or task_groups[key].get('created_at') or ''
                    
                    if current_updated > existing_updated:
                        task_groups[key] = task
            
            # Convert back to list and sort by created_at DESC
            filtered_tasks = list(task_groups.values())
            filtered_tasks.sort(key=lambda x: x.get('created_at') or '', reverse=True)
            
            return jsonify({'tasks': filtered_tasks})
        except Exception as exc:
            return jsonify({'error': f'Database error: {str(exc)}'}), 500
    
    elif request.method == 'POST':
        data = request.json or {}
        sequence = data.get('sequence', '')
        customer = data.get('customer', '')
        email = data.get('email', '')
        catalogue = data.get('catalogue', '').strip()
        template = data.get('template', '').strip()
        attachments = data.get('attachments', [])
        deadline = data.get('deadline')
        status = data.get('status', 'open').strip()  # Default to 'open'
        if isinstance(deadline, str):
            deadline = deadline.strip() or None
        
        if not catalogue:
            return jsonify({'error': 'Catalogue is required'}), 400
        
        if not template:
            return jsonify({'error': 'Template is required'}), 400
        
        # Validate status exists in database (default to 'open' if not found)
        try:
            connection_check = get_db_connection()
            cursor_check = connection_check.cursor()
            cursor_check.execute("SELECT name FROM task_statuses WHERE name = ?", (status,))
            if not cursor_check.fetchone():
                cursor_check.execute("SELECT name FROM task_statuses WHERE name = 'open'")
                open_status = cursor_check.fetchone()
                if open_status:
                    status = 'open'
                else:
                    # If 'open' doesn't exist, get first status
                    cursor_check.execute("SELECT name FROM task_statuses ORDER BY display_order LIMIT 1")
                    first_status = cursor_check.fetchone()
                    status = first_status['name'] if first_status else 'open'
            cursor_check.close()
            connection_check.close()
        except Exception:
            # If table doesn't exist yet, default to 'open'
            status = 'open'
        
        try:
            attachments_json = json.dumps(attachments) if attachments else '[]'
            
            user_email = session.get('user_email')
            if not user_email:
                return jsonify({'error': 'Not authenticated'}), 401
            
            connection = get_db_connection()
            cursor = connection.cursor()
            cursor.execute("""
                INSERT INTO tasks (sequence, customer, email, catalogue, template, attachments, deadline, status, created_at, updated_at, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'), ?)
            """, (sequence, customer, email, catalogue, template, attachments_json, deadline, status, user_email))
            connection.commit()
            task_id = cursor.lastrowid
            cursor.execute("SELECT created_at, updated_at FROM tasks WHERE id = ?", (task_id,))
            timestamps_row = cursor.fetchone()
            created_at_value = timestamps_row['created_at'] if timestamps_row else None
            updated_at_value = timestamps_row['updated_at'] if timestamps_row else None
            cursor.close()
            connection.close()
            
            return jsonify({
                'id': task_id,
                'sequence': sequence,
                'customer': customer,
                'email': email,
                'catalogue': catalogue,
                'template': template,
                'attachments': attachments,
                'deadline': deadline,
                'created_at': created_at_value,
                'updated_at': updated_at_value
            }), 201
        except Exception as exc:
            return jsonify({'error': f'Database error: {str(exc)}'}), 500


@app.route('/api/tasks/<int:task_id>', methods=['PUT', 'DELETE'])
def handle_single_task(task_id):
    """Update or delete a task by ID"""
    if request.method == 'DELETE':
        connection = None
        cursor = None
        try:
            user_email = session.get('user_email')
            if not user_email:
                return jsonify({'error': 'Not authenticated'}), 401
            
            connection = get_db_connection()
            cursor = connection.cursor()
            cursor.execute("DELETE FROM tasks WHERE id = ? AND created_by = ?", (task_id, user_email))
            connection.commit()
            deleted = cursor.rowcount > 0
            cursor.close()
            connection.close()
            cursor = None
            connection = None
            
            if deleted:
                return jsonify({'status': 'deleted', 'id': task_id})
            else:
                return jsonify({'error': 'Task not found'}), 404
        except Exception as exc:
            if cursor:
                cursor.close()
            if connection:
                connection.close()
            return jsonify({'error': f'Database error: {str(exc)}'}), 500
    
    # PUT - update task
    connection = None
    cursor = None
    connection_check = None
    cursor_check = None
    try:
        data = request.get_json() or {}
        catalogue = (data.get('catalogue') or '').strip()
        template = (data.get('template') or '').strip()
        email = (data.get('email') or '').strip()
        customer = (data.get('customer') or '').strip()
        attachments = data.get('attachments')
        deadline = (data.get('deadline') or '').strip() or None
        
        if not catalogue:
            return jsonify({'error': 'Catalogue is required'}), 400
        if not template:
            return jsonify({'error': 'Template is required'}), 400
        
        attachments_json = None
        if attachments is not None:
            try:
                attachments_json = json.dumps(attachments)
            except (TypeError, ValueError):
                return jsonify({'error': 'Invalid attachments format'}), 400
        
        user_email = session.get('user_email')
        if not user_email:
            return jsonify({'error': 'Not authenticated'}), 401
        
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Check if task exists and belongs to user
        cursor.execute("SELECT id FROM tasks WHERE id = ? AND created_by = ?", (task_id, user_email))
        if not cursor.fetchone():
            return jsonify({'error': 'Task not found or access denied'}), 404
        
        status = data.get('status', '').strip()
        # Validate status exists in database if provided
        if status:
            try:
                connection_check = get_db_connection()
                cursor_check = connection_check.cursor()
                cursor_check.execute("SELECT name FROM task_statuses WHERE name = ?", (status,))
                if not cursor_check.fetchone():
                    status = None  # Don't update if invalid
            except Exception:
                status = None  # Don't update if table doesn't exist
            finally:
                if cursor_check:
                    cursor_check.close()
                if connection_check:
                    connection_check.close()
        
        # Whitelist of allowed field names to prevent SQL injection
        ALLOWED_TASK_FIELDS = {'catalogue', 'template', 'deadline', 'email', 'customer', 'status', 'attachments'}
        
        update_fields = []
        if catalogue:
            update_fields.append(('catalogue', catalogue))
        if template:
            update_fields.append(('template', template))
        if deadline:
            update_fields.append(('deadline', deadline))
        if email:
            update_fields.append(('email', email))
        if customer:
            update_fields.append(('customer', customer))
        if status:
            update_fields.append(('status', status))
        if attachments_json is not None:
            update_fields.append(('attachments', attachments_json))
        
        # Validate all field names against whitelist
        for field, _ in update_fields:
            if field not in ALLOWED_TASK_FIELDS:
                return jsonify({'error': f'Invalid field name: {field}'}), 400
        
        if not update_fields:
            return jsonify({'error': 'No fields to update'}), 400
        
        # Build safe parameterized query
        set_clause = ', '.join([f"{field} = ?" for field, _ in update_fields])
        set_clause = f"{set_clause}, updated_at = datetime('now')"
        values = [value for _, value in update_fields]
        values.append(task_id)
        values.append(user_email)
        
        cursor.execute(f"UPDATE tasks SET {set_clause} WHERE id = ? AND created_by = ?", values)
        connection.commit()
        updated = cursor.rowcount > 0
        cursor.close()
        connection.close()
        cursor = None
        connection = None
        
        if not updated:
            return jsonify({'error': 'Task not found'}), 404
        
        return jsonify({'status': 'updated', 'id': task_id})
    except Exception as exc:
        if cursor:
            cursor.close()
        if connection:
            connection.rollback()
            connection.close()
        if cursor_check:
            cursor_check.close()
        if connection_check:
            connection_check.close()
        return jsonify({'error': f'Database error: {str(exc)}'}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@app.route('/api/tasks/by-customer', methods=['GET'])
def get_tasks_by_customer():
    """Get all task history for a specific company_name and customer combination"""
    company_name = (request.args.get('company_name') or '').strip()
    customer = (request.args.get('customer') or '').strip()
    
    if not company_name or not customer:
        return jsonify({'error': 'Both company_name and customer query parameters are required'}), 400
    
    user_email = session.get('user_email')
    if not user_email:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Try the query with email column first
        try:
            cursor.execute("""
                SELECT 
                    t.id,
                    t.sequence,
                    t.customer,
                    t.email,
                    t.catalogue,
                    t.template,
                    t.attachments,
                    t.deadline,
                    t.created_at,
                    t.updated_at,
                    t.created_by,
                    (SELECT company_name FROM customers c 
                     WHERE (t.email IS NOT NULL AND c.email_suffix = t.email) 
                        OR (t.customer IS NOT NULL AND c.name = t.customer)
                     ORDER BY CASE WHEN t.email IS NOT NULL AND c.email_suffix = t.email THEN 1 ELSE 2 END, c.id
                     LIMIT 1) AS company_name,
                    (SELECT source FROM customers c 
                     WHERE (t.email IS NOT NULL AND c.email_suffix = t.email) 
                        OR (t.customer IS NOT NULL AND c.name = t.customer)
                     ORDER BY CASE WHEN t.email IS NOT NULL AND c.email_suffix = t.email THEN 1 ELSE 2 END, c.id
                     LIMIT 1) AS customer_source,
                    (SELECT business_type FROM customers c 
                     WHERE (t.email IS NOT NULL AND c.email_suffix = t.email) 
                        OR (t.customer IS NOT NULL AND c.name = t.customer)
                     ORDER BY CASE WHEN t.email IS NOT NULL AND c.email_suffix = t.email THEN 1 ELSE 2 END, c.id
                     LIMIT 1) AS customer_business_type
                FROM tasks t
                WHERE t.customer = ? AND t.created_by = ?
                ORDER BY datetime(t.updated_at) DESC, datetime(t.created_at) DESC
            """, (customer, user_email))
        except sqlite3.OperationalError as e:
            # If email column still doesn't exist, use fallback query
            if 'no such column' in str(e).lower() and 'email' in str(e).lower():
                cursor.execute("""
                    SELECT 
                        t.id,
                        t.sequence,
                        t.customer,
                        NULL as email,
                        t.catalogue,
                        t.template,
                        t.attachments,
                        t.deadline,
                        t.created_at,
                        t.updated_at,
                        t.created_by,
                        (SELECT company_name FROM customers c 
                         WHERE c.name = t.customer
                         ORDER BY c.id
                         LIMIT 1) AS company_name,
                        (SELECT source FROM customers c 
                         WHERE c.name = t.customer
                         ORDER BY c.id
                         LIMIT 1) AS customer_source,
                        (SELECT business_type FROM customers c 
                         WHERE c.name = t.customer
                         ORDER BY c.id
                         LIMIT 1) AS customer_business_type
                    FROM tasks t
                    WHERE t.customer = ? AND t.created_by = ?
                    ORDER BY datetime(t.updated_at) DESC, datetime(t.created_at) DESC
                """, (customer, user_email))
            else:
                raise
        
        rows = cursor.fetchall()
        cursor.close()
        connection.close()
        
        tasks = []
        for row in rows:
            # Filter by company_name match
            row_company_name = row['company_name'] or ''
            if row_company_name != company_name:
                continue
                
            attachments = []
            try:
                attachments = json.loads(row[6] or '[]')
            except (TypeError, ValueError):
                attachments = []
            
            try:
                created_by = row['created_by']
            except (KeyError, IndexError):
                created_by = None
            
            tasks.append({
                'id': row['id'],
                'sequence': row['sequence'],
                'customer': row['customer'],
                'email': row['email'],
                'catalogue': row['catalogue'],
                'template': row['template'],
                'attachments': attachments,
                'deadline': row['deadline'],
                'created_at': row['created_at'],
                'created_by': created_by,
                'updated_at': row['updated_at'],
                'company_name': row['company_name'],
                'source': row['customer_source'],
                'business_type': row['customer_business_type']
            })
        
        return jsonify({'company_name': company_name, 'customer': customer, 'tasks': tasks})
    except Exception as exc:
        return jsonify({'error': f'Database error: {str(exc)}'}), 500


@app.route('/api/task-types', methods=['GET', 'POST'])
def handle_task_types():
    """Handle task type retrieval and creation"""
    if request.method == 'GET':
        try:
            connection = get_db_connection()
            cursor = connection.cursor()
            cursor.execute("SELECT id, name, display_order, created_at FROM task_types ORDER BY display_order, name")
            types = [dict(row) for row in cursor.fetchall()]
            cursor.close()
            connection.close()
            return jsonify(types)
        except Exception as exc:
            return jsonify({'error': f'Database error: {str(exc)}'}), 500
    
    elif request.method == 'POST':
        try:
            data = request.get_json()
            name = data.get('name', '').strip()
            if not name:
                return jsonify({'error': 'Task type name is required'}), 400
            
            connection = get_db_connection()
            cursor = connection.cursor()
            
            # Check if name already exists
            cursor.execute("SELECT id FROM task_types WHERE name = ?", (name,))
            if cursor.fetchone():
                cursor.close()
                connection.close()
                return jsonify({'error': 'Task type with this name already exists'}), 400
            
            # Get max display_order
            cursor.execute("SELECT MAX(display_order) as max_order FROM task_types")
            max_order = cursor.fetchone()['max_order'] or 0
            display_order = data.get('display_order', max_order + 1)
            
            cursor.execute("""
                INSERT INTO task_types (name, display_order) VALUES (?, ?)
            """, (name, display_order))
            connection.commit()
            task_type_id = cursor.lastrowid
            cursor.close()
            connection.close()
            
            return jsonify({
                'id': task_type_id,
                'name': name,
                'display_order': display_order,
                'status': 'created'
            }), 201
        except Exception as exc:
            return jsonify({'error': f'Database error: {str(exc)}'}), 500


@app.route('/api/task-types/<int:type_id>', methods=['PUT', 'DELETE'])
def handle_task_type(type_id):
    """Handle task type update and deletion"""
    if request.method == 'PUT':
        try:
            data = request.get_json()
            name = data.get('name', '').strip()
            if not name:
                return jsonify({'error': 'Task type name is required'}), 400
            
            connection = get_db_connection()
            cursor = connection.cursor()
            
            # Check if name already exists for another type
            cursor.execute("SELECT id FROM task_types WHERE name = ? AND id != ?", (name, type_id))
            if cursor.fetchone():
                cursor.close()
                connection.close()
                return jsonify({'error': 'Task type with this name already exists'}), 400
            
            display_order = data.get('display_order', 0)
            cursor.execute("""
                UPDATE task_types SET name = ?, display_order = ? WHERE id = ?
            """, (name, display_order, type_id))
            connection.commit()
            updated = cursor.rowcount > 0
            cursor.close()
            connection.close()
            
            if updated:
                return jsonify({
                    'id': type_id,
                    'name': name,
                    'display_order': display_order,
                    'status': 'updated'
                })
            else:
                return jsonify({'error': 'Task type not found'}), 404
        except Exception as exc:
            return jsonify({'error': f'Database error: {str(exc)}'}), 500
    
    elif request.method == 'DELETE':
        try:
            connection = get_db_connection()
            cursor = connection.cursor()
            cursor.execute("DELETE FROM task_types WHERE id = ?", (type_id,))
            connection.commit()
            deleted = cursor.rowcount > 0
            cursor.close()
            connection.close()
            
            if deleted:
                return jsonify({'status': 'deleted', 'id': type_id})
            else:
                return jsonify({'error': 'Task type not found'}), 404
        except Exception as exc:
            return jsonify({'error': f'Database error: {str(exc)}'}), 500


@app.route('/api/countries', methods=['GET', 'POST'])
def handle_countries():
    """Handle country retrieval and creation"""
    if request.method == 'GET':
        try:
            connection = get_db_connection()
            cursor = connection.cursor()
            cursor.execute("SELECT id, name, display_order, created_at FROM countries ORDER BY display_order, name")
            countries = [dict(row) for row in cursor.fetchall()]
            cursor.close()
            connection.close()
            return jsonify(countries)
        except Exception as exc:
            return jsonify({'error': f'Database error: {str(exc)}'}), 500
    
    elif request.method == 'POST':
        try:
            data = request.get_json()
            name = data.get('name', '').strip()
            if not name:
                return jsonify({'error': 'Country name is required'}), 400
            
            connection = get_db_connection()
            cursor = connection.cursor()
            
            # Check if name already exists
            cursor.execute("SELECT id FROM countries WHERE name = ?", (name,))
            if cursor.fetchone():
                cursor.close()
                connection.close()
                return jsonify({'error': 'Country with this name already exists'}), 400
            
            # Get max display_order
            cursor.execute("SELECT MAX(display_order) as max_order FROM countries")
            max_order = cursor.fetchone()['max_order'] or 0
            display_order = data.get('display_order', max_order + 1)
            
            cursor.execute("""
                INSERT INTO countries (name, display_order) VALUES (?, ?)
            """, (name, display_order))
            connection.commit()
            country_id = cursor.lastrowid
            cursor.close()
            connection.close()
            
            return jsonify({
                'id': country_id,
                'name': name,
                'display_order': display_order,
                'status': 'created'
            }), 201
        except Exception as exc:
            return jsonify({'error': f'Database error: {str(exc)}'}), 500


@app.route('/api/countries/<int:country_id>', methods=['PUT', 'DELETE'])
def handle_country(country_id):
    """Handle country update and deletion"""
    if request.method == 'PUT':
        try:
            data = request.get_json()
            name = data.get('name', '').strip()
            if not name:
                return jsonify({'error': 'Country name is required'}), 400
            
            connection = get_db_connection()
            cursor = connection.cursor()
            
            # Check if name already exists for another country
            cursor.execute("SELECT id FROM countries WHERE name = ? AND id != ?", (name, country_id))
            if cursor.fetchone():
                cursor.close()
                connection.close()
                return jsonify({'error': 'Country with this name already exists'}), 400
            
            display_order = data.get('display_order', 0)
            cursor.execute("""
                UPDATE countries SET name = ?, display_order = ? WHERE id = ?
            """, (name, display_order, country_id))
            connection.commit()
            updated = cursor.rowcount > 0
            cursor.close()
            connection.close()
            
            if updated:
                return jsonify({
                    'id': country_id,
                    'name': name,
                    'display_order': display_order,
                    'status': 'updated'
                })
            else:
                return jsonify({'error': 'Country not found'}), 404
        except Exception as exc:
            return jsonify({'error': f'Database error: {str(exc)}'}), 500
    
    elif request.method == 'DELETE':
        try:
            connection = get_db_connection()
            cursor = connection.cursor()
            cursor.execute("DELETE FROM countries WHERE id = ?", (country_id,))
            connection.commit()
            deleted = cursor.rowcount > 0
            cursor.close()
            connection.close()
            
            if deleted:
                return jsonify({'status': 'deleted', 'id': country_id})
            else:
                return jsonify({'error': 'Country not found'}), 404
        except Exception as exc:
            return jsonify({'error': f'Database error: {str(exc)}'}), 500


@app.route('/api/customer-sources', methods=['GET', 'POST'])
def handle_customer_sources():
    """Handle customer source retrieval and creation"""
    if request.method == 'GET':
        try:
            connection = get_db_connection()
            cursor = connection.cursor()
            cursor.execute("SELECT id, name, display_order, created_at FROM customer_sources ORDER BY display_order, name")
            sources = [dict(row) for row in cursor.fetchall()]
            cursor.close()
            connection.close()
            return jsonify(sources)
        except Exception as exc:
            return jsonify({'error': f'Database error: {str(exc)}'}), 500
    
    elif request.method == 'POST':
        try:
            data = request.get_json()
            name = data.get('name', '').strip()
            if not name:
                return jsonify({'error': 'Customer source name is required'}), 400
            
            connection = get_db_connection()
            cursor = connection.cursor()
            
            # Check if name already exists
            cursor.execute("SELECT id FROM customer_sources WHERE name = ?", (name,))
            if cursor.fetchone():
                cursor.close()
                connection.close()
                return jsonify({'error': 'Customer source with this name already exists'}), 400
            
            # Get max display_order
            cursor.execute("SELECT MAX(display_order) as max_order FROM customer_sources")
            max_order = cursor.fetchone()['max_order'] or 0
            display_order = data.get('display_order', max_order + 1)
            
            cursor.execute("""
                INSERT INTO customer_sources (name, display_order) VALUES (?, ?)
            """, (name, display_order))
            connection.commit()
            source_id = cursor.lastrowid
            cursor.close()
            connection.close()
            
            return jsonify({
                'id': source_id,
                'name': name,
                'display_order': display_order,
                'status': 'created'
            }), 201
        except Exception as exc:
            return jsonify({'error': f'Database error: {str(exc)}'}), 500


@app.route('/api/customer-sources/<int:source_id>', methods=['PUT', 'DELETE'])
def handle_customer_source(source_id):
    """Handle customer source update and deletion"""
    if request.method == 'PUT':
        try:
            data = request.get_json()
            name = data.get('name', '').strip()
            if not name:
                return jsonify({'error': 'Customer source name is required'}), 400
            
            connection = get_db_connection()
            cursor = connection.cursor()
            
            # Check if name already exists for another source
            cursor.execute("SELECT id FROM customer_sources WHERE name = ? AND id != ?", (name, source_id))
            if cursor.fetchone():
                cursor.close()
                connection.close()
                return jsonify({'error': 'Customer source with this name already exists'}), 400
            
            display_order = data.get('display_order', 0)
            cursor.execute("""
                UPDATE customer_sources SET name = ?, display_order = ? WHERE id = ?
            """, (name, display_order, source_id))
            connection.commit()
            updated = cursor.rowcount > 0
            cursor.close()
            connection.close()
            
            if updated:
                return jsonify({
                    'id': source_id,
                    'name': name,
                    'display_order': display_order,
                    'status': 'updated'
                })
            else:
                return jsonify({'error': 'Customer source not found'}), 404
        except Exception as exc:
            return jsonify({'error': f'Database error: {str(exc)}'}), 500
    
    elif request.method == 'DELETE':
        try:
            connection = get_db_connection()
            cursor = connection.cursor()
            cursor.execute("DELETE FROM customer_sources WHERE id = ?", (source_id,))
            connection.commit()
            deleted = cursor.rowcount > 0
            cursor.close()
            connection.close()
            
            if deleted:
                return jsonify({'status': 'deleted', 'id': source_id})
            else:
                return jsonify({'error': 'Customer source not found'}), 404
        except Exception as exc:
            return jsonify({'error': f'Database error: {str(exc)}'}), 500


@app.route('/api/customer-business-types', methods=['GET', 'POST'])
def handle_customer_business_types():
    """Handle customer business type retrieval and creation"""
    if request.method == 'GET':
        try:
            connection = get_db_connection()
            cursor = connection.cursor()
            cursor.execute("SELECT id, name, display_order, created_at FROM customer_business_types ORDER BY display_order, name")
            types = [dict(row) for row in cursor.fetchall()]
            cursor.close()
            connection.close()
            return jsonify(types)
        except Exception as exc:
            return jsonify({'error': f'Database error: {str(exc)}'}), 500
    
    elif request.method == 'POST':
        try:
            data = request.get_json()
            name = data.get('name', '').strip()
            if not name:
                return jsonify({'error': 'Customer business type name is required'}), 400
            
            connection = get_db_connection()
            cursor = connection.cursor()
            
            # Check if name already exists
            cursor.execute("SELECT id FROM customer_business_types WHERE name = ?", (name,))
            if cursor.fetchone():
                cursor.close()
                connection.close()
                return jsonify({'error': 'Customer business type with this name already exists'}), 400
            
            # Get max display_order
            cursor.execute("SELECT MAX(display_order) as max_order FROM customer_business_types")
            max_order = cursor.fetchone()['max_order'] or 0
            display_order = data.get('display_order', max_order + 1)
            
            cursor.execute("""
                INSERT INTO customer_business_types (name, display_order) VALUES (?, ?)
            """, (name, display_order))
            connection.commit()
            type_id = cursor.lastrowid
            cursor.close()
            connection.close()
            
            return jsonify({
                'id': type_id,
                'name': name,
                'display_order': display_order,
                'status': 'created'
            }), 201
        except Exception as exc:
            return jsonify({'error': f'Database error: {str(exc)}'}), 500


@app.route('/api/customer-business-types/<int:type_id>', methods=['PUT', 'DELETE'])
def handle_customer_business_type(type_id):
    """Handle customer business type update and deletion"""
    if request.method == 'PUT':
        try:
            data = request.get_json()
            name = data.get('name', '').strip()
            if not name:
                return jsonify({'error': 'Customer business type name is required'}), 400
            
            connection = get_db_connection()
            cursor = connection.cursor()
            
            # Check if name already exists for another type
            cursor.execute("SELECT id FROM customer_business_types WHERE name = ? AND id != ?", (name, type_id))
            if cursor.fetchone():
                cursor.close()
                connection.close()
                return jsonify({'error': 'Customer business type with this name already exists'}), 400
            
            display_order = data.get('display_order', 0)
            cursor.execute("""
                UPDATE customer_business_types SET name = ?, display_order = ? WHERE id = ?
            """, (name, display_order, type_id))
            connection.commit()
            updated = cursor.rowcount > 0
            cursor.close()
            connection.close()
            
            if updated:
                return jsonify({
                    'id': type_id,
                    'name': name,
                    'display_order': display_order,
                    'status': 'updated'
                })
            else:
                return jsonify({'error': 'Customer business type not found'}), 404
        except Exception as exc:
            return jsonify({'error': f'Database error: {str(exc)}'}), 500
    
    elif request.method == 'DELETE':
        try:
            connection = get_db_connection()
            cursor = connection.cursor()
            cursor.execute("DELETE FROM customer_business_types WHERE id = ?", (type_id,))
            connection.commit()
            deleted = cursor.rowcount > 0
            cursor.close()
            connection.close()
            
            if deleted:
                return jsonify({'status': 'deleted', 'id': type_id})
            else:
                return jsonify({'error': 'Customer business type not found'}), 404
        except Exception as exc:
            return jsonify({'error': f'Database error: {str(exc)}'}), 500


@app.route('/api/customer-ranks', methods=['GET', 'POST'])
def handle_customer_ranks():
    """Handle customer rank retrieval and creation"""
    if request.method == 'GET':
        try:
            connection = get_db_connection()
            cursor = connection.cursor()
            cursor.execute("SELECT id, name, display_order, created_at FROM customer_ranks ORDER BY display_order, name")
            ranks = [dict(row) for row in cursor.fetchall()]
            cursor.close()
            connection.close()
            return jsonify(ranks)
        except Exception as exc:
            return jsonify({'error': f'Database error: {str(exc)}'}), 500
    
    elif request.method == 'POST':
        try:
            data = request.get_json()
            name = data.get('name', '').strip()
            if not name:
                return jsonify({'error': 'Customer rank name is required'}), 400
            
            connection = get_db_connection()
            cursor = connection.cursor()
            
            # Check if name already exists
            cursor.execute("SELECT id FROM customer_ranks WHERE name = ?", (name,))
            if cursor.fetchone():
                cursor.close()
                connection.close()
                return jsonify({'error': 'Customer rank with this name already exists'}), 400
            
            # Get max display_order
            cursor.execute("SELECT MAX(display_order) as max_order FROM customer_ranks")
            max_order = cursor.fetchone()['max_order'] or 0
            display_order = data.get('display_order', max_order + 1)
            
            cursor.execute("""
                INSERT INTO customer_ranks (name, display_order) VALUES (?, ?)
            """, (name, display_order))
            connection.commit()
            rank_id = cursor.lastrowid
            cursor.close()
            connection.close()
            
            return jsonify({
                'id': rank_id,
                'name': name,
                'display_order': display_order,
                'status': 'created'
            }), 201
        except Exception as exc:
            return jsonify({'error': f'Database error: {str(exc)}'}), 500


@app.route('/api/customer-ranks/<int:rank_id>', methods=['PUT', 'DELETE'])
def handle_customer_rank(rank_id):
    """Handle customer rank update and deletion"""
    if request.method == 'PUT':
        try:
            data = request.get_json()
            name = data.get('name', '').strip()
            if not name:
                return jsonify({'error': 'Customer rank name is required'}), 400
            
            connection = get_db_connection()
            cursor = connection.cursor()
            
            # Check if name already exists for another rank
            cursor.execute("SELECT id FROM customer_ranks WHERE name = ? AND id != ?", (name, rank_id))
            if cursor.fetchone():
                cursor.close()
                connection.close()
                return jsonify({'error': 'Customer rank with this name already exists'}), 400
            
            display_order = data.get('display_order', 0)
            cursor.execute("""
                UPDATE customer_ranks SET name = ?, display_order = ? WHERE id = ?
            """, (name, display_order, rank_id))
            connection.commit()
            updated = cursor.rowcount > 0
            cursor.close()
            connection.close()
            
            if updated:
                return jsonify({
                    'id': rank_id,
                    'name': name,
                    'display_order': display_order,
                    'status': 'updated'
                })
            else:
                return jsonify({'error': 'Customer rank not found'}), 404
        except Exception as exc:
            return jsonify({'error': f'Database error: {str(exc)}'}), 500
    
    elif request.method == 'DELETE':
        try:
            connection = get_db_connection()
            cursor = connection.cursor()
            cursor.execute("DELETE FROM customer_ranks WHERE id = ?", (rank_id,))
            connection.commit()
            deleted = cursor.rowcount > 0
            cursor.close()
            connection.close()
            
            if deleted:
                return jsonify({'status': 'deleted', 'id': rank_id})
            else:
                return jsonify({'error': 'Customer rank not found'}), 404
        except Exception as exc:
            return jsonify({'error': f'Database error: {str(exc)}'}), 500


@app.route('/api/task-statuses', methods=['GET', 'POST'])
def handle_task_statuses():
    """Handle task status retrieval and creation"""
    if request.method == 'GET':
        try:
            connection = get_db_connection()
            cursor = connection.cursor()
            cursor.execute("SELECT id, name, display_order, created_at FROM task_statuses ORDER BY display_order, name")
            statuses = [dict(row) for row in cursor.fetchall()]
            cursor.close()
            connection.close()
            return jsonify(statuses)
        except Exception as exc:
            return jsonify({'error': f'Database error: {str(exc)}'}), 500
    
    elif request.method == 'POST':
        try:
            data = request.get_json()
            name = data.get('name', '').strip()
            if not name:
                return jsonify({'error': 'Task status name is required'}), 400
            
            connection = get_db_connection()
            cursor = connection.cursor()
            
            # Check if name already exists
            cursor.execute("SELECT id FROM task_statuses WHERE name = ?", (name,))
            if cursor.fetchone():
                cursor.close()
                connection.close()
                return jsonify({'error': 'Task status with this name already exists'}), 400
            
            # Get max display_order
            cursor.execute("SELECT MAX(display_order) as max_order FROM task_statuses")
            max_order = cursor.fetchone()['max_order'] or 0
            display_order = data.get('display_order', max_order + 1)
            
            cursor.execute("""
                INSERT INTO task_statuses (name, display_order) VALUES (?, ?)
            """, (name, display_order))
            connection.commit()
            status_id = cursor.lastrowid
            cursor.close()
            connection.close()
            
            return jsonify({
                'id': status_id,
                'name': name,
                'display_order': display_order,
                'status': 'created'
            }), 201
        except Exception as exc:
            return jsonify({'error': f'Database error: {str(exc)}'}), 500


@app.route('/api/task-statuses/<int:status_id>', methods=['PUT', 'DELETE'])
def handle_task_status(status_id):
    """Handle task status update and deletion"""
    if request.method == 'PUT':
        try:
            data = request.get_json()
            name = data.get('name', '').strip()
            if not name:
                return jsonify({'error': 'Task status name is required'}), 400
            
            connection = get_db_connection()
            cursor = connection.cursor()
            
            # Check if name already exists for another status
            cursor.execute("SELECT id FROM task_statuses WHERE name = ? AND id != ?", (name, status_id))
            if cursor.fetchone():
                cursor.close()
                connection.close()
                return jsonify({'error': 'Task status with this name already exists'}), 400
            
            display_order = data.get('display_order', 0)
            cursor.execute("""
                UPDATE task_statuses SET name = ?, display_order = ? WHERE id = ?
            """, (name, display_order, status_id))
            connection.commit()
            updated = cursor.rowcount > 0
            cursor.close()
            connection.close()
            
            if updated:
                return jsonify({
                    'id': status_id,
                    'name': name,
                    'display_order': display_order,
                    'status': 'updated'
                })
            else:
                return jsonify({'error': 'Task status not found'}), 404
        except Exception as exc:
            return jsonify({'error': f'Database error: {str(exc)}'}), 500
    
    elif request.method == 'DELETE':
        try:
            connection = get_db_connection()
            cursor = connection.cursor()
            cursor.execute("DELETE FROM task_statuses WHERE id = ?", (status_id,))
            connection.commit()
            deleted = cursor.rowcount > 0
            cursor.close()
            connection.close()
            
            if deleted:
                return jsonify({'status': 'deleted', 'id': status_id})
            else:
                return jsonify({'error': 'Task status not found'}), 404
        except Exception as exc:
            return jsonify({'error': f'Database error: {str(exc)}'}), 500


initialize_database()


if __name__ == '__main__':
    # Use 0.0.0.0 to allow access from network (192.168.x.x)
    # FLASK_PORT is already imported at the top
    import socket
    
    port = FLASK_PORT
    
    # Get local IP address for network access
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        local_ip = "localhost"
    
    # Try ports starting from configured port, increment until one works
    start_port = port
    max_attempts = 10
    
    for attempt in range(max_attempts):
        try_port = start_port + attempt
        try:
            if attempt > 0:
                print(f"Port {start_port + attempt - 1} unavailable, trying port {try_port}...")
            else:
                print(f"Starting Flask server on port {try_port}...")
            print(f"  Local access: http://127.0.0.1:{try_port}")
            print(f"  Network access: http://{local_ip}:{try_port}")
            app.run(debug=True, host='0.0.0.0', port=try_port)
            break  # Success, exit loop
        except OSError as e:
            if attempt < max_attempts - 1:
                continue  # Try next port
            else:
                print(f"❌ Failed to start server after trying ports {start_port} to {try_port}")
                raise

