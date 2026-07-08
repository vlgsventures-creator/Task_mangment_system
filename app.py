from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
import requests
import json

app = Flask(__name__)
CORS(app)

# PostgreSQL Connection Helper
def get_db_connection():
    return psycopg2.connect(
        host="127.0.0.1",
        database="vlgsWorkspace_DB",
        user="postgres",
        password="vlgs24"
    )

# -------------------------
# Pages (HTML Templates)
# -------------------------

@app.route("/")
def login_page():
    return render_template("login.html")

@app.route("/user")
def user_page():
    return render_template("user.html")

@app.route("/admin")
def admin_page():
    return render_template("admin.html")

@app.route("/add_employee")
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

@app.route('/OneSignalSDKWorker.js')
def onesignal_worker():
    return app.send_static_file('OneSignalSDKWorker.js')

@app.route('/rescheduled_tasks_page')
def rescheduled_tasks_page():
    return render_template('rescheduled_tasks.html')

@app.route("/api/rescheduled_tasks", methods=["GET"])
def get_rescheduled_tasks_alias():
    return get_admin_reschedule_requests()
# --------------------------------------------
# Notification & Push Helper Function
# --------------------------------------------
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
        print(f"Database Insert Error: {e}")

    ONESIGNAL_APP_ID = "bf1e7c43-6bd2-4b2e-8a3f-87c686f7482a"
    ONESIGNAL_API_KEY = "os_v2_app_x4phyq3l2jfs5cr7q7din52ifl5cweowzpsenjngvur6jpti65i4lkn4zori7bt3fzia7xzncbkrffjf5k65jb54xtepkvl6r4n432a"

    header = {
        "Content-Type": "application/json; charset=utf-8",
        "Authorization": f"Basic {ONESIGNAL_API_KEY}"
    }

    payload = {
        "app_id": ONESIGNAL_APP_ID,
        "included_segments": ["All Users"],
        "contents": {"en": message},
        "headings": {"en": title},
        "url": "http://localhost:5000/user_task"
    }

    try:
        req = requests.post("https://onesignal.com/api/v1/notifications", headers=header, data=json.dumps(payload))
        if req.status_code == 200:
            print("Push Notification Sent Successfully via OneSignal!")
        else:
            print(f"OneSignal Error: {req.status_code} - {req.text}")
    except Exception as err:
        print("OneSignal API Request Failed:", err)

# -------------------------
# Login & Logout APIs
# -------------------------
@app.route("/login", methods=["POST"])
def login():
    try:
        data = request.get_json()
        username = str(data["username"]).strip()
        password = str(data["password"]).strip()
        
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute(
            "SELECT id, username FROM admins WHERE LOWER(username)=LOWER(%s) AND password=%s",
            (username, password)
        )
        admin_user = cur.fetchone()

        if admin_user:
            cur.close()
            conn.close()
            return jsonify({
                "success": True,
                "role": "admin",
                "name": admin_user[1],
                "id": admin_user[0]
            })

        cur.execute(
            "SELECT id, name FROM employees WHERE LOWER(name)=LOWER(%s) AND password=%s",
            (username, password)
        )
        employee_user = cur.fetchone()

        if employee_user:
            emp_id = employee_user[0]
            emp_name = employee_user[1]
            ip_addr = request.remote_addr

            cur.execute("""
                INSERT INTO employee_sessions (employee_id, login_time, ip_address)
                VALUES (%s, CURRENT_TIMESTAMP, %s) RETURNING id
            """, (emp_id, ip_addr))
            
            session_id = cur.fetchone()[0]
            conn.commit()
            cur.close()
            conn.close()

            create_notification(emp_id, "User Login", f"{emp_name} has logged into the workspace.", "Logs")

            return jsonify({
                "success": True,
                "role": "employee",
                "name": emp_name,
                "id": emp_id,
                "session_id": session_id
            })

        cur.close()
        conn.close()
        return jsonify({"success": False, "message": "Wrong Username or Password"})

    except Exception as e:
        print("ERROR:", e)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/logout", methods=["POST"])
