from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from datetime import datetime, timedelta, timezone
import json
import secrets
import base64
import io
from database import init_db, get_db_connection, fix_missing_columns
import traceback

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)
app.permanent_session_lifetime = timedelta(hours=2)

# Add customer_count column if it doesn't exist
def add_customer_count_column():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("PRAGMA table_info(orders)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'customer_count' not in columns:
            cursor.execute("ALTER TABLE orders ADD COLUMN customer_count INTEGER DEFAULT 1")
            conn.commit()
            print("✅ Added customer_count column to orders table")
    except Exception as e:
        print(f"Error adding column: {e}")
    finally:
        conn.close()

init_db()
add_customer_count_column()

PH_TIMEZONE = timezone(timedelta(hours=8))  # UTC+8 for Philippines

def row_to_dict(row):
    """Convert sqlite3.Row to dictionary"""
    if row is None:
        return None
    return dict(row)

def rows_to_dict_list(rows):
    """Convert list of sqlite3.Row to list of dictionaries"""
    return [dict(row) for row in rows]

def validate_image_data(image_data):
    """Validate and sanitize image data from phone camera or upload"""
    if not image_data or image_data == '':
        return '🍽️'  # Default emoji
    
    # If it's a base64 image from camera
    if image_data.startswith('data:image'):
        # INCREASED LIMIT for compressed images
        if len(image_data) > 5000000:  # 5MB limit
            print(f"⚠️ Image still too large after compression: {len(image_data)} bytes")
            return '🍽️'
        
        # Validate base64 format
        try:
            if ';base64,' in image_data:
                return image_data
            else:
                return '🍽️'
        except:
            return '🍽️'
    
    # If it's an emoji or text
    if len(image_data) > 100:
        return image_data[:100]
    
    return image_data


def get_philippine_time():
    """Get current Philippine time (UTC+8)"""
    return datetime.now(PH_TIMEZONE)

def format_datetime_for_db(dt):
    """Format datetime for SQLite storage"""
    return dt.strftime('%Y-%m-%d %H:%M:%S')

def parse_datetime_from_db(dt_str):
    """Parse datetime from SQLite to Python datetime with timezone"""
    if not dt_str:
        return None
    
    # Try different formats
    formats = [
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%d %H:%M:%S.%f',
        '%Y-%m-%dT%H:%M:%S',
        '%Y-%m-%dT%H:%M:%S.%fZ'
    ]
    
    for fmt in formats:
        try:
            dt = datetime.strptime(dt_str, fmt)
            # Assume it's in Philippine time if no timezone
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=PH_TIMEZONE)
            return dt
        except ValueError:
            continue
    
    # If all parsing fails, return current time
    print(f"⚠️ Could not parse datetime: {dt_str}")
    return get_philippine_time()

def calculate_duration_minutes(start_dt_str):
    """Calculate duration in minutes from start time to now"""
    if not start_dt_str:
        return 0
    
    try:
        start_dt = parse_datetime_from_db(start_dt_str)
        now = get_philippine_time()
        
        # Ensure both have timezone info
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=PH_TIMEZONE)
        
        duration = now - start_dt
        return int(duration.total_seconds() // 60)
    except Exception as e:
        print(f"⚠️ Error calculating duration: {e}")
        return 0

# ========== API ENDPOINTS ==========

@app.route('/')
def home():
    if 'logged_in' in session and session['logged_in']:
        role = session.get('role')
        if role == 'manager':
            return redirect(url_for('manager_dashboard'))
        elif role == 'chef':
            return redirect(url_for('chef_dashboard'))
        elif role == 'cashier':
            return redirect(url_for('cashier_dashboard'))
        elif role == 'waiter':
            return redirect(url_for('waiter_dashboard'))
    
    session.clear()
    return render_template('index.html')

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    role = data.get('role')
    
    if not username or not password or not role:
        return jsonify({"success": False, "message": "Please fill all fields!"})
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        'SELECT * FROM users WHERE username=? AND password=? AND role=? AND is_active=1',
        (username, password, role)
    )
    user = cursor.fetchone()
    conn.close()
    
    if user:
        user_dict = dict(user)
        session.permanent = True
        session['logged_in'] = True
        session['username'] = username
        session['role'] = role
        session['name'] = user_dict.get('full_name', 'User')
        session['user_id'] = user_dict['id']
        
        if role == 'manager':
            redirect_url = '/manager-dashboard'
        elif role == 'chef':
            redirect_url = '/chef-dashboard'
        elif role == 'cashier':
            redirect_url = '/cashier-dashboard'
        elif role == 'waiter':
            redirect_url = '/waiter-dashboard'
        else:
            redirect_url = '/'
        
        return jsonify({
            "success": True, 
            "message": f"Login successful as {role}!",
            "redirect": redirect_url,
            "name": user_dict.get('full_name', 'User')
        })
    
    return jsonify({"success": False, "message": "Invalid credentials or role mismatch!"})

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/manager-dashboard')
def manager_dashboard():
    if 'logged_in' not in session or session.get('role') != 'manager':
        return redirect(url_for('home'))
    return render_template('manager-dashboard.html', username=session.get('name'))

@app.route('/chef-dashboard')
def chef_dashboard():
    if 'logged_in' not in session or session.get('role') != 'chef':
        return redirect(url_for('home'))
    return render_template('chef-dashboard.html', username=session.get('name'))

@app.route('/cashier-dashboard')
def cashier_dashboard():
    if 'logged_in' not in session or session.get('role') != 'cashier':
        return redirect(url_for('home'))
    return render_template('cashier-dashboard.html', username=session.get('name'))

