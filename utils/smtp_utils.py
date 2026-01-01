"""
SMTP utility functions for MailTask application.
Handles SMTP configuration sanitization and email sending with automatic fallback.
"""
import ssl
import smtplib
import base64
import email.utils
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from config import VERIFY_SSL_CERTIFICATES


def build_smtp_config_list(configs):
    """
    Construct a sanitized list of SMTP configuration dictionaries.
    
    Args:
        configs (list): List of SMTP configuration dictionaries
    
    Returns:
        list: Sanitized list of SMTP configurations with required fields validated
    """
    sanitized = []
    for cfg in configs:
        if not cfg:
            continue
        server = cfg.get('server')
        username = cfg.get('username')
        password = cfg.get('password')
        if not server or not username or not password:
            continue

        sanitized.append({
            'name': cfg.get('name', server),
            'server': server,
            'port': int(cfg.get('port') or (465 if cfg.get('use_ssl') else 587)),
            'use_ssl': bool(cfg.get('use_ssl')),
            'use_tls': bool(cfg.get('use_tls')),
            'username': username,
            'password': password,
            'timeout': int(cfg.get('timeout') or 10),
            'sender_name': cfg.get('sender_name'),
            'from_address': cfg.get('from_address') or username
        })
    return sanitized


def send_email_with_configs(configs, subject, body, recipients, is_html=False, sender_name=None, attachments=None):
    """
    Attempt to send email using provided SMTP configs with automatic fallback.
    
    Args:
        configs (list): List of SMTP configuration dictionaries (will try each in order)
        subject (str): Email subject
        body (str): Email body (HTML or plain text)
        recipients (list): List of recipient email addresses
        is_html (bool): Whether body is HTML format
        sender_name (str, optional): Display name for sender
        attachments (list, optional): List of attachment dictionaries with 'type', 'data', 'filename', etc.
    
    Returns:
        dict: Result dictionary with 'success' key and either:
              - {'success': True, 'provider': str} if successful
              - {'success': False, 'errors': list} if all attempts failed
    """
    attempts = []
    attachments = attachments or []
    
    for cfg in configs:
        smtp = None
        try:
            if cfg.get('use_ssl'):
                # Create SSL context with configurable certificate verification
                context = ssl.create_default_context()
                if not VERIFY_SSL_CERTIFICATES:
                    # Only disable verification if explicitly configured (for enterprise servers)
                    context.check_hostname = False
                    context.verify_mode = ssl.CERT_NONE
                smtp = smtplib.SMTP_SSL(cfg['server'], cfg['port'], timeout=cfg.get('timeout', 10), context=context)
            else:
                smtp = smtplib.SMTP(cfg['server'], cfg['port'], timeout=cfg.get('timeout', 10))
                if cfg.get('use_tls'):
                    # Create SSL context for STARTTLS with configurable certificate verification
                    context = ssl.create_default_context()
                    if not VERIFY_SSL_CERTIFICATES:
                        # Only disable verification if explicitly configured (for enterprise servers)
                        context.check_hostname = False
                        context.verify_mode = ssl.CERT_NONE
                    smtp.starttls(context=context)

            smtp.login(cfg['username'], cfg['password'])

            # Use MIMEMultipart if there are attachments, otherwise use MIMEText
            if attachments and len(attachments) > 0:
                msg = MIMEMultipart()
            else:
                msg = MIMEText(body or '', 'html' if is_html else 'plain', 'utf-8')
            
            from_address = cfg.get('from_address') or cfg['username']
            display_name = sender_name or cfg.get('sender_name') or from_address
            msg['From'] = email.utils.formataddr((display_name, from_address))
            msg['To'] = ', '.join(recipients)
            msg['Subject'] = subject or ''
            
            # If multipart, add body as a part
            if attachments and len(attachments) > 0:
                # Add YouTube links to body if HTML
                youtube_links = [att for att in attachments if att.get('type') == 'youtube']
                email_body = body or ''
                if youtube_links and is_html:
                    youtube_html = '<br><br><strong>YouTube Links:</strong><br>'
                    for yt in youtube_links:
                        video_id = yt.get('video_id', '')
                        url = yt.get('url', f'https://www.youtube.com/watch?v={video_id}')
                        thumbnail = yt.get('thumbnail_url', f'https://img.youtube.com/vi/{video_id}/0.jpg')
                        youtube_html += f'<a href="{url}" target="_blank"><img src="{thumbnail}" alt="YouTube Video" style="max-width: 200px; margin: 5px;"></a>'
                    email_body = email_body + youtube_html
                
                body_part = MIMEText(email_body, 'html' if is_html else 'plain', 'utf-8')
                msg.attach(body_part)
                
                # Add file attachments
                for att in attachments:
                    if att.get('type') == 'file' and att.get('data'):
                        try:
                            filename = att.get('filename', 'attachment')
                            content_type = att.get('content_type', 'application/octet-stream')
                            file_data = base64.b64decode(att['data'])
                            
                            part = MIMEBase('application', 'octet-stream')
                            part.set_payload(file_data)
                            encoders.encode_base64(part)
                            part.add_header(
                                'Content-Disposition',
                                f'attachment; filename= {filename}'
                            )
                            msg.attach(part)
                        except Exception as att_exc:
                            print(f"Error attaching file {att.get('filename', 'unknown')}: {att_exc}")
                            continue

            smtp.sendmail(from_address, recipients, msg.as_string())
            smtp.quit()
            return {'success': True, 'provider': cfg.get('name', cfg['server'])}
        except smtplib.SMTPAuthenticationError as exc:
            error_msg = f'Authentication failed: {str(exc)}'
            attempts.append({'provider': cfg.get('name', cfg['server']), 'error': error_msg})
            if smtp:
                try:
                    smtp.quit()
                except Exception:
                    pass
        except smtplib.SMTPServerDisconnected as exc:
            error_msg = f'Server disconnected: {str(exc)}. Check server, port, and SSL/TLS settings.'
            attempts.append({'provider': cfg.get('name', cfg['server']), 'error': error_msg})
            if smtp:
                try:
                    smtp.quit()
                except Exception:
                    pass
        except Exception as exc:
            error_msg = f'{type(exc).__name__}: {str(exc)}'
            attempts.append({'provider': cfg.get('name', cfg['server']), 'error': error_msg})
            if smtp:
                try:
                    smtp.quit()
                except Exception:
                    pass
    return {'success': False, 'errors': attempts}