def logout():
    try:
        data = request.get_json()
        session_id = data.get("session_id")

        if not session_id:
            return jsonify({"success": False, "message": "No active session found"}), 400

        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("SELECT e.id, e.name FROM employee_sessions s JOIN employees e ON s.employee_id = e.id WHERE s.id = %s", (session_id,))
        emp_data = cur.fetchone()
        
        cur.execute("""
            UPDATE employee_sessions 
            SET logout_time = CURRENT_TIMESTAMP 
            WHERE id = %s AND logout_time IS NULL
        """, (session_id,))
        
        conn.commit()
        cur.close()
        conn.close()
        
        if emp_data:
            create_notification(emp_data[0], "User Logout", f"{emp_data[1]} has logged out.", "Logs")

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

        logs = [{
            "id": row[0],
            "employee_name": row[1],
            "login_time": str(row[2]),
            "logout_time": str(row[3]) if row[3] else "Active Session",
            "ip_address": row[4] if row[4] else "N/A"
        } for row in rows]

        return jsonify(logs)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# -------------------------
# Employee Management
# -------------------------
@app.route('/add_employee', methods=['POST'])
def add_employee():
    try:
        data = request.get_json()
        name = data['name']
        email = data['email']
        password = data['password']
        team = data.get('team')
        dob = data.get('dob')
        joining_date = data.get('joining_date')

        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO employees(name, email, password, team, dob, joining_date)
            VALUES(%s, %s, %s, %s, %s, %s)
        """, (name, email, password, team, dob, joining_date))
        
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"status": "success", "message": "Employee Added Successfully"})
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

        employees = [
            {
                "id": row[0], 
                "name": row[1],
                "email": row[2],
                "team": row[3],
                "dob": str(row[4]) if row[4] else None,
                "joining_date": str(row[5]) if row[5] else None
            } 
            for row in rows
        ]
        return jsonify(employees)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# -------------------------
# Tasks Management
# -------------------------
@app.route("/api/add_task", methods=["POST"])
def add_task():
    try:
        data = request.get_json()
        title = data["title"]
        description = data["description"]
        assigned_to = data["assigned_to"]
        deadline = data["deadline"]

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO tasks (title, description, assigned_to, deadline)
            VALUES (%s, %s, %s, %s)
        """, (title, description, assigned_to, deadline))

        conn.commit()
        cur.close()
        conn.close()

        create_notification(assigned_to, "New Task Assigned", f"You have been assigned: {title}", "Assigned")

        return jsonify({"success": True, "message": "Task Created Successfully"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# UPDATED USER TASK FETCH (With Pending Reschedule Check)
@app.route("/api/tasks/<int:employee_id>", methods=["GET"])
def employee_tasks(employee_id):
    try:
        update_overdue_tasks()
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT 
                t.id, 
                t.title, 
                t.description, 
                t.deadline, 
                t.status, 
                t.created_at,
                CASE WHEN r.id IS NOT NULL THEN TRUE ELSE FALSE END AS reschedule_requested
            FROM tasks t
            LEFT JOIN reschedule_requests r 
                ON t.id = r.task_id AND r.status = 'Pending'
            WHERE t.assigned_to = %s
            ORDER BY t.id DESC
        """, (employee_id,))
        rows = cur.fetchall()
        cur.close()
        conn.close()

        tasks = [{
            "id": row[0],
            "title": row[1],
            "description": row[2],
            "deadline": str(row[3]),
            "status": row[4],
            "created_at": str(row[5]) if row[5] else "N/A",
            "reschedule_requested": row[6]
        } for row in rows]

        return jsonify(tasks)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/update_task_status", methods=["POST"])
def update_task_status_post():
    try:
        data = request.get_json()
        task_id = data["id"]
        status = data["status"]
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("SELECT assigned_to, title FROM tasks WHERE id=%s", (task_id,))
        task_info = cur.fetchone()

        if status == "Completed":
            cur.execute("""
                UPDATE tasks
                SET status=%s, completed_at=CURRENT_TIMESTAMP
                WHERE id=%s
            """, (status, task_id))
        else:
            cur.execute("UPDATE tasks SET status=%s WHERE id=%s", (status, task_id))

        conn.commit()
        cur.close()
        conn.close()
        
        if task_info:
            emp_id, task_title = task_info[0], task_info[1]
            notif_type = "Completed" if status == "Completed" else "Assigned"
            create_notification(emp_id, f"Task Status: {status}", f"Task '{task_title}' status shifted to {status}.", notif_type)

        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ----------------------------------
# User Side & Notifications APIs
# ----------------------------------
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
            msg = f"Attention! You have overdue tasks: {task_names}. Please complete them immediately."
            create_notification(employee_id, "⚠️ Overdue Reminder", msg, notif_type="Overdue")
            cur.close()
            conn.close()
            return jsonify({"has_overdue": True, "message": "Reminder: You have overdue tasks pending!"})
        
        cur.close()
        conn.close()
        return jsonify({"has_overdue": False})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/today_tasks/<int:employee_id>", methods=["GET"])
def today_tasks(employee_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, title, description, deadline, status
            FROM tasks
            WHERE assigned_to=%s
            AND DATE(deadline)=CURRENT_DATE
            ORDER BY deadline ASC
        """, (employee_id,))
        rows = cur.fetchall()
        cur.close()
        conn.close()

        tasks = [{
            "id": row[0],
            "title": row[1],
            "description": row[2],
            "deadline": str(row[3]),
            "status": row[4]
        } for row in rows]

        return jsonify(tasks)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# -------------------------
# Admin Notifications APIs
# -------------------------
@app.route("/api/admin_notifications", methods=["GET"])
def admin_notifications():
    try:
        update_overdue_tasks()
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, title, message, is_read, created_at, type
            FROM notifications
            ORDER BY created_at DESC
        """)
        rows = cur.fetchall()
        cur.close()
        conn.close()

        data = [{
            "id": row[0],
            "title": row[1],
            "message": row[2],
            "is_read": row[3],
            "created_at": str(row[4]),
            "type": row[5] if row[5] else "Assigned"
        } for row in rows]

        return jsonify(data)
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


@app.route("/api/read_all_notifications", methods=["PUT"])
def read_all_notifications():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE notifications SET is_read=true WHERE is_read=false")
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/task_records", methods=["GET"])
def task_records_api():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT t.id, e.name, t.title, t.description, t.deadline, t.status, t.created_at
            FROM tasks t
            JOIN employees e ON t.assigned_to = e.id
            ORDER BY t.created_at DESC
        """)
        rows = cur.fetchall()
        cur.close()
        conn.close()

        tasks = [{
            "id": row[0],
            "employee": row[1],
            "title": row[2],
            "description": row[3] if row[3] else "",
            "deadline": str(row[4]),
            "status": row[5],
            "created_at": str(row[6])
        } for row in rows]

        return jsonify(tasks)
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
        cur.execute("""
            UPDATE tasks
            SET status='Overdue'
            WHERE deadline < CURRENT_TIMESTAMP
            AND status NOT IN ('Completed','Overdue')
        """)
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print("Error updating overdue tasks:", e)