@app.route('/waiter-dashboard')
def waiter_dashboard():
    if 'logged_in' not in session or session.get('role') != 'waiter':
        return redirect(url_for('home'))
    return render_template('waiter-dashboard.html', username=session.get('name'))


@app.route('/api/time', methods=['GET'])
def get_server_time():
    """Get server time for client synchronization"""
    server_time = get_philippine_time()
    return jsonify({
        "timestamp": int(server_time.timestamp() * 1000),  # milliseconds
        "datetime": server_time.isoformat(),
        "formatted": server_time.strftime('%Y-%m-%d %H:%M:%S'),
        "timezone": "UTC+8"
    })

@app.route('/api/dishes', methods=['GET'])
def get_dishes():
    if 'logged_in' not in session:
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('SELECT * FROM menu_items ORDER BY category, name')
        rows = cursor.fetchall()
        
        dishes = rows_to_dict_list(rows)
        
        for dish in dishes:
            dish['available'] = dish['availability'] == 1 if 'availability' in dish else True
        
        return jsonify(dishes)
    except Exception as e:
        print(f"Error getting dishes: {e}")
        return jsonify([])
    finally:
        conn.close()

@app.route('/api/waiter/dishes', methods=['GET'])
def get_waiter_dishes():
    if 'logged_in' not in session or session.get('role') != 'waiter':
        return jsonify({"success": False, "message": "Waiters only!"}), 403
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('SELECT * FROM menu_items WHERE availability = 1 ORDER BY category, name')
        rows = cursor.fetchall()
        
        dishes = rows_to_dict_list(rows)
        
        for dish in dishes:
            dish['available'] = True
        
        return jsonify(dishes)
    except Exception as e:
        print(f"Error getting waiter dishes: {e}")
        return jsonify([])
    finally:
        conn.close()

