"""
Email fetching utility functions for MailTask application.
Handles email retrieval from Gmail API and IMAP servers.
"""
import imaplib
import email
import email.utils
import ssl
import base64
from datetime import datetime, date, timedelta
from typing import Optional
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from utils.oauth_utils import load_oauth_token
from utils.email_parser import decode_mime_words, strip_html_tags, build_sequence_code
from utils.db_utils import get_db_connection


def fetch_gmail_api(limit=50, days_back=1):
    """
    Fetch emails from Gmail using Gmail API.
    
    Args:
        limit (int): Maximum number of emails to fetch (default: 50)
        days_back (int): Number of days to look back (default: 1)
    
    Returns:
        dict: Dictionary with 'emails' list and 'count', or 'error' if failed
    """
    emails = []
    today = datetime.now().date()
    lookback_days = max(0, days_back)
    allowed_dates = {today - timedelta(days=offset) for offset in range(lookback_days + 1)}
    
    creds = load_oauth_token('gmail')
    if not creds:
        return {'error': 'Gmail OAuth not configured. Please authenticate first.', 'needs_auth': True}
    
    try:
        service = build('gmail', 'v1', credentials=creds)
        
        # Calculate date range for query
        oldest_date = min(allowed_dates)
        query = f'after:{oldest_date.strftime("%Y/%m/%d")}'
        
        # List messages
        results = service.users().messages().list(
            userId='me',
            q=query,
            maxResults=min(limit, 500)
        ).execute()
        
        messages = results.get('messages', [])
        
        for msg_item in messages[:limit]:
            try:
                msg = service.users().messages().get(
                    userId='me',
                    id=msg_item['id'],
                    format='full'
                ).execute()
                
                payload = msg['payload']
                headers = payload.get('headers', [])
                
                # Extract headers
                subject_raw = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
                subject = decode_mime_words(subject_raw) if subject_raw else 'No Subject'
                from_addr_raw = next((h['value'] for h in headers if h['name'] == 'From'), '')
                from_addr = decode_mime_words(from_addr_raw) if from_addr_raw else ''
                to_addr_raw = next((h['value'] for h in headers if h['name'] == 'To'), '')
                to_addr = decode_mime_words(to_addr_raw) if to_addr_raw else ''
                date_str = next((h['value'] for h in headers if h['name'] == 'Date'), '')
                
                # Parse date
                date_obj = None
                date_formatted = date_str
                try:
                    parsed_dt = email.utils.parsedate_to_datetime(date_str)
                    if parsed_dt:
                        if parsed_dt.tzinfo is not None:
                            parsed_dt = parsed_dt.astimezone().replace(tzinfo=None)
                        date_obj = parsed_dt
                        date_formatted = date_obj.strftime('%Y-%m-%d %H:%M:%S')
                except Exception:
                    pass
                
                if not date_obj or date_obj.date() not in allowed_dates:
                    continue
                
                # Extract body and attachments
                body_plain = ''
                body_html = ''
                attachments = []
                
                def extract_parts(parts):
                    nonlocal body_plain, body_html, attachments
                    for part in parts:
                        mime_type = part.get('mimeType', '')
                        filename = part.get('filename', '')
                        body_data = part.get('body', {})
                        attachment_id = body_data.get('attachmentId')
                        
                        # Extract headers for Content-ID and Content-Disposition
                        headers = part.get('headers', [])
                        content_id = ''
                        content_disposition = ''
                        for header in headers:
                            header_name = header.get('name', '').lower()
                            if header_name == 'content-id':
                                content_id = header.get('value', '').strip()
                            elif header_name == 'content-disposition':
                                content_disposition = header.get('value', '').lower()
                        
                        # Check if it's an attachment
                        if attachment_id:
                            try:
                                att_data = service.users().messages().attachments().get(
                                    userId='me',
                                    messageId=msg_item['id'],
                                    id=attachment_id
                                ).execute()
                                
                                # Gmail API returns base64url encoded data
                                file_data = base64.urlsafe_b64decode(att_data['data'])
                                
                                attachments.append({
                                    'filename': filename or f'attachment_{len(attachments) + 1}',
                                    'content_type': mime_type or 'application/octet-stream',
                                    'size': len(file_data),
                                    'data': base64.b64encode(file_data).decode('ascii'),
                                    'content_id': content_id,
                                    'content_disposition': content_disposition
                                })
                            except Exception as att_exc:
                                print(f"Error fetching attachment: {att_exc}")
                                continue
                        elif filename and mime_type not in ['text/plain', 'text/html']:
                            # Inline attachment without attachmentId - try to get from body data
                            data = body_data.get('data', '')
                            if data:
                                try:
                                    file_data = base64.urlsafe_b64decode(data)
                                    attachments.append({
                                        'filename': filename,
                                        'content_type': mime_type or 'application/octet-stream',
                                        'size': len(file_data),
                                        'data': base64.b64encode(file_data).decode('ascii'),
                                        'content_id': content_id,
                                        'content_disposition': content_disposition
                                    })
                                except Exception:
                                    pass
                        else:
                            # Extract body text
                            data = body_data.get('data', '')
                            if data:
                                try:
                                    decoded = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                                    if mime_type == 'text/plain' and not body_plain:
                                        body_plain = decoded
                                    elif mime_type == 'text/html' and not body_html:
                                        body_html = decoded
                                except Exception:
                                    pass
                        
                        # Recursively process nested parts
                        if 'parts' in part:
                            extract_parts(part['parts'])
                
                # Process payload
                if 'parts' in payload:
                    extract_parts(payload['parts'])
                else:
                    # Single part message
                    mime_type = payload.get('mimeType', '')
                    body_data = payload.get('body', {})
                    data = body_data.get('data', '')
                    if data:
                        try:
                            decoded = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                            if mime_type == 'text/html':
                                body_html = decoded
                            else:
                                body_plain = decoded
                        except Exception:
                            pass
                
                preview_source = (body_plain or strip_html_tags(body_html) or '').strip()
                preview = preview_source[:500] + '...' if len(preview_source) > 500 else preview_source
                sequence_code = build_sequence_code(from_addr, date_obj)
                
                emails.append({
                    'id': msg_item['id'],
                    'subject': subject,
                    'from': from_addr,
                    'to': to_addr,
                    'date': date_formatted,
                    'preview': preview,
                    'plain_body': body_plain,
                    'html_body': body_html,
                    'sequence': sequence_code,
                    'attachments': attachments
                })
            except Exception as e:
                print(f"Error processing email {msg_item.get('id', 'unknown')}: {str(e)}")
                continue
        
        return {'emails': emails, 'count': len(emails)}
    except HttpError as e:
        error_str = str(e)
        # Check if it's an authentication error
        if 'invalid_grant' in error_str.lower() or 'token has been expired' in error_str.lower() or 'revoked' in error_str.lower():
            # Clear the invalid token
            try:
                connection = get_db_connection()
                cursor = connection.cursor()
                cursor.execute("DELETE FROM oauth_tokens WHERE provider = ?", ('gmail',))
                connection.commit()
                cursor.close()
                connection.close()
            except Exception:
                pass
            return {'error': 'Gmail OAuth token has expired or been revoked. Please re-authenticate.', 'needs_auth': True}
        return {'error': f'Gmail API error: {error_str}'}
    except Exception as e:
        error_str = str(e)
        # Check if it's an authentication error
        if 'invalid_grant' in error_str.lower() or 'token has been expired' in error_str.lower() or 'revoked' in error_str.lower():
            # Clear the invalid token
            try:
                connection = get_db_connection()
                cursor = connection.cursor()
                cursor.execute("DELETE FROM oauth_tokens WHERE provider = ?", ('gmail',))
                connection.commit()
                cursor.close()
                connection.close()
            except Exception:
                pass
            return {'error': 'Gmail OAuth token has expired or been revoked. Please re-authenticate.', 'needs_auth': True}
        return {'error': f'Error fetching Gmail: {error_str}'}


