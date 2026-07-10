from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
import requests
import json
import os

app = Flask(__name__)
CORS(app)

# Render Environment Variable (DATABASE_URL)
DB_URL = os.environ.get("DATABASE_URL")

# Render Database URL format fix (psycopg2 compatible)
if DB_URL and DB_URL.startswith("postgres://"):
    DB_URL = DB_URL.replace("postgres://", "postgresql://", 1)

# Centralized DB Connection Helper
def get_db_connection():
    if DB_URL:
        return psycopg2.connect(DB_URL)
    else:
        # Fallback Local DB
        return psycopg2.connect(
            host="127.0.0.1",
            database="vlgsWorkspace_DB",
            user="postgres",
            password="vlgs24"
        )

# -------------------------------------------------------------
# Database Initializer (Tables & Auto-Healing Columns)
# -------------------------------------------------------------
def init_db():
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # 1. Admins Table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                id SERIAL PRIMARY KEY,
                username VARCHAR(100) UNIQUE NOT NULL,
                password VARCHAR(100) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 2. Employees Table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS employees (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                password VARCHAR(100),
                team VARCHAR(50),
                dob DATE,
                joining_date DATE,
                profile_pic TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        cur.execute("ALTER TABLE employees ADD COLUMN IF NOT EXISTS password VARCHAR(100);")
        cur.execute("ALTER TABLE employees ADD COLUMN IF NOT EXISTS team VARCHAR(50);")
        cur.execute("ALTER TABLE employees ADD COLUMN IF NOT EXISTS dob DATE;")
        cur.execute("ALTER TABLE employees ADD COLUMN IF NOT EXISTS joining_date DATE;")
        cur.execute("ALTER TABLE employees ADD COLUMN IF NOT EXISTS profile_pic TEXT;")

        # 3. Tasks Table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id SERIAL PRIMARY KEY,
                title VARCHAR(200) NOT NULL,
                description TEXT,
                assigned_to INT REFERENCES employees(id) ON DELETE CASCADE,
                deadline TIMESTAMP,
                status VARCHAR(50) DEFAULT 'Pending',
                is_rescheduled BOOLEAN DEFAULT FALSE,
                completed_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        # CRITICAL AUTO-REPAIR: Ensures tasks table matches production columns
        cur.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS is_rescheduled BOOLEAN DEFAULT FALSE;")
        cur.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS completed_at TIMESTAMP;")

        # 4. Reschedule Requests / History Table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS reschedule_requests (
                id SERIAL PRIMARY KEY,
                task_id INT REFERENCES tasks(id) ON DELETE CASCADE,
                employee_id INT REFERENCES employees(id) ON DELETE CASCADE,
                proposed_deadline TIMESTAMP,
                reason TEXT,
                status VARCHAR(50) DEFAULT 'Approved',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        # CRITICAL AUTO-REPAIR: Ensures reschedule_requests has old_deadline column
        cur.execute("ALTER TABLE reschedule_requests ADD COLUMN IF NOT EXISTS old_deadline TIMESTAMP;")

        # 5. Notifications Table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id SERIAL PRIMARY KEY,
                employee_id INT,
                title VARCHAR(200),
                message TEXT,
                type VARCHAR(50),
                is_read BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 6. Employee Sessions Table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS employee_sessions (
                id SERIAL PRIMARY KEY,
                employee_id INT REFERENCES employees(id) ON DELETE CASCADE,
                login_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                logout_time TIMESTAMP,
                ip_address VARCHAR(50)
            );
        """)

        # Default Admin User Insert
        cur.execute("""
            INSERT INTO admins (username, password)
            VALUES ('admin', 'admin123')
            ON CONFLICT (username) DO NOTHING;
        """)

        conn.commit()
        cur.close()
        conn.close()
        print("✅ DB Schema Initialized & Auto-Healed Successfully!")
    except Exception as e:
        print("❌ DB Init Error:", e)

with app.app_context():
    init_db()

# -------------------------------------------------------------
# Web Page Navigation Routes
# -------------------------------------------------------------
@app.route("/")
def login_page():
    return render_template("login.html")

@app.route("/user")
def user_page():
    return render_template("user.html")

@app.route("/admin")
def admin_page():
    return render_template("admin.html")

@app.route("/add_employee", methods=["GET"])
def add_employee_page():
    return render_template("add_employee.html")

@app.route("/add-task")
def add_task_page():
    return render_template("add_task.html")

@app.route("/task-records")
def task_records_page():
    return render_template("task_records.html")

@app.route("/admin_notify")
def admin_notification():
    return render_template("admin_notification.html")

@app.route("/admin_logs")
def admin_logs_page():
    return render_template("admin_logs.html")

@app.route("/user_profile")
def user_profile_page():
    return render_template("user_profile.html")

@app.route("/user_task")
def user_task_page():
    return render_template("user_task.html")

@app.route("/user_alerts")
def user_alert_page():
    return render_template("user_alert.html")

@app.route('/rescheduled_tasks_page')
def rescheduled_tasks_page():
    return render_template('rescheduled_tasks.html')

@app.route("/user_personal_tasks")
def user_personal_tasks():
    """Renders Employee Personal Task Management Screen"""
    return render_template("user_personal_tasks.html")

@app.route("/admin_personal_tasks")
def admin_personal_tasks():
    return render_template("admin_personal_tasks.html")
# -------------------------------------------------------------
# 🛠️ DYNAMIC SERVICE WORKER ENGINE (Foolproof Notification Delivery)
# -------------------------------------------------------------
@app.route('/OneSignalSDKWorker.js')
def onesignal_worker():
    """Dynamically serves the Service Worker script directly with correct mime type."""
    response = app.response_class(
        response='importScripts("https://cdn.onesignal.com/sdks/web/v16/OneSignalSDK.sw.js");',
        status=200,
        mimetype='application/javascript'
    )
    return response
# -------------------------------------------------------------
# Employee Edit & Delete Routes
# -------------------------------------------------------------
# -------------------------------------------------------------
# Employee Edit, Update & Delete Routes
# -------------------------------------------------------------
@app.route("/edit_employee_page")
def edit_employee_page():
    """Renders the Employee Management / Edit Page"""
    return render_template("edit_employee.html")


@app.route("/api/employees/<int:employee_id>", methods=["PUT"])
def update_employee(employee_id):
    """Updates specific employee details including password and codes"""
    try:
        data = request.get_json() or {}
        name = data.get("name")
        email = data.get("email")
        password = data.get("password")
        team = data.get("team", "General")
        dob = data.get("dob") if data.get("dob") else None
        joining_date = data.get("joining_date") if data.get("joining_date") else None

        if not name or not email:
            return jsonify({"status": "error", "message": "Name and Email are required"}), 400

        conn = get_db_connection()
        cur = conn.cursor()
        
        # Agar password input field khali nahi hai to password bhi update hoga
        if password and password.strip() != "":
            cur.execute("""
                UPDATE employees 
                SET name = %s, email = %s, password = %s, team = %s, dob = %s, joining_date = %s
                WHERE id = %s
            """, (name, email, password, team, dob, joining_date, employee_id))
        else:
            cur.execute("""
                UPDATE employees 
                SET name = %s, email = %s, team = %s, dob = %s, joining_date = %s
                WHERE id = %s
            """, (name, email, team, dob, joining_date, employee_id))
        
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"status": "success", "message": "Employee records updated successfully!"})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/employees/<int:employee_id>", methods=["DELETE"])
def delete_employee(employee_id):
    """Deletes an employee from the system entirely"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Check if employee exists
        cur.execute("SELECT name FROM employees WHERE id = %s", (employee_id,))
        emp = cur.fetchone()
        
        if not emp:
            cur.close()
            conn.close()
            return jsonify({"status": "error", "message": "Employee not found"}), 404
            
        # Deletion logic (FOREIGN KEY cascades will handle task removals seamlessly)
        cur.execute("DELETE FROM employees WHERE id = %s", (employee_id,))
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"status": "success", "message": f"Employee '{emp[0]}' has been deleted successfully!"})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500# -------------------------------------------------------------
# Push Notification Helper
# -------------------------------------------------------------
def create_notification(employee_id, title, message, notif_type="Assigned"):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO notifications (employee_id, title, message, type, is_read, created_at) 
            VALUES (%s, %s, %s, %s, false, CURRENT_TIMESTAMP)
        """, (employee_id, title, message, notif_type))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Notification DB Insert Error: {e}")

    ONESIGNAL_APP_ID = "bf1e7c43-6bd2-4b2e-8a3f-87c686f7482a"
    ONESIGNAL_API_KEY = "os_v2_app_x4phyq3l2jfs5cr7q7din52ifl5cweowzpsenjngvur6jpti65i4lkn4zori7bt3fzia7xzncbkrffjf5k65jb54xtepkvl6r4n432a"

    header = {
        "Content-Type": "application/json; charset=utf-8",
        "Authorization": f"Basic {ONESIGNAL_API_KEY}"
    }

    # Clean segment targets for flawless web standard alerts
    payload = {
        "app_id": ONESIGNAL_APP_ID,
        "included_segments": ["Subscribed Users"],
        "contents": {"en": message},
        "headings": {"en": title},
        "url": "https://vlgs-workspace.onrender.com/user_task"
    }

    try:
        res = requests.post("https://onesignal.com/api/v1/notifications", headers=header, data=json.dumps(payload))
        print("OneSignal Response:", res.status_code, res.text)
    except Exception as err:
        print("OneSignal Error:", err)

# -------------------------------------------------------------
# Authentication APIs
# -------------------------------------------------------------
@app.route("/login", methods=["POST"])
def login():
    try:
        data = request.get_json() or {}
        username = str(data.get("username", "")).strip()
        password = str(data.get("password", "")).strip()
        
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("SELECT id, username FROM admins WHERE LOWER(username)=LOWER(%s) AND password=%s", (username, password))
        admin_user = cur.fetchone()

        if admin_user:
            cur.close()
            conn.close()
            return jsonify({"success": True, "role": "admin", "name": admin_user[1], "id": admin_user[0]})

        cur.execute("SELECT id, name FROM employees WHERE LOWER(name)=LOWER(%s) AND password=%s", (username, password))
        employee_user = cur.fetchone()

        if employee_user:
            emp_id, emp_name = employee_user[0], employee_user[1]
            ip_addr = request.remote_addr

            cur.execute("INSERT INTO employee_sessions (employee_id, login_time, ip_address) VALUES (%s, CURRENT_TIMESTAMP, %s) RETURNING id", (emp_id, ip_addr))
            session_id = cur.fetchone()[0]
            conn.commit()
            cur.close()
            conn.close()

            create_notification(emp_id, "User Login", f"{emp_name} logged in.", "Logs")
            return jsonify({"success": True, "role": "employee", "name": emp_name, "id": emp_id, "session_id": session_id})

        cur.close()
        conn.close()
        return jsonify({"success": False, "message": "Invalid Username or Password"}), 401
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/logout", methods=["POST"])
def logout():
    try:
        data = request.get_json() or {}
        session_id = data.get("session_id")

        if not session_id:
            return jsonify({"success": False, "message": "Session ID required"}), 400

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT e.id, e.name FROM employee_sessions s JOIN employees e ON s.employee_id = e.id WHERE s.id = %s", (session_id,))
        emp_data = cur.fetchone()
        
        cur.execute("UPDATE employee_sessions SET logout_time = CURRENT_TIMESTAMP WHERE id = %s AND logout_time IS NULL", (session_id,))
        conn.commit()
        cur.close()
        conn.close()
        
        if emp_data:
            create_notification(emp_data[0], "User Logout", f"{emp_data[1]} logged out.", "Logs")

        return jsonify({"success": True, "message": "Logged out successfully"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/session_logs", methods=["GET"])
def get_session_logs():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT s.id, e.name, s.login_time, s.logout_time, s.ip_address
            FROM employee_sessions s
            JOIN employees e ON s.employee_id = e.id
            ORDER BY s.login_time DESC
        """)
        rows = cur.fetchall()
        cur.close()
        conn.close()

        return jsonify([{
            "id": row[0],
            "employee_name": row[1],
            "login_time": str(row[2]),
            "logout_time": str(row[3]) if row[3] else "Active Session",
            "ip_address": row[4] if row[4] else "N/A"
        } for row in rows])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# -------------------------------------------------------------