@app.route('/api/dishes', methods=['POST'])
def add_dish():
    if 'logged_in' not in session or session.get('role') != 'manager':
        return jsonify({"success": False, "message": "Managers only!"}), 403
    
    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        available = data.get('available', True)
        availability = 1 if available else 0
        
        # Handle image properly
        image_data = data.get('image', '🍽️')
        validated_image = validate_image_data(image_data)
        
        cursor.execute('''
            INSERT INTO menu_items (name, price, description, image, category, availability)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            data['name'],
            float(data['price']),
            data.get('description', ''),
            validated_image,
            data['category'],
            availability
        ))
        
        conn.commit()
        dish_id = cursor.lastrowid
        
        cursor.execute('SELECT * FROM menu_items WHERE id = ?', (dish_id,))
        row = cursor.fetchone()
        new_dish = row_to_dict(row)
        new_dish['available'] = new_dish['availability'] == 1 if 'availability' in new_dish else True
        
        return jsonify({"success": True, "dish": new_dish})
    except Exception as e:
        print(f"Error adding dish: {e}")
        traceback.print_exc()
        return jsonify({"success": False, "message": f"Error adding dish: {str(e)}"}), 500
    finally:
        conn.close()

@app.route('/api/dishes/<int:dish_id>', methods=['PUT'])
def update_dish(dish_id):
    if 'logged_in' not in session or session.get('role') != 'manager':
        return jsonify({"success": False, "message": "Managers only!"}), 403
    
    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        available = data.get('available', True)
        availability = 1 if available else 0
        
        # Handle image properly
        image_data = data.get('image', '🍽️')
        validated_image = validate_image_data(image_data)
        
        cursor.execute('''
            UPDATE menu_items 
            SET name=?, price=?, description=?, image=?, category=?, availability=?, updated_at=CURRENT_TIMESTAMP
            WHERE id=?
        ''', (
            data.get('name'),
            float(data.get('price', 0)),
            data.get('description', ''),
            validated_image,
            data.get('category'),
            availability,
            dish_id
        ))
        
        if cursor.rowcount == 0:
            return jsonify({"success": False, "message": "Dish not found"}), 404
        
        conn.commit()
        
        cursor.execute('SELECT * FROM menu_items WHERE id = ?', (dish_id,))
        row = cursor.fetchone()
        updated_dish = row_to_dict(row)
        updated_dish['available'] = updated_dish['availability'] == 1 if 'availability' in updated_dish else True
        
        return jsonify({"success": True, "dish": updated_dish})
    except Exception as e:
        print(f"Error updating dish: {e}")
        traceback.print_exc()
        return jsonify({"success": False, "message": f"Error updating dish: {str(e)}"}), 500
    finally:
        conn.close()

@app.route('/api/dishes/<int:dish_id>', methods=['DELETE'])
def delete_dish(dish_id):
    if 'logged_in' not in session or session.get('role') != 'manager':
        return jsonify({"success": False, "message": "Managers only!"}), 403
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM menu_items WHERE id = ?', (dish_id,))
    conn.commit()
    conn.close()
    
    return jsonify({"success": True})


@app.route('/api/waiters', methods=['GET'])
def get_waiters():
    if 'logged_in' not in session:
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        if session.get('role') == 'manager':
            cursor.execute('''
                SELECT id, username, full_name as name, email, phone, 
                       is_active, created_at,
                       CASE 
                           WHEN is_active = 1 THEN 'active'
                           ELSE 'inactive'
                       END as status
                FROM users 
                WHERE role="waiter" 
                ORDER BY full_name
            ''')
        else:
            cursor.execute('''
                SELECT id, full_name as name, is_active FROM users 
                WHERE role="waiter" 
                ORDER BY full_name
            ''')
        
        waiters = []
        rows = cursor.fetchall()
        
        # Convert to proper format
        for row in rows:
            waiter = dict(row)
            # Ensure all required fields are present
            waiter['id'] = waiter['id']
            waiter['name'] = waiter.get('name', '')
            waiter['username'] = waiter.get('username', '')
            waiter['email'] = waiter.get('email', '')
            waiter['phone'] = waiter.get('phone', '')
            
            # Handle status properly
            if 'status' in waiter:
                waiter['status'] = waiter['status']
            elif 'is_active' in waiter:
                waiter['status'] = 'active' if waiter['is_active'] == 1 else 'inactive'
            
            waiters.append(waiter)
        
        conn.close()
        return jsonify(waiters)
        
    except Exception as e:
        print(f"Error getting waiters: {e}")
        traceback.print_exc()
        conn.close()
        return jsonify([])

@app.route('/api/waiters', methods=['POST'])
def add_waiter():
    if 'logged_in' not in session or session.get('role') != 'manager':
        return jsonify({"success": False, "message": "Managers only!"}), 403
    
    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Validate required fields
        required_fields = ['name', 'username', 'password']
        for field in required_fields:
            if not data.get(field):
                conn.close()
                return jsonify({"success": False, "message": f"{field} is required"}), 400
        
        # Check if username exists
        cursor.execute('SELECT id FROM users WHERE username = ?', (data['username'],))
        if cursor.fetchone():
            conn.close()
            return jsonify({"success": False, "message": "Username already exists"}), 400
        
        # Insert new waiter
        cursor.execute('''
            INSERT INTO users (username, password, role, full_name, email, phone, is_active)
            VALUES (?, ?, 'waiter', ?, ?, ?, ?)
        ''', (
            data['username'],
            data['password'],
            data['name'],
            data.get('email', ''),
            data.get('phone', ''),
            1  # Default to active
        ))
        
        conn.commit()
        waiter_id = cursor.lastrowid
        
        # Get the newly created waiter
        cursor.execute('''
            SELECT id, username, full_name as name, email, phone, 
                   'active' as status
            FROM users WHERE id = ?
        ''', (waiter_id,))
        
        row = cursor.fetchone()
        new_waiter = dict(row) if row else {}
        
        conn.close()
        return jsonify({
            "success": True, 
            "message": "Waiter added successfully",
            "waiter": new_waiter
        })
        
    except Exception as e:
        conn.rollback()
        conn.close()
        print(f"Error adding waiter: {e}")
        traceback.print_exc()
        return jsonify({"success": False, "message": f"Error adding waiter: {str(e)}"}), 500

@app.route('/api/waiters/<int:waiter_id>', methods=['PUT'])
def update_waiter(waiter_id):
    if 'logged_in' not in session or session.get('role') != 'manager':
        return jsonify({"success": False, "message": "Managers only!"}), 403
    
    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check if waiter exists
        cursor.execute("SELECT id FROM users WHERE id = ? AND role='waiter'", (waiter_id,))
        if not cursor.fetchone():
            conn.close()
            return jsonify({"success": False, "message": "Waiter not found"}), 404
        
        update_fields = []
        values = []
        
        if 'name' in data:
            update_fields.append("full_name = ?")
            values.append(data['name'])
        
        if 'username' in data:
            # Check if username already exists (excluding current waiter)
            cursor.execute("SELECT id FROM users WHERE username = ? AND id != ?", 
                         (data['username'], waiter_id))
            if cursor.fetchone():
                conn.close()
                return jsonify({"success": False, "message": "Username already exists"}), 400
            
            update_fields.append("username = ?")
            values.append(data['username'])
        
        if 'password' in data and data['password'].strip():
            update_fields.append("password = ?")
            values.append(data['password'].strip())
        
        if 'email' in data:
            update_fields.append("email = ?")
            values.append(data['email'])
        
        if 'phone' in data:
            update_fields.append("phone = ?")
            values.append(data['phone'])
        
        if 'status' in data:
            is_active = 1 if data['status'] == 'active' else 0
            update_fields.append("is_active = ?")
            values.append(is_active)
        
        if update_fields:
            query = f"UPDATE users SET {', '.join(update_fields)} WHERE id = ? AND role='waiter'"
            values.append(waiter_id)
            cursor.execute(query, values)
            conn.commit()
            
            # Get updated waiter
            cursor.execute('''
                SELECT id, username, full_name as name, email, phone, 
                       CASE 
                           WHEN is_active = 1 THEN 'active'
                           ELSE 'inactive'
                       END as status
                FROM users WHERE id = ?
            ''', (waiter_id,))
            
            row = cursor.fetchone()
            if row:
                updated_waiter = dict(row)
                conn.close()
                return jsonify({
                    "success": True, 
                    "message": "Waiter updated successfully",
                    "waiter": updated_waiter
                })
        
        conn.close()
        return jsonify({"success": True, "message": "Waiter updated"})
        
    except Exception as e:
        conn.rollback()
        conn.close()
        print(f"Error updating waiter: {e}")
        traceback.print_exc()
        return jsonify({"success": False, "message": f"Error updating waiter: {str(e)}"}), 500

@app.route('/api/waiters/<int:waiter_id>', methods=['DELETE'])
def delete_waiter(waiter_id):
    if 'logged_in' not in session or session.get('role') != 'manager':
        return jsonify({"success": False, "message": "Managers only!"}), 403
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check if waiter exists
        cursor.execute("SELECT id FROM users WHERE id = ? AND role='waiter'", (waiter_id,))
        if not cursor.fetchone():
            conn.close()
            return jsonify({"success": False, "message": "Waiter not found"}), 404
        
        # Check if waiter has active orders
        cursor.execute("SELECT COUNT(*) FROM orders WHERE waiter_id = ? AND status != 'completed'", (waiter_id,))
        active_orders = cursor.fetchone()[0]
        
        if active_orders > 0:
            conn.close()
            return jsonify({
                "success": False, 
                "message": f"Cannot delete waiter with {active_orders} active orders"
            }), 400
        
        # Delete waiter
        cursor.execute("DELETE FROM users WHERE id = ? AND role='waiter'", (waiter_id,))
        conn.commit()
        
        conn.close()
        return jsonify({
            "success": True, 
            "message": "Waiter deleted successfully"
        })
        
    except Exception as e:
        conn.rollback()
        conn.close()
        print(f"Error deleting waiter: {e}")
        return jsonify({"success": False, "message": f"Error deleting waiter: {str(e)}"}), 500

# ========== DEBUG ENDPOINT ==========

@app.route('/api/debug/waiters', methods=['GET'])
def debug_waiters():
    """Debug endpoint to see waiter data structure"""
    if 'logged_in' not in session:
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, username, full_name, email, phone, is_active, 
               role, created_at
        FROM users 
        WHERE role="waiter" 
        ORDER BY id
    ''')
    
    waiters = []
    for row in cursor.fetchall():
        waiter = dict(row)
        waiters.append({
            "id": waiter['id'],
            "username": waiter['username'],
            "name": waiter['full_name'],
            "email": waiter['email'],
            "phone": waiter['phone'],
            "is_active": waiter['is_active'],
            "status": "active" if waiter['is_active'] == 1 else "inactive",
            "role": waiter['role'],
            "created_at": waiter['created_at']
        })
    
    conn.close()
    
    return jsonify({
        "success": True,
        "total_waiters": len(waiters),
        "waiters": waiters,
        "debug_info": {
            "field_names": ["id", "username", "name", "email", "phone", "status", "is_active"],
            "sample_waiter": waiters[0] if waiters else {}
        }
    })


