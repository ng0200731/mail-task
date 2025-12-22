"""
Database utility functions for MailTask application.
Handles database connection and initialization.
"""
import sqlite3
from config import CUSTOMER_DB_PATH


def get_db_connection():
    """
    Get a database connection with Row factory enabled.
    Ensures UTF-8 encoding for proper handling of international characters.
    
    Returns:
        sqlite3.Connection: Database connection with row_factory set to sqlite3.Row
    """
    connection = sqlite3.connect(str(CUSTOMER_DB_PATH), detect_types=sqlite3.PARSE_DECLTYPES)
    connection.row_factory = sqlite3.Row
    # Ensure UTF-8 encoding for text data
    connection.execute("PRAGMA encoding = 'UTF-8'")
    return connection


def initialize_database():
    """
    Initialize the database schema and create all required tables.
    Handles migrations for existing tables by adding new columns if they don't exist.
    """
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email_suffix TEXT NOT NULL,
                country TEXT,
                website TEXT,
                remark TEXT,
                attachments TEXT,
                company_name TEXT,
                tel TEXT,
                source TEXT,
                address TEXT,
                business_type TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                created_by TEXT
            )
        """)
        # Migrate existing customers table to add new columns if they don't exist
        try:
            cursor.execute("ALTER TABLE customers ADD COLUMN country TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists
        try:
            cursor.execute("ALTER TABLE customers ADD COLUMN website TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists
        try:
            cursor.execute("ALTER TABLE customers ADD COLUMN remark TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists
        try:
            cursor.execute("ALTER TABLE customers ADD COLUMN attachments TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists
        try:
            cursor.execute("ALTER TABLE customers ADD COLUMN company_name TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists
        try:
            cursor.execute("ALTER TABLE customers ADD COLUMN tel TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists
        try:
            cursor.execute("ALTER TABLE customers ADD COLUMN source TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists
        try:
            cursor.execute("ALTER TABLE customers ADD COLUMN address TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists
        try:
            cursor.execute("ALTER TABLE customers ADD COLUMN business_type TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists
        try:
            cursor.execute("ALTER TABLE customers ADD COLUMN created_by TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists
        # Update existing records to set created_by
        cursor.execute("UPDATE customers SET created_by = 'eric.brilliant@gmail.com' WHERE created_by IS NULL")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS emails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider TEXT NOT NULL,
                email_uid TEXT NOT NULL,
                subject TEXT,
                from_addr TEXT,
                to_addr TEXT,
                date TEXT,
                preview TEXT,
                plain_body TEXT,
                html_body TEXT,
                sequence TEXT,
                attachments TEXT,
                fetched_at TEXT DEFAULT (datetime('now')),
                created_by TEXT,
                UNIQUE(provider, email_uid)
            )
        """)
        cursor.execute("PRAGMA table_info(emails)")
        email_columns = {row['name'] for row in cursor.fetchall()}
        # Migrate existing emails table to add new columns if they don't exist
        if 'subject' not in email_columns:
            try:
                cursor.execute("ALTER TABLE emails ADD COLUMN subject TEXT")
            except sqlite3.OperationalError:
                pass  # Column already exists or error occurred
        if 'attachments' not in email_columns:
            try:
                cursor.execute("ALTER TABLE emails ADD COLUMN attachments TEXT")
            except sqlite3.OperationalError:
                pass  # Column already exists
        if 'created_by' not in email_columns:
            try:
                cursor.execute("ALTER TABLE emails ADD COLUMN created_by TEXT")
            except sqlite3.OperationalError:
                pass  # Column already exists
        # Update existing records to set created_by
        cursor.execute("UPDATE emails SET created_by = 'eric.brilliant@gmail.com' WHERE created_by IS NULL")
        
        # OAuth tokens table for Gmail API
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS oauth_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider TEXT NOT NULL UNIQUE,
                token TEXT,
                refresh_token TEXT,
                token_uri TEXT,
                client_id TEXT,
                client_secret TEXT,
                scopes TEXT,
                updated_at TEXT DEFAULT (datetime('now'))
            )
        """)
        # OAuth states table for state parameter validation
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS oauth_states (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                state TEXT NOT NULL UNIQUE,
                client_id TEXT,
                client_secret TEXT,
                redirect_uri TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        # Clean up old states (older than 10 minutes)
        cursor.execute("""
            DELETE FROM oauth_states 
            WHERE datetime(created_at) < datetime('now', '-10 minutes')
        """)
        # Task types table for dropdown options
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS task_types (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                display_order INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        # Initialize default task types if table is empty
        cursor.execute("SELECT COUNT(*) as count FROM task_types")
        if cursor.fetchone()['count'] == 0:
            default_types = [
                ('need sample', 1),
                ('quotation', 2),
                ('outsource', 3)
            ]
            cursor.executemany("""
                INSERT INTO task_types (name, display_order) VALUES (?, ?)
            """, default_types)
        
        # Tasks table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sequence TEXT,
                customer TEXT,
                email TEXT,
                catalogue TEXT NOT NULL,
                template TEXT NOT NULL,
                attachments TEXT,
                deadline TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now')),
                created_by TEXT
            )
        """)
        try:
            cursor.execute("ALTER TABLE tasks ADD COLUMN deadline TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists
        try:
            cursor.execute("ALTER TABLE tasks ADD COLUMN email TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists
        cursor.execute("PRAGMA table_info(tasks)")
        task_columns = {row['name'] for row in cursor.fetchall()}
        if 'updated_at' not in task_columns:
            cursor.execute("ALTER TABLE tasks ADD COLUMN updated_at TEXT")
            cursor.execute("UPDATE tasks SET updated_at = created_at WHERE updated_at IS NULL")
        if 'created_by' not in task_columns:
            cursor.execute("ALTER TABLE tasks ADD COLUMN created_by TEXT")
        if 'status' not in task_columns:
            cursor.execute("ALTER TABLE tasks ADD COLUMN status TEXT DEFAULT 'open'")
            cursor.execute("UPDATE tasks SET status = 'open' WHERE status IS NULL")
        # Update existing records to set created_by
        cursor.execute("UPDATE tasks SET created_by = 'eric.brilliant@gmail.com' WHERE created_by IS NULL")
        # Countries table for dropdown options
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS countries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                display_order INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        # Customer sources table for dropdown options
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS customer_sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                display_order INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        # Initialize default customer sources if table is empty
        cursor.execute("SELECT COUNT(*) as count FROM customer_sources")
        if cursor.fetchone()['count'] == 0:
            default_sources = [
                ('2025 PT Jakarta Intl Expo', 1),
                ('Sales Referral', 2)
            ]
            cursor.executemany("""
                INSERT INTO customer_sources (name, display_order) VALUES (?, ?)
            """, default_sources)
        
        # Customer business types table for dropdown options
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS customer_business_types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            display_order INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        )
        """)
        # Initialize default customer business types if table is empty
        cursor.execute("SELECT COUNT(*) as count FROM customer_business_types")
        if cursor.fetchone()['count'] == 0:
            default_business_types = [
                ('Buyer', 1),
                ('Agent', 2),
                ('Garment Factory', 3)
            ]
            cursor.executemany("""
            INSERT INTO customer_business_types (name, display_order) VALUES (?, ?)
            """, default_business_types)
        
        # Task statuses table for dropdown options
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS task_statuses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            display_order INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        )
        """)
        # Initialize default task statuses if table is empty
        cursor.execute("SELECT COUNT(*) as count FROM task_statuses")
        if cursor.fetchone()['count'] == 0:
            default_statuses = [
                ('open', 1),
                ('close', 2)
            ]
            cursor.executemany("""
            INSERT INTO task_statuses (name, display_order) VALUES (?, ?)
            """, default_statuses)
        
        # Users/security table for tracking login history
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                level TEXT DEFAULT 'user',
                status TEXT DEFAULT 'active',
                created_at TEXT DEFAULT (datetime('now')),
                last_login TEXT,
                login_count INTEGER DEFAULT 0
            )
        """)
        
        # Initialize or update countries list
        default_countries = [
            ('India', 1),
            ('China', 2),
            ('United States', 3),
            ('Indonesia', 4),
            ('Pakistan', 5),
            ('Nigeria', 6),
            ('Brazil', 7),
            ('Bangladesh', 8),
            ('Russia', 9),
            ('Ethiopia', 10),
            ('Mexico', 11),
            ('Japan', 12),
            ('Egypt', 13),
            ('Philippines', 14),
            ('DR Congo', 15),
            ('Vietnam', 16),
            ('Iran', 17),
            ('Turkey', 18),
            ('Germany', 19),
            ('Thailand', 20),
            ('Tanzania', 21),
            ('United Kingdom', 22),
            ('France', 23),
            ('South Africa', 24),
            ('Italy', 25),
            ('Kenya', 26),
            ('Myanmar', 27),
            ('Colombia', 28),
            ('South Korea', 29),
            ('Sudan', 30),
            ('Uganda', 31),
            ('Spain', 32),
            ('Algeria', 33),
            ('Iraq', 34),
            ('Argentina', 35),
            ('Afghanistan', 36),
            ('Yemen', 37),
            ('Canada', 38),
            ('Angola', 39),
            ('Ukraine', 40),
            ('Morocco', 41),
            ('Poland', 42),
            ('Uzbekistan', 43),
            ('Malaysia', 44),
            ('Mozambique', 45),
            ('Ghana', 46),
            ('Peru', 47),
            ('Saudi Arabia', 48),
            ('Madagascar', 49),
            ('Côte d\'Ivoire', 50),
            ('Cameroon', 51),
            ('Nepal', 52),
            ('Venezuela', 53),
            ('Niger', 54),
            ('Australia', 55),
            ('North Korea', 56),
            ('Syria', 57),
            ('Mali', 58),
            ('Burkina Faso', 59),
            ('Sri Lanka', 60),
            ('Malawi', 61),
            ('Zambia', 62),
            ('Chad', 63),
            ('Kazakhstan', 64),
            ('Chile', 65),
            ('Somalia', 66),
            ('Senegal', 67),
            ('Romania', 68),
            ('Guatemala', 69),
            ('Netherlands', 70),
            ('Ecuador', 71),
            ('Cambodia', 72),
            ('Zimbabwe', 73),
            ('Guinea', 74),
            ('Benin', 75),
            ('Rwanda', 76),
            ('Burundi', 77),
            ('Bolivia', 78),
            ('Tunisia', 79),
            ('South Sudan', 80),
            ('Haiti', 81),
            ('Belgium', 82),
            ('Jordan', 83),
            ('Dominican Republic', 84),
            ('United Arab Emirates', 85),
            ('Honduras', 86),
            ('Cuba', 87),
            ('Tajikistan', 88),
            ('Papua New Guinea', 89),
            ('Sweden', 90),
            ('Czech Republic (Czechia)', 91),
            ('Portugal', 92),
            ('Azerbaijan', 93),
            ('Greece', 94),
            ('Togo', 95),
            ('Hungary', 96),
            ('Israel', 97),
            ('Austria', 98),
            ('Belarus', 99),
            ('Switzerland', 100),
            ('Sierra Leone', 101),
            ('Laos', 102),
            ('Turkmenistan', 103),
            ('Libya', 104),
            ('Kyrgyzstan', 105),
            ('Paraguay', 106),
            ('Nicaragua', 107),
            ('Bulgaria', 108),
            ('Serbia', 109),
            ('Congo', 110),
            ('El Salvador', 111),
            ('Denmark', 112),
            ('Singapore', 113),
            ('Lebanon', 114),
            ('Liberia', 115),
            ('Finland', 116),
            ('Norway', 117),
            ('State of Palestine', 118),
            ('Central African Republic', 119),
            ('Oman', 120),
            ('Slovakia', 121),
            ('Mauritania', 122),
            ('Ireland', 123),
            ('New Zealand', 124),
            ('Costa Rica', 125),
            ('Kuwait', 126),
            ('Panama', 127),
            ('Croatia', 128),
            ('Georgia', 129),
            ('Eritrea', 130),
            ('Mongolia', 131),
            ('Uruguay', 132),
            ('Bosnia and Herzegovina', 133),
            ('Qatar', 134),
            ('Namibia', 135),
            ('Moldova', 136),
            ('Armenia', 137),
            ('Jamaica', 138),
            ('Lithuania', 139),
            ('Gambia', 140),
            ('Albania', 141),
            ('Gabon', 142),
            ('Botswana', 143),
            ('Lesotho', 144),
            ('Guinea-Bissau', 145),
            ('Slovenia', 146),
            ('Equatorial Guinea', 147),
            ('Latvia', 148),
            ('North Macedonia', 149),
            ('Bahrain', 150),
            ('Trinidad and Tobago', 151),
            ('Timor-Leste', 152),
            ('Cyprus', 153),
            ('Estonia', 154),
            ('Mauritius', 155),
            ('Eswatini', 156),
            ('Djibouti', 157),
            ('Fiji', 158),
            ('Comoros', 159),
            ('Solomon Islands', 160),
            ('Guyana', 161),
            ('Bhutan', 162),
            ('Luxembourg', 163),
            ('Suriname', 164),
            ('Montenegro', 165),
            ('Malta', 166),
            ('Maldives', 167),
            ('Cabo Verde', 168),
            ('Brunei', 169),
            ('Belize', 170),
            ('Bahamas', 171),
            ('Iceland', 172),
            ('Vanuatu', 173),
            ('Barbados', 174),
            ('Sao Tome & Principe', 175),
            ('Samoa', 176),
            ('Saint Lucia', 177),
            ('Kiribati', 178),
            ('Seychelles', 179),
            ('Grenada', 180),
            ('Micronesia', 181),
            ('Tonga', 182),
            ('St. Vincent & Grenadines', 183),
            ('Antigua and Barbuda', 184),
            ('Andorra', 185),
            ('Dominica', 186),
            ('Saint Kitts & Nevis', 187),
            ('Liechtenstein', 188),
            ('Monaco', 189),
            ('Marshall Islands', 190),
            ('San Marino', 191),
            ('Palau', 192),
            ('Nauru', 193),
            ('Tuvalu', 194),
            ('Holy See', 195)
        ]
        # Replace all countries with the new list
        cursor.execute("DELETE FROM countries")
        cursor.executemany("""
            INSERT INTO countries (name, display_order) VALUES (?, ?)
        """, default_countries)
        connection.commit()
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

