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
    
    # Only create essential users (no waiters)
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
    
    # Create tables only
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
    print("✅ Database initialized successfully!")

def fix_missing_columns():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Fix users table
        cursor.execute("PRAGMA table_info(users)")
        user_columns = [col[1] for col in cursor.fetchall()]
        
        if 'is_active' not in user_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN is_active INTEGER DEFAULT 1")
            print("✅ Added is_active column to users table")
        
        # Fix orders table
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
                print(f"✅ Added missing column to orders: {col_name}")
        
        # Fix menu_items table
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
                print(f"✅ Added missing column to menu_items: {col_name}")
        
        conn.commit()
        print("✅ Fixed all missing columns")
        
    except Exception as e:
        print(f"⚠️ Error fixing columns: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

def enhance_database_for_images():
    """Enhance database to better handle images from phone cameras"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Update image_type for existing rows
        cursor.execute('''
            UPDATE menu_items 
            SET image_type = CASE 
                WHEN image LIKE 'data:image%' THEN 'base64'
                ELSE 'emoji'
            END
        ''')
        
        # Update image_size for existing rows
        cursor.execute('''
            UPDATE menu_items 
            SET image_size = LENGTH(image)
        ''')
        
        conn.commit()
        print("✅ Database enhanced for image handling")
        
    except Exception as e:
        print(f"⚠️ Error enhancing database: {e}")
    finally:
        conn.close()

def check_database():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    print("\n📊 DATABASE STATUS:")
    print("=" * 50)
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' OR type='view' ORDER BY name")
    tables = cursor.fetchall()
    print("📁 Tables in database:")
    for table in tables:
        print(f"  - {table[0]}")
    
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    print(f"\n👥 Total users: {total_users}")
    
    cursor.execute("SELECT role, COUNT(*) FROM users GROUP BY role ORDER BY role")
    print("👥 Users by role:")
    for role, count in cursor.fetchall():
        print(f"  - {role}: {count}")
    
    # Show waiters
    cursor.execute("SELECT id, username, full_name, is_active FROM users WHERE role='waiter' ORDER BY id")
    waiters = cursor.fetchall()
    print("\n👨‍🍳 Waiters:")
    if waiters:
        for waiter in waiters:
            status = "ACTIVE" if waiter['is_active'] == 1 else "INACTIVE"
            print(f"  - ID:{waiter['id']} | {waiter['username']} | {waiter['full_name']} | {status}")
    else:
        print("  No waiters in database")
    
    cursor.execute("SELECT COUNT(*) FROM orders")
    print(f"\n📋 Total orders: {cursor.fetchone()[0]}")
    
    cursor.execute("SELECT status, COUNT(*) FROM orders GROUP BY status")
    print("📋 Orders by status:")
    for status, count in cursor.fetchall():
        print(f"  - {status}: {count}")
    
    today = datetime.now().strftime('%Y-%m-%d')
    cursor.execute("SELECT COUNT(*), COALESCE(SUM(total), 0) FROM orders WHERE DATE(order_date) = ? AND status = 'completed'", (today,))
    order_count, total_sales = cursor.fetchone()
    print(f"\n💰 Today's COMPLETED orders: {order_count}")
    print(f"💰 Today's sales (completed only): ₱{total_sales:.2f}")
    
    cursor.execute("SELECT COUNT(*) FROM menu_items")
    total_dishes = cursor.fetchone()[0]
    print(f"\n🍽️  Total dishes: {total_dishes}")
    
    cursor.execute("SELECT COUNT(*) FROM menu_items WHERE image_type = 'base64'")
    base64_images = cursor.fetchone()[0]
    print(f"📸 Dishes with camera/base64 images: {base64_images}")
    
    cursor.execute("SELECT COUNT(*) FROM menu_items WHERE image_type = 'emoji'")
    emoji_images = cursor.fetchone()[0]
    print(f"🍽️  Dishes with emoji images: {emoji_images}")
    
    cursor.execute("SELECT name, order_count FROM menu_items WHERE order_count > 0 ORDER BY order_count DESC LIMIT 3")
    top_dishes = cursor.fetchall()
    print("🏆 Top selling dishes:")
    if top_dishes:
        for dish in top_dishes:
            print(f"  - {dish[0]}: {dish[1]} orders")
    else:
        print("  No orders yet")
    
    conn.close()
    print("=" * 50)

if __name__ == "__main__":
    init_db()
    check_database()