@app.route('/api/tables', methods=['GET'])
def get_tables():
    if 'logged_in' not in session:
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT t.*, u.full_name as waiter_name, o.status as order_status,
                   o.order_date as last_order_time
            FROM restaurant_tables t
            LEFT JOIN users u ON t.current_waiter_id = u.id
            LEFT JOIN orders o ON t.current_order_id = o.id
            ORDER BY t.table_number
        ''')
        
        tables = []
        for row in cursor.fetchall():
            table = row_to_dict(row)
            
            if table['status'] == 'occupied' and table.get('occupied_since'):
                table['duration_minutes'] = calculate_duration_minutes(table['occupied_since'])
            else:
                table['duration_minutes'] = 0
            
            tables.append(table)
        
        conn.close()
        return jsonify(tables)
    except Exception as e:
        print(f"Error getting tables: {e}")
        traceback.print_exc()
        return jsonify([])

@app.route('/api/tables/<int:table_number>/status', methods=['PUT'])
def update_table_status(table_number):
    if 'logged_in' not in session:
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    
    data = request.json
    status = data.get('status')
    waiter_id = session.get('user_id')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        current_time = get_philippine_time()
        formatted_time = format_datetime_for_db(current_time)
        
        if status == 'occupied':
            cursor.execute('''
                UPDATE restaurant_tables 
                SET status = ?, 
                    current_waiter_id = ?, 
                    occupied_since = ?
                WHERE table_number = ?
            ''', (status, waiter_id, formatted_time, table_number))
        else:
            cursor.execute('''
                UPDATE restaurant_tables 
                SET status = ?, 
                    current_waiter_id = NULL, 
                    occupied_since = NULL, 
                    current_order_id = NULL
                WHERE table_number = ?
            ''', (status, table_number))
        
        conn.commit()
        
        # Return updated table with duration
        cursor.execute('SELECT * FROM restaurant_tables WHERE table_number = ?', (table_number,))
        row = cursor.fetchone()
        table = row_to_dict(row) if row else {}
        
        if table and table['status'] == 'occupied' and table.get('occupied_since'):
            table['duration_minutes'] = calculate_duration_minutes(table['occupied_since'])
        
        conn.close()
        return jsonify({"success": True, "table": table})
    except Exception as e:
        conn.rollback()
        conn.close()
        print(f"Error updating table status: {e}")
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/orders', methods=['GET'])
def get_orders():
    if 'logged_in' not in session:
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    user_role = session.get('role')
    
    if user_role == 'chef':
        cursor.execute('SELECT * FROM orders WHERE status IN ("pending", "preparing", "served") ORDER BY order_date DESC')
    elif user_role == 'cashier':
        cursor.execute('SELECT * FROM orders WHERE bill_requested = 1 AND status != "completed" ORDER BY order_date DESC')
    elif user_role == 'waiter':
        waiter_name = session.get('name')
        cursor.execute('SELECT * FROM orders WHERE waiter_name = ? ORDER BY order_date DESC', (waiter_name,))
    else:
        cursor.execute('SELECT * FROM orders ORDER BY order_date DESC')
    
    orders = []
    for row in cursor.fetchall():
        order = row_to_dict(row)
        try:
            order['items'] = json.loads(order['items'])
        except:
            order['items'] = []
        
        if 'waiter' not in order and 'waiter_name' in order:
            order['waiter'] = order['waiter_name']
        elif 'waiter_name' not in order and 'waiter' in order:
            order['waiter_name'] = order['waiter']
        
        if 'table' not in order and 'table_number' in order:
            order['table'] = order['table_number']
        elif 'table_number' not in order and 'table' in order:
            order['table_number'] = order['table']
        
        orders.append(order)
    
    conn.close()
    return jsonify(orders)

@app.route('/api/orders/<int:order_id>', methods=['GET'])
def get_single_order(order_id):
    if 'logged_in' not in session:
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('SELECT * FROM orders WHERE id = ?', (order_id,))
        row = cursor.fetchone()
        
        if not row:
            return jsonify({"success": False, "message": "Order not found"}), 404
        
        order = row_to_dict(row)
        
        try:
            order['items'] = json.loads(order['items']) if order.get('items') else []
        except:
            order['items'] = []
        
        if 'table' not in order and 'table_number' in order:
            order['table'] = order['table_number']
        
        if 'waiter' not in order and 'waiter_name' in order:
            order['waiter'] = order['waiter_name']
        
        conn.close()
        return jsonify({"success": True, "order": order})
        
    except Exception as e:
        conn.close()
        print(f"Error getting order: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/orders', methods=['POST'])
def create_order():
    if 'logged_in' not in session:
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    
    user_role = session.get('role')
    if user_role not in ['waiter', 'manager']:
        return jsonify({"success": False, "message": "Waiters or Managers only"}), 403
    
    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        items_json = json.dumps(data['items'])
        waiter_name = session.get('name', 'Unknown Waiter')
        waiter_id = session.get('user_id')
        
        cursor.execute("SELECT MAX(id) FROM orders")
        max_id = cursor.fetchone()[0] or 0
        order_number = f"ORD-{(max_id + 1):05d}"
        
        special_requests = data.get('specialRequests', '')
        customer_count = data.get('customer_count', 1)
        
        current_time = get_philippine_time()
        formatted_time = format_datetime_for_db(current_time)
        
        cursor.execute('''
            INSERT INTO orders (order_number, table_number, waiter_name, waiter_id, items, total, 
                               status, order_date, special_requests, customer_count, bill_requested)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
        ''', (
            order_number,
            data['table'],
            waiter_name,
            waiter_id,
            items_json,
            float(data['total']),
            'pending',
            formatted_time,
            special_requests,
            customer_count
        ))
        
        order_id = cursor.lastrowid
        
        cursor.execute('''
            UPDATE restaurant_tables 
            SET status = 'occupied', 
                current_waiter_id = ?,
                current_order_id = ?,
                occupied_since = ?
            WHERE table_number = ?
        ''', (waiter_id, order_id, formatted_time, data['table']))
        
        conn.commit()
        
        cursor.execute('SELECT * FROM orders WHERE id = ?', (order_id,))
        row = cursor.fetchone()
        
        order = row_to_dict(row) if row else {}
        if order:
            try:
                order['items'] = json.loads(order['items'])
            except:
                order['items'] = []
        
        if 'waiter_name' not in order:
            order['waiter_name'] = waiter_name
        
        conn.close()
        return jsonify({"success": True, "order": order})
        
    except Exception as e:
        conn.rollback()
        conn.close()
        print(f"Error creating order: {e}")
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/orders/<int:order_id>/status', methods=['PUT'])
def update_order_status(order_id):
    if 'logged_in' not in session:
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    
    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get current order first
        cursor.execute('SELECT * FROM orders WHERE id = ?', (order_id,))
        current_order = cursor.fetchone()
        current_order_dict = row_to_dict(current_order) if current_order else {}
        
        update_fields = ["status = ?"]
        values = [data['status']]
        
        # Only when waiter explicitly requests bill
        if 'bill_requested' in data:
            update_fields.append("bill_requested = ?")
            values.append(data['bill_requested'])
        elif data.get('status') == 'served':
            # When chef marks as served, PRESERVE current bill_requested value
            # Default is 0 (not requested)
            current_bill_requested = current_order_dict.get('bill_requested', 0)
            if current_bill_requested != 1:
                update_fields.append("bill_requested = 0")
        
        if 'cashier_notes' in data:
            update_fields.append("cashier_notes = ?")
            values.append(data['cashier_notes'])
        
        values.append(order_id)
        
        query = f"UPDATE orders SET {', '.join(update_fields)} WHERE id = ?"
        cursor.execute(query, values)
        
        # Only clear table if status is 'completed' (after payment)
        if data.get('status') == 'completed':
            cursor.execute('''
                UPDATE restaurant_tables 
                SET status = 'available', 
                    current_waiter_id = NULL, 
                    current_order_id = NULL,
                    occupied_since = NULL
                WHERE current_order_id = ?
            ''', (order_id,))
        
        conn.commit()
        
        cursor.execute('SELECT * FROM orders WHERE id = ?', (order_id,))
        row = cursor.fetchone()
        order = row_to_dict(row) if row else None
        if order and 'items' in order:
            try:
                order['items'] = json.loads(order['items'])
            except:
                order['items'] = []
        
        conn.close()
        return jsonify({"success": True, "order": order})
    except Exception as e:
        conn.rollback()
        conn.close()
        print(f"Error updating order status: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/tables/<int:table_number>/orders', methods=['GET'])
def get_table_orders(table_number):
    if 'logged_in' not in session:
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM orders 
        WHERE table_number = ? 
        AND status IN ('pending', 'preparing', 'served')
        ORDER BY order_date DESC
    ''', (table_number,))
    
    orders = []
    for row in cursor.fetchall():
        order = row_to_dict(row)
        try:
            order['items'] = json.loads(order['items'])
        except:
            order['items'] = []
        orders.append(order)
    
    conn.close()
    
    if orders:
        return jsonify({"success": True, "orders": orders})
    else:
        return jsonify({"success": False, "message": "No active orders for this table"})

