"""
Email parsing utility functions for MailTask application.
Handles MIME decoding, HTML stripping, and sequence code generation.
"""
import re
import email.utils
from email.header import decode_header
from datetime import datetime
from typing import Optional


def decode_mime_words(s):
    """
    Decode MIME encoded words in email headers.
    
    Args:
        s (str or None): MIME encoded string (e.g., "=?UTF-8?B?...?=")
    
    Returns:
        str: Decoded string, empty string if input is None
    """
    if s is None:
        return ''
    decoded_fragments = decode_header(s)
    decoded_str = ''
    for fragment, encoding in decoded_fragments:
        if isinstance(fragment, bytes):
            # Try the specified encoding first
            enc = encoding or 'utf-8'
            try:
                decoded_str += fragment.decode(enc, errors='replace')
            except (LookupError, UnicodeDecodeError):
                # Try common encodings if specified encoding fails
                # Try broader set of common encodings, including gb18030 for Chinese
                for fallback_enc in ['utf-8', 'gb18030', 'gb2312', 'gbk', 'big5', 'latin1', 'iso-8859-1']:
                    try:
                        decoded_str += fragment.decode(fallback_enc, errors='replace')
                        break
                    except (LookupError, UnicodeDecodeError):
                        continue
                else:
                    # Last resort: ignore errors
                    decoded_str += fragment.decode('utf-8', errors='ignore')
        else:
            decoded_str += fragment
    return decoded_str


def strip_html_tags(text):
    """
    Remove HTML tags from text for preview purposes.
    
    Args:
        text (str or None): HTML text
    
    Returns:
        str: Plain text without HTML tags, empty string if input is None or empty
    """
    if not text:
        return ''
    return re.sub(r'<[^>]+>', '', text)


def build_sequence_code(from_address: str, email_date: Optional[datetime] = None) -> str:
    """
    Construct a sequence code in format: yyyymmdd_hhmmss_<two letters>_<domain>.
    
    Args:
        from_address (str): Email address of the sender
        email_date (Optional[datetime]): Email date/time, defaults to current time
    
    Returns:
        str: Sequence code in format yyyymmdd_hhmmss_<prefix>_<domain>
             Example: "20251219_143022_qu_prostretch"
    """
    email_datetime = email_date or datetime.now()
    sequence_date = email_datetime.strftime('%Y%m%d_%H%M%S')
    
    parsed_email = email.utils.parseaddr(from_address)[1].lower() if from_address else ''
    local_part = ''
    domain_part = ''

    if parsed_email and '@' in parsed_email:
        local_part, domain_part = parsed_email.split('@', 1)
    elif parsed_email:
        local_part = parsed_email

    letters = [ch for ch in local_part if ch.isalpha()]
    if len(letters) >= 2:
        prefix = ''.join(letters[:2]).lower()
    elif len(letters) == 1:
        prefix = letters[0].lower() + 'x'
    else:
        prefix = 'xx'

    domain_label = ''
    if domain_part:
        first_label = domain_part.split('.')[0]
        domain_label = ''.join(ch for ch in first_label if ch.isalnum()).lower()
    if not domain_label:
        domain_label = 'domain'

    return f'{sequence_date}_{prefix}_{domain_label}'

