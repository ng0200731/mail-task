"""
Email model for MailTask application.
Handles email database operations.
"""
import json
from datetime import datetime
from flask import session
from utils.db_utils import get_db_connection


def save_emails(provider: str, emails: list[dict], created_by: str = None):
    """
    Save emails to database.
    
    Args:
        provider (str): Email provider name (e.g., 'gmail', 'lcf', 'qq', '163')
        emails (list[dict]): List of email dictionaries
        created_by (str, optional): User email who created these emails.
                                   If None, will use session.get('user_email') or default.
    """
    if not emails:
        return
    
    if created_by is None:
        created_by = session.get('user_email')
        if not created_by:
            raise ValueError("User email is required. User must be authenticated.")
    
    connection = get_db_connection()
    cursor = connection.cursor()
    now_iso = datetime.utcnow().isoformat()
    rows = []
    
    for email in emails:
        email_uid = str(email.get('id') or email.get('email_uid') or '')
        if not email_uid:
            continue
        attachments = email.get('attachments') or []
        try:
            attachments_json = json.dumps(attachments)
        except (TypeError, ValueError):
            attachments_json = '[]'
        rows.append((
            provider,
            email_uid,
            email.get('subject'),
            email.get('from'),
            email.get('to'),
            email.get('date'),
            email.get('preview'),
            email.get('plain_body'),
            email.get('html_body'),
            email.get('sequence'),
            attachments_json,
            now_iso,
            created_by
        ))
    
    if not rows:
        cursor.close()
        connection.close()
        return

    cursor.executemany("""
        INSERT INTO emails (
            provider,
            email_uid,
            subject,
            from_addr,
            to_addr,
            date,
            preview,
            plain_body,
            html_body,
            sequence,
            attachments,
            fetched_at,
            created_by
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(provider, email_uid) DO UPDATE SET
            subject = excluded.subject,
            from_addr = excluded.from_addr,
            to_addr = excluded.to_addr,
            date = excluded.date,
            preview = excluded.preview,
            plain_body = excluded.plain_body,
            html_body = excluded.html_body,
            sequence = excluded.sequence,
            attachments = excluded.attachments,
            fetched_at = excluded.fetched_at,
            created_by = COALESCE(excluded.created_by, emails.created_by)
    """, rows)
    connection.commit()
    cursor.close()
    connection.close()