# Employee Operations
# -------------------------------------------------------------
@app.route('/add_employee', methods=['POST'])
@app.route('/api/add_employee', methods=['POST'])
def add_employee():
    try:
        data = request.get_json() or {}
        name = data.get('name')
        email = data.get('email')
        password = data.get('password', '123456')
        team = data.get('team', 'General')
        dob = data.get('dob') if data.get('dob') else None
        joining_date = data.get('joining_date') if data.get('joining_date') else None

        if not name or not email:
            return jsonify({"status": "error", "message": "Name and Email are required"}), 400

        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO employees(name, email, password, team, dob, joining_date)
            VALUES(%s, %s, %s, %s, %s, %s)
            RETURNING id;
        """, (name, email, password, team, dob, joining_date))
        
        new_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"status": "success", "message": "Employee Added Successfully", "id": new_id})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route("/api/employees", methods=["GET"])
def get_employees():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, name, email, team, dob, joining_date FROM employees ORDER BY name ASC")
        rows = cur.fetchall()
        cur.close()
        conn.close()

        return jsonify([{
            "id": row[0], 
            "name": row[1],
            "email": row[2],
            "team": row[3],
            "dob": str(row[4]) if row[4] else None,
            "joining_date": str(row[5]) if row[5] else None
        } for row in rows])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/upload_avatar/<int:employee_id>", methods=["POST"])
def upload_avatar(employee_id):
    try:
        data = request.get_json() or {}
        image_data = data.get("image")

        if not image_data:
            return jsonify({"success": False, "message": "No image data provided"}), 400

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE employees SET profile_pic = %s WHERE id = %s", (image_data, employee_id))
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"success": True, "message": "Profile picture updated successfully"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/employee_profile/<int:employee_id>", methods=["GET"])
def get_employee_profile(employee_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, name, email, team, dob, profile_pic, joining_date FROM employees WHERE id = %s", (employee_id,))
        emp_data = cur.fetchone()

        if not emp_data:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Employee not found"}), 404

        cur.execute("SELECT COUNT(*) FROM tasks WHERE assigned_to = %s AND status = 'Completed'", (employee_id,))
        completed_tasks = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM tasks WHERE assigned_to = %s AND status IN ('Overdue', 'Delayed')", (employee_id,))
        delayed_tasks = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM tasks WHERE assigned_to = %s", (employee_id,))
        total_tasks = cur.fetchone()[0]

        efficiency = 100 if total_tasks == 0 else round((completed_tasks / total_tasks) * 100)
        cur.close()
        conn.close()

        return jsonify({
            "success": True,
            "profile": {
                "emp_code": f"EMP-2026{emp_data[0]:02d}",
                "name": emp_data[1],
                "email": emp_data[2],
                "team": emp_data[3] if emp_data[3] else "Assign Team",
                "dob": str(emp_data[4]) if emp_data[4] else "",
                "profile_pic": emp_data[5] if emp_data[5] else "https://images.unsplash.com/photo-1534528741775-53994a69daeb?q=80&w=256",
                "joining_date": str(emp_data[6]) if emp_data[6] else "",
                "stats": {
                    "efficiency": f"{efficiency}%",
                    "completed": completed_tasks,
                    "delayed": delayed_tasks
                }
            }
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# -------------------------------------------------------------
# Tasks Management APIs
# -------------------------------------------------------------
@app.route("/api/task_records", methods=["GET"])
def get_all_task_records():
    try:
        update_overdue_tasks()
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT 
                t.id, 
                COALESCE(e.name, 'Unassigned') AS employee_name, 
                t.title, 
                t.description, 
                t.deadline, 
                t.status, 
                t.created_at,
                t.is_rescheduled
            FROM tasks t
            LEFT JOIN employees e ON t.assigned_to = e.id
            ORDER BY t.id DESC
        """)
        rows = cur.fetchall()
        cur.close()
        conn.close()

        return jsonify([{
            "id": row[0],
            "employee": row[1],
            "title": row[2],
            "description": row[3],
            "deadline": str(row[4]) if row[4] else "",
            "status": row[5],
            "created_at": str(row[6]) if row[6] else "",
            "is_rescheduled": row[7]
        } for row in rows])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/add_task", methods=["POST"])
