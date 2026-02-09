import streamlit as st
import requests
import io
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN
from pptx.dml.color import RGBColor
from PIL import Image
import time
import json
import pandas as pd
from datetime import datetime
import hashlib
import sqlite3

# ============ DATABASE SETUP ============
def init_database():
    """Initialize database with migration support"""
    conn = sqlite3.connect('ppt_generator.db', check_same_thread=False)
    c = conn.cursor()
    
    # Create users table
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE NOT NULL,
                  password_hash TEXT NOT NULL,
                  email TEXT,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  last_login TIMESTAMP,
                  is_active BOOLEAN DEFAULT 1,
                  role TEXT DEFAULT 'user')''')
    
    # Create usage_logs table
    c.execute('''CREATE TABLE IF NOT EXISTS usage_logs
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  action TEXT,
                  topic TEXT,
                  slides_count INTEGER,
                  timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (user_id) REFERENCES users (id))''')
    
    # Create sessions table
    c.execute('''CREATE TABLE IF NOT EXISTS sessions
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  login_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  logout_time TIMESTAMP,
                  is_active BOOLEAN DEFAULT 1,
                  session_token TEXT,
                  FOREIGN KEY (user_id) REFERENCES users (id))''')
    
    # Migration: Add missing columns to existing sessions table
    try:
        # Check if is_active column exists
        c.execute("PRAGMA table_info(sessions)")
        columns = [column[1] for column in c.fetchall()]
        
        if 'is_active' not in columns:
            c.execute("ALTER TABLE sessions ADD COLUMN is_active BOOLEAN DEFAULT 1")
            conn.commit()
            
        if 'session_token' not in columns:
            c.execute("ALTER TABLE sessions ADD COLUMN session_token TEXT")
            conn.commit()
    except Exception as e:
        # If migration fails, it's okay - table might be new
        pass
    
    # Create admin user if not exists
    c.execute("SELECT * FROM users WHERE username = 'admin'")
    if not c.fetchone():
        admin_password = hashlib.sha256('admin123'.encode()).hexdigest()
        c.execute("INSERT INTO users (username, password_hash, email, role) VALUES (?, ?, ?, ?)",
                  ('admin', admin_password, 'admin@pptgen.com', 'admin'))
    
    conn.commit()
    conn.close()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def verify_user(username, password):
    """Verify and login user"""
    conn = sqlite3.connect('ppt_generator.db', check_same_thread=False)
    c = conn.cursor()
    
    try:
        password_hash = hash_password(password)
        c.execute("SELECT id, username, role, is_active FROM users WHERE username = ? AND password_hash = ?",
                  (username, password_hash))
        
        user = c.fetchone()
        
        if user and user[3]:
            c.execute("UPDATE users SET last_login = ? WHERE id = ?", (datetime.now(), user[0]))
            session_token = hashlib.md5(f"{user[0]}{datetime.now()}".encode()).hexdigest()
            
            # Try to update sessions with is_active column
            try:
                c.execute("UPDATE sessions SET is_active = 0, logout_time = ? WHERE user_id = ? AND is_active = 1", 
                          (datetime.now(), user[0]))
            except sqlite3.OperationalError:
                # is_active column doesn't exist, skip this step
                pass
            
            # Insert new session
            try:
                c.execute("INSERT INTO sessions (user_id, login_time, is_active, session_token) VALUES (?, ?, ?, ?)",
                          (user[0], datetime.now(), 1, session_token))
            except sqlite3.OperationalError:
                # Fallback to basic session insert without is_active
                c.execute("INSERT INTO sessions (user_id, login_time) VALUES (?, ?)",
                          (user[0], datetime.now()))
            
            conn.commit()
            conn.close()
            
            return {
                'id': user[0], 
                'username': user[1], 
                'role': user[2], 
                'is_active': user[3], 
                'session_token': session_token
            }
        
        conn.close()
        return None
    except Exception as e:
        conn.close()
        st.error(f"Login error: {str(e)}")
        return None

def create_user_by_admin(username, password, email):
    """Admin creates user"""
    conn = sqlite3.connect('ppt_generator.db', check_same_thread=False)
    c = conn.cursor()
    try:
        password_hash = hash_password(password)
        c.execute("INSERT INTO users (username, password_hash, email, role) VALUES (?, ?, ?, ?)",
                  (username, password_hash, email, 'user'))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False

def logout_user(user_id):
    """Logout user"""
    conn = sqlite3.connect('ppt_generator.db', check_same_thread=False)
    c = conn.cursor()
    
    try:
        c.execute("UPDATE sessions SET is_active = 0, logout_time = ? WHERE user_id = ? AND is_active = 1",
                  (datetime.now(), user_id))
    except sqlite3.OperationalError:
        # is_active column doesn't exist, just update logout_time
        c.execute("UPDATE sessions SET logout_time = ? WHERE user_id = ? AND logout_time IS NULL",
                  (datetime.now(), user_id))
    
    conn.commit()
    conn.close()

def log_usage(user_id, action, topic="", slides_count=0):
    """Log activity"""
    conn = sqlite3.connect('ppt_generator.db', check_same_thread=False)
    c = conn.cursor()
    c.execute("INSERT INTO usage_logs (user_id, action, topic, slides_count) VALUES (?, ?, ?, ?)",
              (user_id, action, topic, slides_count))
    conn.commit()
    conn.close()

def get_user_stats(user_id):
    """Get user stats"""
    conn = sqlite3.connect('ppt_generator.db', check_same_thread=False)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM usage_logs WHERE user_id = ? AND action = 'generate_presentation'", (user_id,))
    total_presentations = c.fetchone()[0]
    c.execute("SELECT SUM(slides_count) FROM usage_logs WHERE user_id = ? AND action = 'generate_presentation'", (user_id,))
    total_slides = c.fetchone()[0] or 0
    c.execute("SELECT COUNT(*) FROM sessions WHERE user_id = ?", (user_id,))
    total_logins = c.fetchone()[0]
    conn.close()
    return {'total_presentations': total_presentations, 'total_slides': total_slides, 'total_logins': total_logins}

def get_all_users():
    """Get all users"""
    conn = sqlite3.connect('ppt_generator.db', check_same_thread=False)
    c = conn.cursor()
    c.execute("SELECT id, username, email, created_at, last_login, is_active, role FROM users ORDER BY created_at DESC")
    users = c.fetchall()
    conn.close()
    return users

def get_currently_logged_in_users():
    """Get currently logged in users with their stats"""
    conn = sqlite3.connect('ppt_generator.db', check_same_thread=False)
    c = conn.cursor()
    
    try:
        # Try to query with is_active column
        c.execute("""
            SELECT u.id, u.username, u.email, s.login_time, u.role
            FROM sessions s
            JOIN users u ON s.user_id = u.id
            WHERE s.is_active = 1
            ORDER BY s.login_time DESC
        """)
        active_users = c.fetchall()
    except sqlite3.OperationalError:
        # Fallback: is_active column doesn't exist, return empty list
        active_users = []
    
    conn.close()
    return active_users

def get_user_activity_details(user_id):
    """Get detailed activity for a specific user"""
    conn = sqlite3.connect('ppt_generator.db', check_same_thread=False)
    c = conn.cursor()
    c.execute("""
        SELECT action, topic, slides_count, timestamp
        FROM usage_logs
        WHERE user_id = ?
        ORDER BY timestamp DESC
        LIMIT 20
    """, (user_id,))
    activities = c.fetchall()
    conn.close()
    return activities

def get_all_user_activities():
    """Get all activities from all users"""
    conn = sqlite3.connect('ppt_generator.db', check_same_thread=False)
    c = conn.cursor()
    c.execute("""
        SELECT u.username, l.action, l.topic, l.slides_count, l.timestamp
        FROM usage_logs l
        JOIN users u ON l.user_id = u.id
        ORDER BY l.timestamp DESC
        LIMIT 100
    """)
    activities = c.fetchall()
    conn.close()
    return activities

def get_system_stats():
    """Get system stats"""
    conn = sqlite3.connect('ppt_generator.db', check_same_thread=False)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users WHERE role = 'user'")
    total_users = c.fetchone()[0]
    
    try:
        c.execute("SELECT COUNT(*) FROM sessions WHERE is_active = 1")
        currently_online = c.fetchone()[0]
    except sqlite3.OperationalError:
        currently_online = 0
    
    c.execute("SELECT COUNT(*) FROM usage_logs WHERE action = 'generate_presentation'")
    total_presentations = c.fetchone()[0]
    c.execute("SELECT SUM(slides_count) FROM usage_logs WHERE action = 'generate_presentation'")
    total_slides = c.fetchone()[0] or 0
    c.execute("SELECT COUNT(*) FROM sessions WHERE DATE(login_time) = DATE('now')")
    today_logins = c.fetchone()[0]
    conn.close()
    return {
        'total_users': total_users,
        'currently_online': currently_online,
        'total_presentations': total_presentations,
        'total_slides': total_slides,
        'today_logins': today_logins
    }

def toggle_user_status(user_id, is_active):
    """Enable/disable user"""
    conn = sqlite3.connect('ppt_generator.db', check_same_thread=False)
    c = conn.cursor()
    c.execute("UPDATE users SET is_active = ? WHERE id = ?", (is_active, user_id))
    conn.commit()
    conn.close()

def delete_user(user_id):
    """Delete user"""
    conn = sqlite3.connect('ppt_generator.db', check_same_thread=False)
    c = conn.cursor()
    c.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()

# ============ LOGIN PAGE ============
def show_login_page():
    """Login page - same for admin and users"""
    st.markdown("""
        <style>
        .login-container {
            max-width: 400px;
            margin: 100px auto;
            padding: 40px;
            background: white;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .login-header {
            text-align: center;
            color: #1f77b4;
            margin-bottom: 30px;
        }
        </style>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown('<div class="login-container">', unsafe_allow_html=True)
        st.markdown('<div style="font-size: 60px; text-align: center; margin-bottom: 20px;">📊</div>', unsafe_allow_html=True)
        st.markdown('<h1 class="login-header">AI PowerPoint Generator</h1>', unsafe_allow_html=True)
        
        st.markdown("### 🔐 Login")
        
        username = st.text_input("Username", key="login_username")
        password = st.text_input("Password", type="password", key="login_password")
        
        col_btn1, col_btn2 = st.columns(2)
        
        with col_btn1:
            if st.button("🔓 Login", use_container_width=True, type="primary"):
                if username and password:
                    user = verify_user(username, password)
                    if user:
                        st.session_state.logged_in = True
                        st.session_state.user = user
                        log_usage(user['id'], 'login')
                        st.success(f"✅ Welcome, {username}!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("❌ Invalid credentials")
                else:
                    st.warning("⚠️ Enter username & password")
        
        with col_btn2:
            if st.button("🔑 Demo", use_container_width=True):
                st.info("**Admin:**\nUsername: `admin`\nPassword: `admin123`")
        
        st.markdown('</div>', unsafe_allow_html=True)

# ============ PAGE CONFIG ============
st.set_page_config(
    page_title="AI PPT Generator Pro",
    page_icon="📊",
    layout="wide"
)

init_database()

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user' not in st.session_state:
    st.session_state.user = None

if not st.session_state.logged_in:
    show_login_page()
    st.stop()

# ============ STYLES ============
st.markdown("""
<style>
.main-header {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    padding: 30px;
    border-radius: 10px;
    color: white;
    text-align: center;
    margin-bottom: 20px;
}
.admin-header {
    background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
    padding: 30px;
    border-radius: 10px;
    color: white;
    text-align: center;
    margin-bottom: 20px;
}
.user-info {
    background: #f0f8ff;
    padding: 15px;
    border-radius: 8px;
    margin-bottom: 20px;
}
.metric-box {
    background: white;
    padding: 20px;
    border-radius: 8px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    text-align: center;
}
.online-indicator {
    display: inline-block;
    width: 10px;
    height: 10px;
    background: #4caf50;
    border-radius: 50%;
    margin-right: 5px;
    animation: pulse 2s infinite;
}
@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
}
.activity-card {
    background: #f5f5f5;
    padding: 12px;
    border-radius: 6px;
    margin: 8px 0;
    border-left: 4px solid #1f77b4;
}
</style>
""", unsafe_allow_html=True)

# ============ SIDEBAR (Common for both) ============
with st.sidebar:
    user_stats = get_user_stats(st.session_state.user['id'])
    st.markdown(f"""
    <div class='user-info'>
        <h3>👤 {st.session_state.user['username']}</h3>
        <p>Role: <b>{st.session_state.user['role'].upper()}</b></p>
        <hr>
        <p>📊 Presentations: <b>{user_stats['total_presentations']}</b></p>
        <p>📄 Slides: <b>{user_stats['total_slides']}</b></p>
        <p>🔑 Logins: <b>{user_stats['total_logins']}</b></p>
    </div>
    """, unsafe_allow_html=True)
    
    if st.button("🚪 Logout", use_container_width=True):
        logout_user(st.session_state.user['id'])
        log_usage(st.session_state.user['id'], 'logout')
        st.session_state.logged_in = False
        st.session_state.user = None
        st.rerun()

# ============ ADMIN DASHBOARD (Completely Separate) ============
if st.session_state.user['role'] == 'admin':
    
    st.markdown('<div class="admin-header"><h1>👑 Admin Dashboard</h1><p>Complete System Overview & User Management</p></div>', unsafe_allow_html=True)
    
    # Top Stats
    sys_stats = get_system_stats()
    
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.markdown('<div class="metric-box">', unsafe_allow_html=True)
        st.metric("👥 Total Users", sys_stats['total_users'])
        st.markdown('</div>', unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="metric-box">', unsafe_allow_html=True)
        st.metric("🟢 Online Now", sys_stats['currently_online'])
        st.markdown('</div>', unsafe_allow_html=True)
    with col3:
        st.markdown('<div class="metric-box">', unsafe_allow_html=True)
        st.metric("📊 Presentations", sys_stats['total_presentations'])
        st.markdown('</div>', unsafe_allow_html=True)
    with col4:
        st.markdown('<div class="metric-box">', unsafe_allow_html=True)
        st.metric("📄 Total Slides", sys_stats['total_slides'])
        st.markdown('</div>', unsafe_allow_html=True)
    with col5:
        st.markdown('<div class="metric-box">', unsafe_allow_html=True)
        st.metric("🕒 Today Logins", sys_stats['today_logins'])
        st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Admin Tabs
    admin_tab1, admin_tab2, admin_tab3, admin_tab4 = st.tabs([
        "🟢 Live Activity Dashboard",
        "➕ Create User",
        "👥 Manage Users",
        "📊 All Activities Log"
    ])
    
    # ========== TAB 1: LIVE ACTIVITY DASHBOARD ==========
    with admin_tab1:
        st.markdown("## 🟢 Live User Activity Dashboard")
        st.info("🔄 This shows real-time data - refresh to see latest updates")
        
        if st.button("🔄 Refresh Dashboard", key="refresh_dash", type="primary"):
            st.rerun()
        
        st.markdown("---")
        
        # Currently Logged In Users
        st.markdown("### 👥 Currently Logged In Users")
        active_users = get_currently_logged_in_users()
        
        if active_users:
            st.success(f"**{len(active_users)} user(s) currently online**")
            
            for user in active_users:
                user_id, username, email, login_time, role = user
                
                # Get user's stats
                user_activity_stats = get_user_stats(user_id)
                
                col_a, col_b = st.columns([3, 1])
                
                with col_a:
                    st.markdown(f"""
<div style='background:#e8f5e9;padding:15px;border-radius:8px;margin:10px 0;'>
    <span class='online-indicator'></span>
    <b style='font-size:18px;'>{username}</b> <span style='background:#4caf50;color:white;padding:2px 8px;border-radius:4px;font-size:12px;'>{role}</span>
    <br><small>📧 {email if email else 'No email'}</small>
    <br><small>🕒 Logged in: {login_time}</small>
</div>
                    """, unsafe_allow_html=True)
                
                with col_b:
                    st.markdown("**User Stats:**")
                    st.write(f"📊 {user_activity_stats['total_presentations']} presentations")
                    st.write(f"📄 {user_activity_stats['total_slides']} slides")
                
                # Show recent activities of this user
                with st.expander(f"📜 View {username}'s Recent Activities"):
                    activities = get_user_activity_details(user_id)
                    
                    if activities:
                        for activity in activities:
                            action, topic, slides_count, timestamp = activity
                            
                            if action == 'generate_presentation':
                                st.markdown(f"""
<div class='activity-card'>
    <b>📊 Generated Presentation</b><br>
    <small>📌 Topic: {topic}</small><br>
    <small>📄 Slides: {slides_count}</small><br>
    <small>🕒 {timestamp}</small>
</div>
                                """, unsafe_allow_html=True)
                            elif action == 'login':
                                st.markdown(f"""
<div class='activity-card'>
    <b>🔓 Logged In</b><br>
    <small>🕒 {timestamp}</small>
</div>
                                """, unsafe_allow_html=True)
                    else:
                        st.info("No recent activities")
                
                st.markdown("---")
        else:
            st.warning("⚠️ No users currently logged in")
        
        st.markdown("---")
        
        # Recent Activity Summary
        st.markdown("### 📊 Recent System Activities (Last 10)")
        all_activities = get_all_user_activities()
        
        if all_activities:
            for activity in all_activities[:10]:
                username, action, topic, slides_count, timestamp = activity
                
                if action == 'generate_presentation':
                    st.markdown(f"""
<div class='activity-card'>
    👤 <b>{username}</b> generated a presentation<br>
    <small>📌 Topic: {topic} | 📄 Slides: {slides_count}</small><br>
    <small>🕒 {timestamp}</small>
</div>
                    """, unsafe_allow_html=True)
                elif action == 'login':
                    st.markdown(f"""
<div class='activity-card'>
    👤 <b>{username}</b> logged in<br>
    <small>🕒 {timestamp}</small>
</div>
                    """, unsafe_allow_html=True)
        else:
            st.info("No recent activities")
    
    # ========== TAB 2: CREATE USER ==========
    with admin_tab2:
        st.markdown("### ➕ Create New User Account")
        st.info("💡 Create user accounts and provide credentials to users")
        
        with st.form("create_user_form"):
            col_a, col_b = st.columns(2)
            with col_a:
                new_username = st.text_input("Username *", placeholder="john_doe")
                new_email = st.text_input("Email", placeholder="john@company.com")
            with col_b:
                new_password = st.text_input("Password *", type="password", placeholder="Min 6 chars")
                confirm_password = st.text_input("Confirm Password *", type="password")
            
            submitted = st.form_submit_button("✅ Create User", use_container_width=True, type="primary")
            
            if submitted:
                if new_username and new_password:
                    if new_password == confirm_password:
                        if len(new_password) >= 6:
                            success = create_user_by_admin(new_username, new_password, new_email)
                            if success:
                                st.success(f"""
### ✅ User Created Successfully!

**Share these credentials with the user:**

📧 **Username:** `{new_username}`  
🔑 **Password:** `{new_password}`  

✉️ Send them these login details.
                                """)
                            else:
                                st.error("❌ Username already exists!")
                        else:
                            st.error("❌ Password must be at least 6 characters")
                    else:
                        st.error("❌ Passwords don't match")
                else:
                    st.warning("⚠️ Fill all required fields")
    
    # ========== TAB 3: MANAGE USERS ==========
    with admin_tab3:
        st.markdown("### 👥 All Users Management")
        
        users = get_all_users()
        
        user_data = []
        for user in users:
            user_data.append({
                'ID': user[0],
                'Username': user[1],
                'Email': user[2] if user[2] else 'N/A',
                'Created': user[3],
                'Last Login': user[4] if user[4] else 'Never',
                'Active': '✅' if user[5] else '❌',
                'Role': user[6]
            })
        
        df_users = pd.DataFrame(user_data)
        st.dataframe(df_users, use_container_width=True, height=400)
        
        st.markdown("---")
        st.markdown("### ⚙️ User Actions")
        
        col_m1, col_m2, col_m3 = st.columns(3)
        
        with col_m1:
            user_id_action = st.number_input("User ID", min_value=1, step=1, key="user_manage_id")
        
        with col_m2:
            action_type = st.selectbox("Action", ["Enable Account", "Disable Account", "Delete User"])
        
        with col_m3:
            st.write("")
            if st.button("▶️ Execute", use_container_width=True, type="primary"):
                if user_id_action == 1:
                    st.error("❌ Cannot modify admin account!")
                else:
                    if action_type == "Enable Account":
                        toggle_user_status(user_id_action, 1)
                        st.success(f"✅ User {user_id_action} enabled!")
                        time.sleep(1)
                        st.rerun()
                    elif action_type == "Disable Account":
                        toggle_user_status(user_id_action, 0)
                        st.warning(f"⚠️ User {user_id_action} disabled!")
                        time.sleep(1)
                        st.rerun()
                    elif action_type == "Delete User":
                        delete_user(user_id_action)
                        st.error(f"🗑️ User {user_id_action} deleted!")
                        time.sleep(1)
                        st.rerun()
    
    # ========== TAB 4: ALL ACTIVITIES LOG ==========
    with admin_tab4:
        st.markdown("### 📊 Complete Activity Log (Last 100)")
        
        all_activities = get_all_user_activities()
        
        if all_activities:
            activity_records = []
            for activity in all_activities:
                username, action, topic, slides_count, timestamp = activity
                
                activity_records.append({
                    'Username': username,
                    'Action': action,
                    'Topic': topic if topic else '-',
                    'Slides': slides_count if slides_count else '-',
                    'Timestamp': timestamp
                })
            
            df_activities = pd.DataFrame(activity_records)
            st.dataframe(df_activities, use_container_width=True, height=600)
            
            # Download option
            csv = df_activities.to_csv(index=False)
            st.download_button(
                "📥 Download Activity Log (CSV)",
                csv,
                f"activity_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                "text/csv",
                key='download-csv'
            )
        else:
            st.info("No activities logged yet")

# ============ REGULAR USER PANEL (Completely Different View) ============
else:
    
    st.markdown('<div class="main-header"><h1>📊 AI PowerPoint Generator</h1><p>Create Professional Presentations with AI</p></div>', unsafe_allow_html=True)
    
    st.markdown("## 📝 Create Your Presentation")
    
    col1, col2 = st.columns(2)
    
    with col1:
        topic = st.text_input("📌 Presentation Topic", placeholder="e.g., AI in Healthcare")
        category = st.selectbox("📂 Category", ["Business", "Technical", "Marketing", "Sales", "Education"])
    
    with col2:
        slide_count = st.number_input("📄 Number of Slides", min_value=5, max_value=30, value=10)
        tone = st.selectbox("🎨 Tone", ["Professional", "Casual", "Formal", "Creative"])
    
    st.markdown("---")
    
    if st.button("🚀 Generate Presentation", type="primary", use_container_width=True):
        if topic:
            # Log the activity
            log_usage(st.session_state.user['id'], 'generate_presentation', topic, slide_count)
            
            st.success(f"✅ Generating {slide_count} slides on: **{topic}**")
            st.info("🔧 Your full PPT generation code goes here...")
            
            # Simulate some processing
            with st.spinner("Creating presentation..."):
                time.sleep(2)
            
            st.success("✅ Presentation generated successfully!")
            st.balloons()
            
        else:
            st.error("⚠️ Please enter a topic")
    
    st.markdown("---")
    
    # User's Recent Activity
    st.markdown("### 📊 Your Recent Activities")
    
    my_activities = get_user_activity_details(st.session_state.user['id'])
    
    if my_activities:
        for activity in my_activities[:10]:
            action, topic, slides_count, timestamp = activity
            
            if action == 'generate_presentation':
                st.markdown(f"""
<div class='activity-card'>
    <b>📊 Generated Presentation</b><br>
    <small>📌 Topic: {topic}</small><br>
    <small>📄 Slides: {slides_count}</small><br>
    <small>🕒 {timestamp}</small>
</div>
                """, unsafe_allow_html=True)
    else:
        st.info("No activities yet. Create your first presentation!")

# Footer
st.markdown("---")
st.markdown(f"""
<div style='text-align: center; color: #666;'>
    <p>🔐 Logged in as: <b>{st.session_state.user['username']}</b> ({st.session_state.user['role']}) | {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
</div>
""", unsafe_allow_html=True)