def fetch_emails(imap_server, port, username, password, use_ssl=True, use_tls=False, limit=50, days_back=0, folder='INBOX'):
    """
    Fetch emails from IMAP server.
    
    Args:
        imap_server (str): IMAP server address
        port (int): IMAP server port
        username (str): Username for authentication
        password (str): Password for authentication
        use_ssl (bool): Use SSL connection (default: True)
        use_tls (bool): Use TLS connection (default: False)
        limit (int): Maximum number of emails to fetch (default: 50)
        days_back (int): Number of days to look back (default: 0)
        folder (str): IMAP folder to fetch from (default: 'INBOX', can be 'Sent Items', 'Sent', etc.)
    
    Returns:
        dict: Dictionary with 'emails' list and 'count', or 'error' if failed
    """
    emails = []
    today = datetime.now().date()
    lookback_days = max(0, days_back)
    allowed_dates = {today - timedelta(days=offset) for offset in range(lookback_days + 1)}

    def _imap_date(d: date) -> str:
        """
        Format date in the fixed English month format required by IMAP
        servers, independent of OS locale. Using strftime('%d-%b-%Y')
        can produce non-English month names on some systems (e.g. Chinese
        locale on Windows), which causes IMAP errors like b'ERR.PARAM'.
        """
        month_abbr = [
            "",  # 1-based index
            "Jan", "Feb", "Mar", "Apr", "May", "Jun",
            "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
        ]
        return f"{d.day:02d}-{month_abbr[d.month]}-{d.year}"

    def _clean_content_id(raw: Optional[str]) -> str:
        if not raw:
            return ''
        return raw.strip().strip('<>').strip()
    
    try:
        # Create SSL context
        context = ssl.create_default_context()
        
        # Connect to IMAP server based on SSL/TLS settings
        if use_ssl:
            mail = imaplib.IMAP4_SSL(imap_server, port, ssl_context=context)
        else:
            mail = imaplib.IMAP4(imap_server, port)
            if use_tls:
                mail.starttls()
        
        mail.login(username, password)
        mail.select(folder)
        
        # Search for recent emails - fetch all emails in date range (with and without attachments)
        oldest_date = min(allowed_dates)
        since_clause = f'(SINCE { _imap_date(oldest_date) })'
        status, messages = mail.search(None, since_clause)
        email_ids = []
        if status == 'OK' and messages and len(messages) > 0:
            email_ids = [seq_id for seq_id in messages[0].split() if seq_id and seq_id.strip()]
        
        # Get the most recent emails (limit)
        if email_ids:
            email_ids = sorted(email_ids, key=lambda eid: int(eid))
        email_ids = email_ids[-limit:] if len(email_ids) > limit else email_ids
        
        for email_id in reversed(email_ids):
            try:
                status, msg_data = mail.fetch(email_id, '(RFC822)')
                if status != 'OK':
                    continue
                
                email_body = msg_data[0][1]
                msg = email.message_from_bytes(email_body)
                
                # Extract email details
                subject = decode_mime_words(msg.get('Subject', ''))
                from_addr = decode_mime_words(msg.get('From', ''))
                to_addr = decode_mime_words(msg.get('To', ''))
                date_str = msg.get('Date', '')
                
                # Parse date
                date_obj = None
                date_formatted = date_str
                try:
                    parsed_dt = email.utils.parsedate_to_datetime(date_str)
                    if parsed_dt:
                        if parsed_dt.tzinfo is not None:
                            parsed_dt = parsed_dt.astimezone().replace(tzinfo=None)
                        date_obj = parsed_dt
                        date_formatted = date_obj.strftime('%Y-%m-%d %H:%M:%S')
                except Exception:
                    pass

                if not date_obj or date_obj.date() not in allowed_dates:
                    continue

                # Get email body (plain and html) and attachments
                body_plain = ''
                body_html = ''
                attachments = []

                if msg.is_multipart():
                    for part in msg.walk():
                        content_type = part.get_content_type()
                        content_disposition = str(part.get("Content-Disposition") or "").lower()
                        content_id = _clean_content_id(part.get("Content-ID"))
                        filename = part.get_filename()

                        # More thorough attachment detection
                        is_attachment = (
                            'attachment' in content_disposition or
                            bool(filename) or
                            (content_type not in ['text/plain', 'text/html', 'multipart/alternative', 'multipart/related', 'multipart/mixed'] and 
                             'inline' not in content_disposition)
                        )

                        # Only extract body from non-attachment text parts
                        if not is_attachment:
                            if content_type == "text/plain" and not body_plain:
                                try:
                                    payload = part.get_payload(decode=True)
                                    if payload:
                                        # Get charset from Content-Type header
                                        charset = part.get_content_charset() or 'utf-8'
                                        try:
                                            body_plain = payload.decode(charset, errors='replace')
                                        except (LookupError, UnicodeDecodeError):
                                            # Try common encodings if specified charset fails
                                            for enc in ['utf-8', 'gb18030', 'gb2312', 'gbk', 'big5', 'latin1', 'iso-8859-1']:
                                                try:
                                                    body_plain = payload.decode(enc, errors='replace')
                                                    break
                                                except (LookupError, UnicodeDecodeError):
                                                    continue
                                            else:
                                                # Last resort: ignore errors
                                                body_plain = payload.decode('utf-8', errors='ignore')
                                except Exception:
                                    pass
                            elif content_type == "text/html" and not body_html:
                                try:
                                    payload = part.get_payload(decode=True)
                                    if payload:
                                        # Get charset from Content-Type header
                                        charset = part.get_content_charset() or 'utf-8'
                                        try:
                                            body_html = payload.decode(charset, errors='replace')
                                        except (LookupError, UnicodeDecodeError):
                                            # Try common encodings if specified charset fails
                                            for enc in ['utf-8', 'gb18030', 'gb2312', 'gbk', 'big5', 'latin1', 'iso-8859-1']:
                                                try:
                                                    body_html = payload.decode(enc, errors='replace')
                                                    break
                                                except (LookupError, UnicodeDecodeError):
                                                    continue
                                            else:
                                                # Last resort: ignore errors
                                                body_html = payload.decode('utf-8', errors='ignore')
                                except Exception:
                                    pass

                        # Extract attachments
                        if is_attachment:
                            try:
                                payload = part.get_payload(decode=True)
                                if payload is None:
                                    payload = b''
                                elif not isinstance(payload, bytes):
                                    payload = str(payload).encode('utf-8')
                                
                                decoded_filename = decode_mime_words(filename) if filename else f'attachment_{len(attachments) + 1}'
                                
                                # Skip empty attachments
                                if len(payload) > 0:
                                    attachments.append({
                                        'filename': decoded_filename,
                                        'content_type': content_type or 'application/octet-stream',
                                        'size': len(payload),
                                        'data': base64.b64encode(payload).decode('ascii'),
                                        'content_id': content_id,
                                        'content_disposition': content_disposition
                                    })
                            except Exception as att_exc:
                                print(f"Error extracting attachment: {att_exc}")
                                continue
                else:
                    content_type = msg.get_content_type()
                    filename = msg.get_filename()
                    is_attachment = bool(filename)
                    content_id = _clean_content_id(msg.get("Content-ID"))
                    content_disposition = str(msg.get("Content-Disposition") or "").lower()
                    try:
                        payload = msg.get_payload(decode=True)
                        if isinstance(payload, bytes):
                            # Get charset from Content-Type header
                            charset = msg.get_content_charset() or 'utf-8'
                            try:
                                decoded = payload.decode(charset, errors='replace')
                            except (LookupError, UnicodeDecodeError):
                                # Try common encodings if specified charset fails
                                for enc in ['utf-8', 'gb18030', 'gb2312', 'gbk', 'big5', 'latin1', 'iso-8859-1']:
                                    try:
                                        decoded = payload.decode(enc, errors='replace')
                                        break
                                    except (LookupError, UnicodeDecodeError):
                                        continue
                                else:
                                    # Last resort: ignore errors
                                    decoded = payload.decode('utf-8', errors='ignore')
                        else:
                            decoded = str(payload)
                    except Exception:
                        payload = b''
                        decoded = str(msg.get_payload())

                    if is_attachment:
                        attachments.append({
                            'filename': decode_mime_words(filename) if filename else 'attachment',
                            'content_type': content_type,
                            'size': len(payload or b''),
                            'data': base64.b64encode(payload or b'').decode('ascii'),
                            'content_id': content_id,
                            'content_disposition': content_disposition
                        })
                    elif content_type == "text/html":
                        body_html = decoded
                    else:
                        body_plain = decoded

                preview_source = (body_plain or strip_html_tags(body_html) or '').strip()
                preview = preview_source[:500] + '...' if len(preview_source) > 500 else preview_source
                sequence_code = build_sequence_code(from_addr, date_obj)
                
                emails.append({
                    'id': email_id.decode(),
                    'subject': subject,
                    'from': from_addr,
                    'to': to_addr,
                    'date': date_formatted,
                    'preview': preview,
                    'plain_body': body_plain,
                    'html_body': body_html,
                    'sequence': sequence_code,
                    'attachments': attachments
                })
            except Exception as e:
                print(f"Error processing email {email_id}: {str(e)}")
                continue
        
        mail.close()
        mail.logout()
        
    except Exception as e:
        print(f"Error fetching emails: {str(e)}")
        return {'error': str(e)}
    
    return {'emails': emails, 'count': len(emails)}

