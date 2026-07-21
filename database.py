import sqlite3
from datetime import datetime, timedelta
import json

DATABASE_NAME = 'restaurant.db'

def get_db_connection():
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('manager', 'waiter', 'chef', 'cashier')),
            full_name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS menu_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            description TEXT,
            image TEXT DEFAULT '🍽️',
            category TEXT NOT NULL CHECK(category IN ('Appetizer', 'Main Course', 'Dessert', 'Beverage', 'Side Dish', 'Lasa Specialty')),
            availability INTEGER DEFAULT 1,
            order_count INTEGER DEFAULT 0,
            image_type TEXT DEFAULT 'emoji',
            image_size INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS restaurant_tables (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_number INTEGER UNIQUE NOT NULL,
            capacity TEXT NOT NULL,
            status TEXT DEFAULT 'available' CHECK(status IN ('available', 'occupied')),
            current_order_id INTEGER,
            current_waiter_id INTEGER,
            occupied_since TIMESTAMP,
            FOREIGN KEY (current_order_id) REFERENCES orders(id),
            FOREIGN KEY (current_waiter_id) REFERENCES users(id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_number TEXT,
            table_number INTEGER NOT NULL,
            waiter_name TEXT NOT NULL,
            waiter_id INTEGER,
            items TEXT NOT NULL,
            total REAL NOT NULL,
            status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'preparing', 'served', 'completed', 'cancelled')),
            order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            payment_method TEXT,
            paid_amount REAL,
            change_amount REAL,
            discount REAL DEFAULT 0,
            subtotal REAL,
            tax REAL,
            cashier TEXT,
            payment_time TIMESTAMP,
            bill_requested INTEGER DEFAULT 0,
            cashier_notes TEXT,
            special_requests TEXT,
            customer_count INTEGER DEFAULT 1
        )
    ''')
    
    fix_missing_columns()
    enhance_database_for_images()
    
    default_users = [
        ('manager', 'admin123', 'manager', 'Admin Manager', 'manager@restaurant.com', '09171234567'),
        ('chef', 'chef123', 'chef', 'Head Chef', 'chef@restaurant.com', '09171234568'),
        ('cashier', 'cashier123', 'cashier', 'Cashier Staff', 'cashier@restaurant.com', '09171234569')
    ]
    
    for username, password, role, full_name, email, phone in default_users:
        cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
        if not cursor.fetchone():
            cursor.execute(
                'INSERT INTO users (username, password, role, full_name, email, phone, is_active) VALUES (?, ?, ?, ?, ?, ?, ?)',
                (username, password, role, full_name, email, phone, 1)
            )
    
    cursor.execute("SELECT COUNT(*) FROM restaurant_tables")
    if cursor.fetchone()[0] == 0:
        for i in range(1, 13):
            capacity = '3-5p' if i <= 4 else ('4-6p' if i <= 7 else ('6-8p' if i <= 9 else ('8-10p' if i <= 11 else '10-12p')))
            cursor.execute(
                'INSERT INTO restaurant_tables (table_number, capacity) VALUES (?, ?)',
                (i, capacity)
            )
    
    conn.commit()
    conn.close()

def fix_missing_columns():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("PRAGMA table_info(users)")
        user_columns = [col[1] for col in cursor.fetchall()]
        
        if 'is_active' not in user_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN is_active INTEGER DEFAULT 1")
        
        cursor.execute("PRAGMA table_info(orders)")
        order_columns = [col[1] for col in cursor.fetchall()]
        
        missing_columns = [
            ('bill_requested', 'INTEGER DEFAULT 0'),
            ('cashier_notes', 'TEXT'),
            ('special_requests', 'TEXT'),
            ('order_number', 'TEXT'),
            ('subtotal', 'REAL'),
            ('tax', 'REAL'),
            ('discount', 'REAL DEFAULT 0'),
            ('payment_method', 'TEXT'),
            ('paid_amount', 'REAL'),
            ('change_amount', 'REAL'),
            ('cashier', 'TEXT'),
            ('payment_time', 'TIMESTAMP'),
            ('customer_count', 'INTEGER DEFAULT 1'),
            ('waiter_id', 'INTEGER')
        ]
        
        for col_name, col_type in missing_columns:
            if col_name not in order_columns:
                cursor.execute(f"ALTER TABLE orders ADD COLUMN {col_name} {col_type}")
        
        cursor.execute("PRAGMA table_info(menu_items)")
        menu_columns = [col[1] for col in cursor.fetchall()]
        
        menu_missing_columns = [
            ('order_count', 'INTEGER DEFAULT 0'),
            ('image_type', 'TEXT DEFAULT "emoji"'),
            ('image_size', 'INTEGER DEFAULT 0'),
            ('updated_at', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
        ]
        
        for col_name, col_type in menu_missing_columns:
            if col_name not in menu_columns:
                cursor.execute(f"ALTER TABLE menu_items ADD COLUMN {col_name} {col_type}")
        
        conn.commit()
        
    except Exception as e:
        pass
    finally:
        conn.close()

def enhance_database_for_images():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            UPDATE menu_items 
            SET image_type = CASE 
                WHEN image LIKE 'data:image%' THEN 'base64'
                ELSE 'emoji'
            END
        ''')
        
        cursor.execute('''
            UPDATE menu_items 
            SET image_size = LENGTH(image)
        ''')
        
        conn.commit()
        
    except Exception as e:
        pass
    finally:
        conn.close()

if __name__ == "__main__":
    init_db()