def add_task():
    try:
        data = request.get_json() or {}
        title = data["title"]
        description = data.get("description", "")
        assigned_to = data["assigned_to"]
        deadline = data["deadline"]

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO tasks (title, description, assigned_to, deadline, is_rescheduled)
            VALUES (%s, %s, %s, %s, FALSE)
        """, (title, description, assigned_to, deadline))

        conn.commit()
        cur.close()
        conn.close()

        create_notification(assigned_to, "New Task Assigned", f"Assigned: {title}", "Assigned")
        return jsonify({"success": True, "message": "Task Created Successfully"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/tasks/<int:employee_id>", methods=["GET"])
def employee_tasks(employee_id):
    try:
        update_overdue_tasks()
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT 
                t.id, t.title, t.description, t.deadline, t.status, t.created_at, t.is_rescheduled
            FROM tasks t
            WHERE t.assigned_to = %s
            ORDER BY t.id DESC
        """, (employee_id,))
        rows = cur.fetchall()
        cur.close()
        conn.close()

        return jsonify([{
            "id": row[0],
            "title": row[1],
            "description": row[2],
            "deadline": str(row[3]),
            "status": row[4],
            "created_at": str(row[5]) if row[5] else "N/A",
            "is_rescheduled": row[6]
        } for row in rows])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/update_task_status", methods=["POST"])
