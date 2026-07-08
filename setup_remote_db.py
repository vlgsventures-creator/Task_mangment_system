import psycopg2

# Yahan Render se copy ki gayi External Database URL paste karein
DB_URL = "postgresql://vlgs_user:HtBKKN2joUeZsEhRzM3bWczANVE5S72Q@dpg-d973u7ss728c738l6g9g-a.singapore-postgres.render.com/vlgs_db"

def create_tables():
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS employees (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                role VARCHAR(50) DEFAULT 'Employee',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id SERIAL PRIMARY KEY,
                title VARCHAR(200) NOT NULL,
                description TEXT,
                assigned_to INT REFERENCES employees(id) ON DELETE CASCADE,
                deadline TIMESTAMP,
                status VARCHAR(50) DEFAULT 'Pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS reschedule_requests (
                id SERIAL PRIMARY KEY,
                task_id INT REFERENCES tasks(id) ON DELETE CASCADE,
                employee_id INT REFERENCES employees(id) ON DELETE CASCADE,
                proposed_deadline TIMESTAMP,
                reason TEXT,
                status VARCHAR(50) DEFAULT 'Pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        conn.commit()
        cur.close()
        conn.close()
        print("🎉 Remote Render Database me saare tables ban gaye hain!")
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    create_tables()