# -------------------------------------------------------------
# RESCHEDULE REQUESTS (User & Admin Handlers)
# -------------------------------------------------------------

# 1. User Reschedule Request Bhejega (Status = 'Pending')
# 1. Main Rescheduled Tasks API (Sabhi Requests Fetch Karega: Pending, Approved, Rejected)
@app.route('/api/rescheduled_tasks', methods=['GET'])
def get_rescheduled_tasks():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT 
                r.id AS request_id,
                t.id AS task_id,
                e.name AS employee_name,
                t.title AS task_title,
                t.deadline AS old_deadline,
                r.proposed_deadline AS new_deadline,
                r.reason,
                r.status,
                r.created_at
            FROM reschedule_requests r
            JOIN tasks t ON r.task_id = t.id
            JOIN employees e ON r.employee_id = e.id
            ORDER BY r.created_at DESC
        """)
        rows = cur.fetchall()
        cur.close()
        conn.close()

        # Frontend JS ke sath keys match kar di gayi hain
        requests = [
            {
                "request_id": row[0],
                "task_id": row[1],
                "employee_name": row[2],  # Fix: 'employee' -> 'employee_name'
                "employee": row[2],       # Safe backup
                "task_title": row[3],     # Fix: 'title' -> 'task_title'
                "title": row[3],          # Safe backup
                "old_deadline": str(row[4]) if row[4] else None,
                "proposed_deadline": str(row[5]) if row[5] else None, # Fix: 'new_deadline' -> 'proposed_deadline'
                "new_deadline": str(row[5]) if row[5] else None,
                "reason": row[6],
                "status": row[7],
                "created_at": str(row[8]) if row[8] else None
            }
            for row in rows
        ]
        return jsonify(requests)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
# 2. Admin Pending Requests Fetch karega
@app.route("/api/admin/reschedule_requests", methods=["GET"])
def get_admin_reschedule_requests():
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT 
                r.id AS request_id,
                r.task_id,
                t.title AS task_title,
                e.name AS employee_name,
                t.deadline AS old_deadline,
                r.proposed_deadline,
                r.reason,
                r.status,
                r.created_at
            FROM reschedule_requests r
            JOIN tasks t ON r.task_id = t.id
            JOIN employees e ON r.employee_id = e.id
            WHERE r.status = 'Pending'
            ORDER BY r.created_at DESC
        """)
        requests_list = cur.fetchall()
        cur.close()
        conn.close()

        for req in requests_list:
            req['old_deadline'] = str(req['old_deadline']) if req['old_deadline'] else None
            req['proposed_deadline'] = str(req['proposed_deadline']) if req['proposed_deadline'] else None
            req['created_at'] = str(req['created_at']) if req['created_at'] else None

        return jsonify(requests_list)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# 3. Admin Approve ya Reject karega
