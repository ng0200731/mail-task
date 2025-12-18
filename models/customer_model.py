"""
Customer model for MailTask application.
Handles customer database operations.
"""
from datetime import datetime
from flask import session
from utils.db_utils import get_db_connection


def insert_customer(name: str, email_suffix: str, country: str = None, website: str = None, remark: str = None, attachments: str = None, company_name: str = None, tel: str = None, source: str = None, address: str = None, business_type: str = None, created_by: str = None) -> int:
    """
    Insert a new customer into the database.
    
    Args:
        name (str): Customer name
        email_suffix (str): Email suffix (domain part)
        country (str, optional): Country
        website (str, optional): Website URL
        remark (str, optional): Remarks
        attachments (str, optional): Attachments JSON string
        company_name (str, optional): Company name
        tel (str, optional): Telephone number
        source (str, optional): Customer source
        address (str, optional): Address
        business_type (str, optional): Business type
        created_by (str, optional): User email who created this customer.
                                    If None, will use session.get('user_email') or default.
    
    Returns:
        int: Customer ID
    """
    if created_by is None:
        created_by = session.get('user_email', 'eric.brilliant@gmail.com')
    
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute(
        "INSERT INTO customers (name, email_suffix, country, website, remark, attachments, company_name, tel, source, address, business_type, created_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (name, email_suffix, country, website, remark, attachments, company_name, tel, source, address, business_type, created_by)
    )
    connection.commit()
    customer_id = cursor.lastrowid
    cursor.close()
    connection.close()
    return customer_id


def fetch_customers(created_by: str = None):
    """
    Fetch customers from database.
    
    Args:
        created_by (str, optional): Filter by user email.
                                    If None, will use session.get('user_email').
    
    Returns:
        list: List of customer dictionaries
    """
    if created_by is None:
        user_email = session.get('user_email')
        if not user_email:
            return []
        created_by = user_email
    else:
        if not created_by:
            return []
    
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute("""
        SELECT id, name, email_suffix, country, website, remark, attachments, company_name, tel, source, address, business_type, created_at, created_by
        FROM customers
        WHERE created_by = ?
        ORDER BY datetime(created_at) DESC
    """, (created_by,))
    rows = cursor.fetchall()
    cursor.close()
    connection.close()

    customers = []
    for row in rows:
        created_at = row['created_at']
        if created_at:
            try:
                created_at_iso = datetime.fromisoformat(created_at.replace(' ', 'T'))
                created_at = created_at_iso.isoformat()
            except ValueError:
                pass

        # Handle new columns that may not exist in old databases
        country = None
        website = None
        remark = None
        attachments = None
        try:
            country = row['country'] if row['country'] else None
        except (KeyError, IndexError):
            pass
        try:
            website = row['website'] if row['website'] else None
        except (KeyError, IndexError):
            pass
        try:
            remark = row['remark'] if row['remark'] else None
        except (KeyError, IndexError):
            pass
        try:
            attachments = row['attachments'] if row['attachments'] else None
        except (KeyError, IndexError):
            pass
        try:
            company_name = row['company_name'] if row['company_name'] else None
        except (KeyError, IndexError):
            company_name = None
        try:
            tel = row['tel'] if row['tel'] else None
        except (KeyError, IndexError):
            tel = None
        try:
            source = row['source'] if row['source'] else None
        except (KeyError, IndexError):
            source = None
        try:
            address = row['address'] if row['address'] else None
        except (KeyError, IndexError):
            address = None
        try:
            business_type = row['business_type'] if row['business_type'] else None
        except (KeyError, IndexError):
            business_type = None
        try:
            created_by_val = row['created_by'] if row['created_by'] else None
        except (KeyError, IndexError):
            created_by_val = None

        customers.append({
            'id': row['id'],
            'name': row['name'],
            'email_suffix': row['email_suffix'],
            'country': country,
            'website': website,
            'source': source,
            'remark': remark,
            'attachments': attachments,
            'company_name': company_name,
            'tel': tel,
            'address': address,
            'business_type': business_type,
            'created_at': created_at,
            'created_by': created_by_val
        })
    return customers

