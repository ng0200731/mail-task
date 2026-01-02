#!/usr/bin/env python
"""
Script to fix missing customer_ranks table
"""
import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from utils.db_utils import get_db_connection, initialize_database

def fix_customer_ranks():
    """Create customer_ranks table if it doesn't exist"""
    print("Initializing database...")
    try:
        initialize_database()
        print("✓ Database initialized successfully")
    except Exception as e:
        print(f"✗ Error during initialization: {e}")
        return False
    
    # Verify the table exists
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='customer_ranks'")
        result = cursor.fetchone()
        if result:
            print("✓ customer_ranks table exists")
            # Check if it has data
            cursor.execute("SELECT COUNT(*) as count FROM customer_ranks")
            count = cursor.fetchone()['count']
            print(f"✓ customer_ranks table has {count} records")
            if count == 0:
                print("  Adding default ranks (A, B, C, D)...")
                default_ranks = [
                    ('A', 1),
                    ('B', 2),
                    ('C', 3),
                    ('D', 4)
                ]
                cursor.executemany("""
                    INSERT INTO customer_ranks (name, display_order) VALUES (?, ?)
                """, default_ranks)
                connection.commit()
                print("✓ Default ranks added")
        else:
            print("✗ customer_ranks table does not exist - creating it...")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS customer_ranks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    display_order INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT (datetime('now'))
                )
            """)
            connection.commit()
            print("✓ customer_ranks table created")
            # Add default ranks
            default_ranks = [
                ('A', 1),
                ('B', 2),
                ('C', 3),
                ('D', 4)
            ]
            cursor.executemany("""
                INSERT INTO customer_ranks (name, display_order) VALUES (?, ?)
            """, default_ranks)
            connection.commit()
            print("✓ Default ranks (A, B, C, D) added")
        
        cursor.close()
        connection.close()
        print("\n✓ All done! Please restart your Flask application.")
        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

if __name__ == '__main__':
    fix_customer_ranks()