@app.route("/api/admin/action_reschedule", methods=["POST"])
def action_reschedule():
    try:
        data = request.get_json()
        request_id = data.get("request_id")
        action = data.get("action") # 'approve' or 'reject'

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT task_id, employee_id, proposed_deadline 
            FROM reschedule_requests 
            WHERE id = %s
        """, (request_id,))
        req_data = cur.fetchone()

        if not req_data:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Request not found"}), 404

        task_id, emp_id, new_deadline = req_data[0], req_data[1], req_data[2]

        if action == 'approve':
            cur.execute("UPDATE reschedule_requests SET status = 'Approved' WHERE id = %s", (request_id,))
            
            cur.execute("""
                UPDATE tasks 
                SET deadline = %s, status = 'Pending' 
                WHERE id = %s
            """, (new_deadline, task_id))

            create_notification(
                emp_id, 
                "✅ Reschedule Approved", 
                "Your reschedule request has been approved by Admin! Deadline updated.", 
                "Assigned"
            )

        elif action == 'reject':
            cur.execute("UPDATE reschedule_requests SET status = 'Rejected' WHERE id = %s", (request_id,))

            create_notification(
                emp_id, 
                "❌ Reschedule Rejected", 
                "Your reschedule request was rejected by Admin.", 
                "Overdue"
            )

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"success": True, "message": f"Request {action}d successfully!"})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    
# -------------------------
# Dynamic Employee Profile APIs
# -------------------------
@app.route("/api/update_profile/<int:employee_id>", methods=["POST"])
def update_profile(employee_id):
    try:
        data = request.get_json()
        dob = data.get("dob")
        team = data.get("team")

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE employees 
            SET dob = %s, team = %s 
            WHERE id = %s
        """, (dob if dob else None, team, employee_id))
        
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"success": True, "message": "Profile updated successfully"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/upload_avatar/<int:employee_id>", methods=["POST"])
def upload_avatar(employee_id):
    try:
        data = request.get_json()
        image_data = data.get("image")

        if not image_data:
            return jsonify({"success": False, "message": "No image data found"}), 400

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE employees SET profile_pic = %s WHERE id = %s", (image_data, employee_id))
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({"success": True, "message": "Avatar updated successfully"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/employee_profile/<int:employee_id>", methods=["GET"])
def get_employee_profile(employee_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT id, name, email, team, dob, profile_pic, joining_date 
            FROM employees 
            WHERE id = %s
        """, (employee_id,))
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
    

 # -------------------------
# Auto-Cleanup Tasks (Older than 2 Weeks)
# -------------------------
@app.route("/api/admin/cleanup_old_tasks", methods=["DELETE"])
def cleanup_old_tasks():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # 2 hafte (14 days) se purane completed tasks delete karega
        cur.execute("""
            DELETE FROM tasks 
            WHERE status = 'Completed' 
            AND (completed_at < NOW() - INTERVAL '14 days' OR deadline < NOW() - INTERVAL '14 days')
        """)
        
        deleted_count = cur.rowcount  # Kitne rows delete hue
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({
            "success": True, 
            "message": f"Successfully deleted {deleted_count} tasks older than 2 weeks!"
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    
       
if __name__ == "__main__":
    app.run(debug=True)