def update_task_status_post():
    try:
        data = request.get_json() or {}
        task_id = data.get("id") or data.get("task_id")
        status = data.get("status")

        if not task_id or not status:
            return jsonify({"success": False, "error": "Missing task_id or status"}), 400

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT assigned_to, title FROM tasks WHERE id=%s", (task_id,))
        task_info = cur.fetchone()

        if status == "Completed":
            cur.execute("UPDATE tasks SET status = 'Completed', completed_at = CURRENT_TIMESTAMP WHERE id = %s", (task_id,))
        else:
            cur.execute("UPDATE tasks SET status = %s WHERE id = %s", (status, task_id))

        conn.commit()
        cur.close()
        conn.close()

        if task_info:
            create_notification(task_info[0], f"Task Status: {status}", f"Task '{task_info[1]}' updated to {status}.", "Completed" if status == "Completed" else "Assigned")

        return jsonify({"success": True, "message": "Status updated successfully"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# -------------------------------------------------------------
# Reschedule Handlers (Direct Self Reschedule - No Approval)
# -------------------------------------------------------------
@app.route("/api/request_reschedule", methods=["POST"])
def request_reschedule():
    try:
        data = request.get_json() or {}
        task_id = data.get("task_id")
        employee_id = data.get("employee_id")
        proposed_deadline = data.get("proposed_deadline")
        reason = data.get("reason", "Rescheduled by user")

        conn = get_db_connection()
        cur = conn.cursor()

        # Pehle purani deadline nikalo
        cur.execute("SELECT deadline FROM tasks WHERE id = %s", (task_id,))
        task_row = cur.fetchone()
        old_deadline = task_row[0] if task_row else None

        # 1. Reschedule History Log
        cur.execute("""
            INSERT INTO reschedule_requests (task_id, employee_id, old_deadline, proposed_deadline, reason, status)
            VALUES (%s, %s, %s, %s, %s, 'Approved')
        """, (task_id, employee_id, old_deadline, proposed_deadline, reason))

        # 2. Update Main Task: New Deadline, set is_rescheduled, and set Status back to Pending
        cur.execute("""
            UPDATE tasks 
            SET deadline = %s, status = 'Pending', is_rescheduled = TRUE 
            WHERE id = %s
        """, (proposed_deadline, task_id))

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"success": True, "message": "Deadline updated successfully!"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/rescheduled_tasks", methods=["GET"])
def get_rescheduled_tasks():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT 
                r.id AS request_id,
                t.id AS task_id,
                COALESCE(e.name, 'Unassigned') AS employee_name,
                t.title AS task_title,
                r.old_deadline,
                r.proposed_deadline,
                COALESCE(r.reason, 'No reason provided') AS reason,
                t.status AS task_status
            FROM reschedule_requests r
            JOIN tasks t ON r.task_id = t.id
            LEFT JOIN employees e ON t.assigned_to = e.id
            ORDER BY r.id DESC
        """)
        rows = cur.fetchall()
        cur.close()
        conn.close()

        return jsonify([{
            "request_id": row[0],
            "task_id": row[1],
            "employee_name": row[2],
            "task_title": row[3],
            "old_deadline": str(row[4]) if row[4] else "",
            "proposed_deadline": str(row[5]) if row[5] else "",
            "reason": row[6],
            "status": row[7]
        } for row in rows])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# -------------------------------------------------------------
# Notifications & Dashboard Stats
# -------------------------------------------------------------
@app.route('/api/get_notifications/<int:employee_id>', methods=['GET'])
def get_user_notifications(employee_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT id, title, message, type, is_read, created_at FROM notifications WHERE employee_id = %s ORDER BY id DESC", (employee_id,))
        notifications = cur.fetchall()
        
        cur.execute("UPDATE notifications SET is_read = true WHERE employee_id = %s", (employee_id,))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify(notifications)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/check_overdue_alerts/<int:employee_id>', methods=['GET'])
def check_overdue_alerts(employee_id):
    try:
        update_overdue_tasks()
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT title FROM tasks WHERE assigned_to = %s AND status = 'Overdue'", (employee_id,))
        overdue_tasks = cur.fetchall()
        
        if overdue_tasks:
            task_names = ", ".join([task['title'] for task in overdue_tasks])
            create_notification(employee_id, "⚠️ Overdue Reminder", f"Overdue tasks: {task_names}", notif_type="Overdue")
            cur.close()
            conn.close()
            return jsonify({"has_overdue": True, "message": "Overdue tasks pending!"})
        
        cur.close()
        conn.close()
        return jsonify({"has_overdue": False})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/admin_notifications", methods=["GET"])
def admin_notifications():
    try:
        update_overdue_tasks()
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, title, message, is_read, created_at, type FROM notifications ORDER BY created_at DESC")
        rows = cur.fetchall()
        cur.close()
        conn.close()

        return jsonify([{
            "id": row[0],
            "title": row[1],
            "message": row[2],
            "is_read": row[3],
            "created_at": str(row[4]),
            "type": row[5] if row[5] else "Assigned"
        } for row in rows])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/admin_notification_count", methods=["GET"])
def admin_notification_count():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM notifications WHERE is_read=false")
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        return jsonify({"count": count})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/dashboard_counts", methods=["GET"])
def dashboard_counts():
    try:
        update_overdue_tasks()
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("SELECT COUNT(*) FROM employees")
        employee_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM tasks")
        task_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM tasks WHERE status='Pending'")
        pending_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM tasks WHERE status='Completed'")
        completed_count = cur.fetchone()[0]

        cur.close()
        conn.close()

        return jsonify({
            "employees": employee_count,
            "tasks": task_count,
            "pending": pending_count,
            "completed": completed_count
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def update_overdue_tasks():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE tasks SET status='Overdue' WHERE deadline < CURRENT_TIMESTAMP AND status NOT IN ('Completed','Overdue')")
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print("Error updating overdue tasks:", e)

# -------------------------------------------------------------
# Auto-Cleanup Tasks (Older than 2 Weeks)
# -------------------------------------------------------------
@app.route("/api/admin/cleanup_old_tasks", methods=["DELETE"])
def cleanup_old_tasks():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            DELETE FROM tasks 
            WHERE status = 'Completed' 
            AND (completed_at < NOW() - INTERVAL '14 days' OR deadline < NOW() - INTERVAL '14 days')
        """)
        deleted_count = cur.rowcount
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"success": True, "message": f"Successfully deleted {deleted_count} tasks older than 2 weeks!"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)