@app.route('/api/stats', methods=['GET'])
def get_stats():
    if 'logged_in' not in session or session.get('role') != 'manager':
        return jsonify({"success": False, "message": "Managers only!"}), 403
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    fix_missing_columns()
    
    today = datetime.now(PH_TIMEZONE).strftime('%Y-%m-%d')
    
    cursor.execute('''
        SELECT COUNT(*) as count, COALESCE(SUM(total), 0) as sales 
        FROM orders 
        WHERE DATE(order_date) = ? AND status = 'completed'
    ''', (today,))
    today_stats = row_to_dict(cursor.fetchone())
    
    cursor.execute("SELECT COUNT(*) FROM users WHERE role='waiter' AND is_active=1")
    active_waiters = cursor.fetchone()[0]
    
    today_sales = today_stats['sales'] or 0 if today_stats else 0
    total_orders = today_stats['count'] or 0 if today_stats else 0
    average_bill = today_sales / total_orders if total_orders > 0 else 0
    
    conn.close()
    
    return jsonify({
        "today_sales": today_sales,
        "total_orders": total_orders,
        "active_waiters": active_waiters,
        "average_bill": average_bill
    })

@app.route('/api/top-dishes', methods=['GET'])
def get_top_dishes():
    if 'logged_in' not in session or session.get('role') != 'manager':
        return jsonify({"success": False, "message": "Managers only!"}), 403
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT id, name, category, price, image, 
                   COALESCE(order_count, 0) as orders
            FROM menu_items 
            WHERE COALESCE(order_count, 0) > 0
            ORDER BY COALESCE(order_count, 0) DESC
            LIMIT 10
        """)
        
        top_dishes = []
        rows = cursor.fetchall()
        
        if rows:
            for row in rows:
                dish = dict(row)
                dish['orders'] = int(dish.get('orders', 0))
                dish['revenue'] = dish['orders'] * dish.get('price', 0)
                top_dishes.append(dish)
        
        if len(top_dishes) == 0:
            cursor.execute("""
                SELECT id, name, category, price, image
                FROM menu_items
                WHERE availability = 1
                LIMIT 5
            """)
            for row in cursor.fetchall():
                dish = dict(row)
                dish['orders'] = 0
                dish['revenue'] = 0
                top_dishes.append(dish)
        
        conn.close()
        return jsonify(top_dishes)
        
    except Exception as e:
        print(f"Error getting top dishes: {e}")
        traceback.print_exc()
        conn.close()
        return jsonify([])

@app.route('/api/sales-data', methods=['GET'])
def get_sales_data():
    if 'logged_in' not in session or session.get('role') != 'manager':
        return jsonify({"success": False, "message": "Managers only!"}), 403
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        period = request.args.get('period', 'today')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        today = datetime.now(PH_TIMEZONE).date()
        
        date_condition = ""
        query_params = []
        
        if period == 'today':
            date_condition = "DATE(order_date) = ?"
            query_params.append(today.strftime('%Y-%m-%d'))
        elif period == 'week':
            week_ago = today - timedelta(days=7)
            date_condition = "DATE(order_date) BETWEEN ? AND ?"
            query_params.append(week_ago.strftime('%Y-%m-%d'))
            query_params.append(today.strftime('%Y-%m-%d'))
        elif period == 'month':
            month_ago = today - timedelta(days=30)
            date_condition = "DATE(order_date) BETWEEN ? AND ?"
            query_params.append(month_ago.strftime('%Y-%m-%d'))
            query_params.append(today.strftime('%Y-%m-%d'))
        elif period == 'custom' and start_date and end_date:
            date_condition = "DATE(order_date) BETWEEN ? AND ?"
            query_params.append(start_date)
            query_params.append(end_date)
        else:
            date_condition = "DATE(order_date) = ?"
            query_params.append(today.strftime('%Y-%m-%d'))
        
        query = f"""
            SELECT * FROM orders 
            WHERE status = 'completed' 
            AND {date_condition}
            ORDER BY order_date DESC
        """
        
        cursor.execute(query, query_params)
        completed_orders = rows_to_dict_list(cursor.fetchall())
        
        total_revenue = 0
        total_orders = len(completed_orders)
        
        for order in completed_orders:
            total_revenue += order.get('total', 0)
        
        avg_order = total_revenue / total_orders if total_orders > 0 else 0
        
        category_data = {}
        
        for order in completed_orders:
            try:
                items_json = order.get('items', '[]')
                
                items = []
                if items_json:
                    try:
                        items = json.loads(items_json)
                    except:
                        items = []
                
                for item in items:
                    if isinstance(item, dict):
                        dish_name = item.get('dish') or item.get('name') or ''
                        qty = int(item.get('qty', 1))
                        price = float(item.get('price', 0))
                        
                        if dish_name:
                            cursor.execute("SELECT category FROM menu_items WHERE name = ?", (dish_name,))
                            dish_row = cursor.fetchone()
                            
                            if dish_row:
                                dish_dict = row_to_dict(dish_row)
                                category = dish_dict.get('category') if dish_dict else ''
                                
                                if category:
                                    revenue = price * qty
                                    
                                    if category not in category_data:
                                        category_data[category] = {
                                            'orders': 0,
                                            'revenue': 0,
                                            'item_count': 0
                                        }
                                    
                                    category_data[category]['orders'] += 1
                                    category_data[category]['revenue'] += revenue
                                    category_data[category]['item_count'] += qty
            except Exception as e:
                continue
        
        sales_by_category = []
        for category, data in category_data.items():
            sales_by_category.append({
                'category': category,
                'orders': data['orders'],
                'revenue': data['revenue'],
                'item_count': data['item_count']
            })
        
        conn.close()
        
        return jsonify({
            "success": True,
            "total_revenue": total_revenue,
            "total_orders": total_orders,
            "average_order": avg_order,
            "sales_by_category": sales_by_category
        })
        
    except Exception as e:
        print(f"Error getting sales data: {e}")
        traceback.print_exc()
        if conn:
            conn.close()
        return jsonify({
            "success": False, 
            "message": str(e),
            "total_revenue": 0,
            "total_orders": 0,
            "average_order": 0,
            "sales_by_category": []
        }), 500

# ========== CRITICAL FIX: CASHIER PENDING BILLS ==========

@app.route('/api/cashier/pending-bills', methods=['GET'])
def get_pending_bills():
    if 'logged_in' not in session or session.get('role') != 'cashier':
        return jsonify({"success": False, "message": "Cashiers only!"}), 403
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # NOT all 'served' orders
        cursor.execute('''
            SELECT * FROM orders 
            WHERE bill_requested = 1 
            AND status != 'completed'
            ORDER BY order_date DESC
        ''')
        
        pending_bills = []
        for row in cursor.fetchall():
            order = row_to_dict(row)
            try:
                order['items'] = json.loads(order['items']) if order.get('items') else []
            except:
                order['items'] = []
            
            if 'table' not in order and 'table_number' in order:
                order['table'] = order['table_number']
            
            if 'totalAmount' not in order and 'total' in order:
                order['totalAmount'] = order['total']
            
            if 'tableNumber' not in order and 'table_number' in order:
                order['tableNumber'] = order['table_number']
            
            pending_bills.append(order)
        
        conn.close()
        return jsonify(pending_bills)
    except Exception as e:
        conn.close()
        print(f"Error getting pending bills: {e}")
        return jsonify([])

@app.route('/api/cashier/order-details/<int:order_id>', methods=['GET'])
def get_order_details(order_id):
    if 'logged_in' not in session or session.get('role') != 'cashier':
        return jsonify({"success": False, "message": "Cashiers only!"}), 403
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('SELECT * FROM orders WHERE id = ?', (order_id,))
        row = cursor.fetchone()
        
        if not row:
            return jsonify({"success": False, "message": "Order not found"}), 404
        
        order = row_to_dict(row)
        
        try:
            items = json.loads(order['items']) if order.get('items') else []
        except:
            items = []
        
        subtotal = 0
        for item in items:
            price = float(item.get('price', 0))
            qty = int(item.get('qty', 1))
            subtotal += price * qty
        
        tax = subtotal * 0.12
        discount = float(order.get('discount', 0))
        final_total = subtotal + tax - discount
        
        response = {
            "success": True,
            "data": {
                "id": order['id'],
                "tableNumber": order['table_number'],
                "table_number": order['table_number'],
                "table": order['table_number'],
                "waiter_name": order.get('waiter_name', 'Unknown'),
                "totalAmount": float(order.get('total', 0)),
                "total": float(order.get('total', 0)),
                "subtotal": subtotal,
                "sub_total": subtotal,
                "tax": tax,
                "vat": tax,
                "discount": discount,
                "discount_amount": discount,
                "finalTotal": final_total,
                "grand_total": final_total,
                "items": items,
                "order_items": items,
                "orderDate": order.get('order_date'),
                "created_at": order.get('order_date'),
                "timestamp": order.get('order_date'),
                "bill_requested": order.get('bill_requested', 0)
            }
        }
        
        conn.close()
        return jsonify(response)
        
    except Exception as e:
        conn.close()
        print(f"Error getting order details: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/cashier/process-payment/<int:order_id>', methods=['POST'])
def process_payment(order_id):
    if 'logged_in' not in session or session.get('role') != 'cashier':
        return jsonify({"success": False, "message": "Cashiers only!"}), 403
    
    data = request.json
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        final_total = data.get('final_total', 0)
        subtotal = final_total / 1.12
        tax = subtotal * 0.12
        
        cursor.execute('''
            UPDATE orders 
            SET status = 'completed', 
                payment_method = ?, 
                paid_amount = ?, 
                change_amount = ?,
                cashier = ?,
                payment_time = CURRENT_TIMESTAMP,
                bill_requested = 0,
                subtotal = ?,
                tax = ?,
                discount = ?
            WHERE id = ?
        ''', (
            data.get('payment_method', 'cash'),
            data.get('paid_amount'),
            data.get('change', 0),
            session.get('name'),
            subtotal,
            tax,
            data.get('final_total', 0) - (subtotal + tax),
            order_id
        ))
        
        cursor.execute('SELECT items FROM orders WHERE id = ?', (order_id,))
        order_row = cursor.fetchone()
        
        if order_row:
            order = dict(order_row)
            items_json = order.get('items', '[]')
            
            try:
                items = json.loads(items_json)
                for item in items:
                    if isinstance(item, dict):
                        dish_name = item.get('dish') or item.get('name') or ''
                        qty = item.get('qty', 1)
                        
                        if dish_name:
                            cursor.execute('''
                                UPDATE menu_items 
                                SET order_count = COALESCE(order_count, 0) + ?
                                WHERE name = ?
                            ''', (qty, dish_name))
            except Exception as e:
                pass
        
        cursor.execute('''
            UPDATE restaurant_tables 
            SET status = 'available', 
                current_waiter_id = NULL, 
                current_order_id = NULL,
                occupied_since = NULL
            WHERE current_order_id = ?
        ''', (order_id,))
        
        conn.commit()
        
        return jsonify({
            "success": True, 
            "message": "Payment processed successfully",
            "order_id": order_id
        })
        
    except Exception as e:
        conn.rollback()
        print(f"Error processing payment: {e}")
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        conn.close()

@app.route('/api/cashier/receipt/<int:order_id>', methods=['GET'])
def get_receipt(order_id):
    if 'logged_in' not in session or session.get('role') != 'cashier':
        return jsonify({"success": False, "message": "Cashiers only!"}), 403
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('SELECT * FROM orders WHERE id = ?', (order_id,))
        row = cursor.fetchone()
        
        if not row:
            return jsonify({"success": False, "message": "Order not found"}), 404
        
        order = row_to_dict(row)
        
        try:
            items = json.loads(order['items']) if order.get('items') else []
        except:
            items = []
        
        receipt_html = generate_receipt_html(order, items)
        
        conn.close()
        return jsonify({"success": True, "html": receipt_html})
        
    except Exception as e:
        conn.close()
        print(f"Error generating receipt: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

def generate_receipt_html(order, items):
    subtotal = float(order.get('subtotal', 0)) or sum(item.get('price', 0) * item.get('qty', 1) for item in items)
    tax = float(order.get('tax', 0)) or subtotal * 0.12
    discount = float(order.get('discount', 0))
    total = float(order.get('total', 0)) or subtotal + tax - discount
    payment_method = order.get('payment_method', 'cash')
    paid_amount = float(order.get('paid_amount', 0))
    change_amount = float(order.get('change_amount', 0))
    
    current_time = get_philippine_time()
    
    html = f"""
    <div class="receipt-header">
        <div class="receipt-title">🍽️ RESTAURANT PRO</div>
        <div>123 Main Street, City</div>
        <div>Tel: (123) 456-7890</div>
        <div>VAT Reg TIN: 000-000-000-000</div>
        <div style="margin-top: 10px; font-size: 12px;">SERIAL: {str(order.get('id', '')).zfill(6)}</div>
    </div>
    
    <div style="margin: 15px 0;">
        <div><strong>Table {order.get('table_number', 'N/A')}</strong></div>
        <div>Date: {current_time.strftime('%Y-%m-%d')}</div>
        <div>Time: {current_time.strftime('%H:%M:%S')}</div>
        <div>Cashier: {order.get('cashier', session.get('name', 'Cashier'))}</div>
        <div>Order ID: #{order.get('id', 'N/A')}</div>
    </div>
    
    <div style="border-top: 2px dashed #333; padding-top: 10px; margin-bottom: 10px;">
        <div style="display: flex; justify-content: space-between; font-weight: bold; padding-bottom: 5px;">
            <span>ITEM</span>
            <span>AMOUNT</span>
        </div>
        {"".join(f'''
        <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
            <span>{item.get("qty", 1)}x {item.get("name", item.get("dish", "Item"))}</span>
            <span>{(item.get("price", 0) * item.get("qty", 1)):.2f}</span>
        </div>
        ''' for item in items)}
    </div>
    
    <div style="margin-top: 15px;">
        <div style="display: flex; justify-content: space-between; margin-bottom: 3px;">
            <span>Subtotal:</span>
            <span>{subtotal:.2f}</span>
        </div>
        <div style="display: flex; justify-content: space-between; margin-bottom: 3px;">
            <span>Tax (12%):</span>
            <span>{tax:.2f}</span>
        </div>
        <div style="display: flex; justify-content: space-between; margin-bottom: 3px;">
            <span>Discount:</span>
            <span>-{discount:.2f}</span>
        </div>
        <div style="display: flex; justify-content: space-between; font-weight: bold; border-top: 2px solid #333; padding-top: 10px; margin-top: 10px; font-size: 18px;">
            <span>TOTAL:</span>
            <span>₱{total:.2f}</span>
        </div>
    </div>
    
    <div style="text-align: center; margin-top: 20px; border-top: 2px dashed #333; padding-top: 15px; font-size: 12px;">
        <div>Payment Method: {payment_method.upper()}</div>
        {f'<div>Amount Paid: ₱{paid_amount:.2f}</div>' if paid_amount > 0 else ''}
        {f'<div>Change: ₱{change_amount:.2f}</div>' if change_amount > 0 else ''}
        <div style="margin-top: 15px;">*** OFFICIAL RECEIPT ***</div>
        <div style="margin-top: 10px;">Thank you for dining with us!</div>
        <div style="margin-top: 5px; font-size: 10px; color: #666;">
            {current_time.strftime('%Y-%m-%d %H:%M:%S')}
        </div>
    </div>
    """
    
    return html

if __name__ == '__main__':
    print("=" * 60)
    print("🌐 Server: http://localhost:5000")
    print("=" * 60)
    print("👥 Available Login:")
    print("  👔 Manager:    manager / admin123")
    print("  👨‍🍳 Chef:       chef / chef123")
    print("  💰 Cashier:    cashier / cashier123")
    print("=" * 60)
    print("🕒 Server Timezone: UTC+8 (Philippine Time)")
    print("=" * 60)
    app.run(debug=True, port=5000, host='0.0.0.0')
