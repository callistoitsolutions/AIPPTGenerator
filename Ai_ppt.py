import streamlit as st
import requests
import base64
import io
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN
from pptx.dml.color import RGBColor
from PIL import Image
import time
import json
import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from datetime import datetime
import hashlib
import sqlite3

# ============================================================================
# DATABASE FUNCTIONS
# ============================================================================

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
        c.execute("PRAGMA table_info(sessions)")
        columns = [column[1] for column in c.fetchall()]
        
        if 'is_active' not in columns:
            c.execute("ALTER TABLE sessions ADD COLUMN is_active BOOLEAN DEFAULT 1")
            conn.commit()
            
        if 'session_token' not in columns:
            c.execute("ALTER TABLE sessions ADD COLUMN session_token TEXT")
            conn.commit()
    except Exception as e:
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
            
            try:
                c.execute("UPDATE sessions SET is_active = 0, logout_time = ? WHERE user_id = ? AND is_active = 1", 
                          (datetime.now(), user[0]))
            except sqlite3.OperationalError:
                pass
            
            try:
                c.execute("INSERT INTO sessions (user_id, login_time, is_active, session_token) VALUES (?, ?, ?, ?)",
                          (user[0], datetime.now(), 1, session_token))
            except sqlite3.OperationalError:
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
    """Get currently logged in users"""
    conn = sqlite3.connect('ppt_generator.db', check_same_thread=False)
    c = conn.cursor()
    try:
        c.execute("""
            SELECT u.id, u.username, u.email, s.login_time, u.role
            FROM sessions s
            JOIN users u ON s.user_id = u.id
            WHERE s.is_active = 1
            ORDER BY s.login_time DESC
        """)
        active_users = c.fetchall()
    except sqlite3.OperationalError:
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

# ============================================================================
# IMAGE GENERATION FUNCTIONS
# ============================================================================

def get_google_image(query, api_key, cx):
    """Get image using Google Custom Search API"""
    try:
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            'key': api_key,
            'cx': cx,
            'q': query,
            'searchType': 'image',
            'num': 3,
            'imgSize': 'large',
            'imgType': 'photo',
            'safe': 'active',
            'fileType': 'jpg,png'
        }
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if 'items' in data and len(data['items']) > 0:
                for item in data['items'][:3]:
                    try:
                        image_url = item['link']
                        img_response = requests.get(image_url, timeout=10, headers={
                            'User-Agent': 'Mozilla/5.0'
                        })
                        if img_response.status_code == 200 and len(img_response.content) > 5000:
                            img = Image.open(io.BytesIO(img_response.content))
                            if img.size[0] > 300 and img.size[1] > 200:
                                return img_response.content
                    except:
                        continue
        return None
    except:
        return None

def get_unsplash_image(query, width=800, height=600):
    """Get image from Unsplash"""
    try:
        clean_query = query.strip().replace(' ', ',')
        url = f"https://source.unsplash.com/{width}x{height}/?{clean_query}"
        response = requests.get(url, timeout=15, allow_redirects=True, headers={
            'User-Agent': 'Mozilla/5.0'
        })
        if response.status_code == 200 and len(response.content) > 5000:
            return response.content
        return None
    except:
        return None

def get_topic_relevant_image(main_topic, slide_title, google_api_key, google_cx, use_unsplash):
    """Get relevant image"""
    search_terms = []
    if slide_title:
        search_terms.append(slide_title)
    if main_topic:
        search_terms.append(main_topic)
    
    for term in search_terms:
        if google_api_key and google_cx:
            image_data = get_google_image(term, google_api_key, google_cx)
            if image_data:
                return image_data
        
        if use_unsplash:
            image_data = get_unsplash_image(term)
            if image_data:
                return image_data
    
    return None

# ============================================================================
# AI CONTENT GENERATION
# ============================================================================

def repair_truncated_json(json_text):
    """Attempt to repair truncated JSON"""
    text = json_text.strip()
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()
    
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    slides = []
    slides_start = text.find('"slides"')
    if slides_start == -1:
        return None
    
    bracket_pos = text.find('[', slides_start)
    if bracket_pos == -1:
        return None
    
    current_pos = bracket_pos + 1
    brace_count = 0
    slide_start = -1
    
    while current_pos < len(text):
        char = text[current_pos]
        if char == '{' and brace_count == 0:
            slide_start = current_pos
            brace_count = 1
        elif char == '{':
            brace_count += 1
        elif char == '}':
            brace_count -= 1
            if brace_count == 0 and slide_start != -1:
                slide_text = text[slide_start:current_pos + 1]
                try:
                    slide_obj = json.loads(slide_text)
                    if 'title' in slide_obj:
                        if 'bullets' not in slide_obj:
                            slide_obj['bullets'] = []
                        if 'image_prompt' not in slide_obj:
                            slide_obj['image_prompt'] = slide_obj['title']
                        if 'speaker_notes' not in slide_obj:
                            slide_obj['speaker_notes'] = ""
                        slides.append(slide_obj)
                except:
                    pass
                slide_start = -1
        current_pos += 1
    
    if slides:
        return {"slides": slides}
    return None

def generate_content_with_ai(api_key, topic, category, slide_count, tone, audience, key_points, model_choice, language, groq_api_key=None):
    """Generate presentation content using AI"""
    try:
        use_groq_api = "Groq" in model_choice and groq_api_key
        
        if use_groq_api:
            if "Llama 3.3" in model_choice:
                model = "llama-3.3-70b-versatile"
            else:
                model = "mixtral-8x7b-32768"
            api_url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {groq_api_key.strip()}",
                "Content-Type": "application/json",
            }
        else:
            if "Gemini" in model_choice:
                model = "google/gemini-2.0-flash-exp:free"
            elif "Llama" in model_choice:
                model = "meta-llama/llama-3.2-3b-instruct:free"
            elif "Mistral" in model_choice:
                model = "mistralai/mistral-7b-instruct:free"
            else:
                model = "anthropic/claude-3.5-sonnet"
            api_url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {api_key.strip()}",
                "Content-Type": "application/json",
            }
        
        calculated_tokens = min(slide_count * 350 + 500, 4000)
        language_instruction = f"Generate ALL content in {language} language." if language != "English" else ""
        
        prompt = f"""{language_instruction}
Create a {slide_count}-slide presentation about: {topic}
Category: {category} | Tone: {tone} | Audience: {audience}
{f"Include these points: {key_points}" if key_points else ""}

Return ONLY valid JSON (no markdown):
{{"slides": [
  {{
    "title": "Main Title",
    "bullets": [],
    "image_prompt": "professional {topic}",
    "speaker_notes": "Introduction"
  }},
  {{
    "title": "Key Point",
    "bullets": ["Point 1", "Point 2", "Point 3"],
    "image_prompt": "{topic} concept",
    "speaker_notes": "Explain points"
  }}
]}}

CRITICAL:
1. First slide: TITLE ONLY (empty bullets)
2. Other slides: 3-5 bullets each
3. Complete sentences (8-15 words)
4. Total: exactly {slide_count} slides
5. Return ONLY JSON

Generate now:"""

        response = requests.post(
            api_url,
            headers=headers,
            json={
                "model": model,
                "max_tokens": calculated_tokens,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=60
        )
        
        if response.status_code == 200:
            data = response.json()
            content_text = data["choices"][0]["message"]["content"]
            slides_data = repair_truncated_json(content_text)
            
            if slides_data and "slides" in slides_data:
                slides = slides_data["slides"]
                if not slides:
                    return None
                
                for i, slide in enumerate(slides):
                    if 'bullets' not in slide:
                        slide['bullets'] = []
                    if 'image_prompt' not in slide:
                        slide['image_prompt'] = slide.get('title', topic)
                    if 'speaker_notes' not in slide:
                        slide['speaker_notes'] = ""
                
                return slides
        return None
    except Exception as e:
        st.error(f"Error: {str(e)}")
        return None

# ============================================================================
# POWERPOINT CREATION
# ============================================================================

def create_powerpoint(slides_content, theme, image_mode, google_api_key, google_cx, use_unsplash, topic):
    """Create PowerPoint presentation"""
    prs = Presentation()
    prs.slide_width = Inches(10)
    prs.slide_height = Inches(7.5)
    
    themes = {
        "Corporate Blue": {"bg": RGBColor(240, 248, 255), "accent": RGBColor(31, 119, 180), "text": RGBColor(0, 0, 0)},
        "Modern Purple": {"bg": RGBColor(240, 242, 246), "accent": RGBColor(138, 43, 226), "text": RGBColor(0, 0, 0)},
        "Dark": {"bg": RGBColor(30, 30, 30), "accent": RGBColor(255, 215, 0), "text": RGBColor(255, 255, 255)},
        "Soft Pastel": {"bg": RGBColor(255, 250, 240), "accent": RGBColor(255, 182, 193), "text": RGBColor(60, 60, 60)},
        "Green": {"bg": RGBColor(245, 255, 250), "accent": RGBColor(34, 139, 34), "text": RGBColor(0, 0, 0)}
    }
    
    color_scheme = themes.get(theme, themes["Corporate Blue"])
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for idx, slide_data in enumerate(slides_content):
        status_text.text(f"Creating slide {idx + 1}/{len(slides_content)}...")
        progress_bar.progress((idx + 1) / len(slides_content))
        
        blank_slide_layout = prs.slide_layouts[6]
        slide = prs.slides.add_slide(blank_slide_layout)
        
        # Background
        background = slide.background
        fill = background.fill
        fill.solid()
        fill.fore_color.rgb = color_scheme["bg"]
        
        # Title
        title_box = slide.shapes.add_textbox(Inches(0.5), Inches(0.5), Inches(8.5), Inches(1))
        title_frame = title_box.text_frame
        title_frame.text = slide_data["title"]
        title_frame.paragraphs[0].font.size = Pt(36 if idx == 0 else 28)
        title_frame.paragraphs[0].font.bold = True
        title_frame.paragraphs[0].font.color.rgb = color_scheme["accent"]
        title_frame.paragraphs[0].alignment = PP_ALIGN.CENTER if idx == 0 else PP_ALIGN.LEFT
        
        # Bullets
        if idx > 0 and slide_data.get("bullets"):
            bullet_width = Inches(5.5) if image_mode == "With Images" else Inches(9)
            bullet_box = slide.shapes.add_textbox(Inches(0.5), Inches(2), bullet_width, Inches(4.5))
            text_frame = bullet_box.text_frame
            text_frame.word_wrap = True
            
            for bullet in slide_data["bullets"]:
                p = text_frame.add_paragraph()
                p.text = bullet
                p.level = 0
                p.font.size = Pt(18)
                p.font.color.rgb = color_scheme["text"]
                p.space_after = Pt(12)
        
        # Speaker Notes
        if slide_data.get("speaker_notes"):
            notes_slide = slide.notes_slide
            notes_slide.notes_text_frame.text = slide_data["speaker_notes"]
        
        # Images
        if idx > 0 and image_mode == "With Images":
            image_data = get_topic_relevant_image(
                topic,
                slide_data["title"],
                google_api_key,
                google_cx,
                use_unsplash
            )
            if image_data:
                try:
                    image_stream = io.BytesIO(image_data)
                    slide.shapes.add_picture(
                        image_stream,
                        Inches(6.5),
                        Inches(2),
                        width=Inches(3)
                    )
                except:
                    pass
        
        time.sleep(0.2)
    
    progress_bar.progress(1.0)
    status_text.text("✅ Presentation created!")
    return prs

# ============================================================================
# LOGIN PAGE
# ============================================================================

def show_login_page():
    """Login page"""
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

# ============================================================================
# PAGE CONFIGURATION
# ============================================================================

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
if 'google_searches_used' not in st.session_state:
    st.session_state.google_searches_used = 0

if not st.session_state.logged_in:
    show_login_page()
    st.stop()

# ============================================================================
# STYLES
# ============================================================================

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

# ============================================================================
# SIDEBAR (Common)
# ============================================================================

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
    
    st.markdown("---")

# ============================================================================
# ADMIN DASHBOARD
# ============================================================================

if st.session_state.user['role'] == 'admin':
    
    st.markdown('<div class="admin-header"><h1>👑 Admin Dashboard</h1><p>Complete System Overview & Management</p></div>', unsafe_allow_html=True)
    
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
    admin_tab1, admin_tab2, admin_tab3, admin_tab4, admin_tab5 = st.tabs([
        "🟢 Live Dashboard",
        "📊 PPT Generator",
        "➕ Create User",
        "👥 Manage Users",
        "📊 Activity Log"
    ])
    
    # TAB 1: LIVE DASHBOARD
    with admin_tab1:
        st.markdown("## 🟢 Live User Activity Dashboard")
        
        if st.button("🔄 Refresh", key="refresh_dash", type="primary"):
            st.rerun()
        
        st.markdown("---")
        st.markdown("### 👥 Currently Logged In Users")
        
        active_users = get_currently_logged_in_users()
        
        if active_users:
            st.success(f"**{len(active_users)} user(s) online**")
            
            for user in active_users:
                user_id, username, email, login_time, role = user
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
                    st.markdown("**Stats:**")
                    st.write(f"📊 {user_activity_stats['total_presentations']} ppts")
                    st.write(f"📄 {user_activity_stats['total_slides']} slides")
                
                with st.expander(f"📜 {username}'s Activities"):
                    activities = get_user_activity_details(user_id)
                    if activities:
                        for activity in activities:
                            action, topic, slides_count, timestamp = activity
                            if action == 'generate_presentation':
                                st.markdown(f"""
<div class='activity-card'>
    <b>📊 Generated Presentation</b><br>
    <small>📌 {topic}</small><br>
    <small>📄 {slides_count} slides</small><br>
    <small>🕒 {timestamp}</small>
</div>
                                """, unsafe_allow_html=True)
                    else:
                        st.info("No activities yet")
                
                st.markdown("---")
        else:
            st.warning("⚠️ No users online")
        
        st.markdown("### 📊 Recent System Activities")
        all_activities = get_all_user_activities()
        
        if all_activities:
            for activity in all_activities[:10]:
                username, action, topic, slides_count, timestamp = activity
                if action == 'generate_presentation':
                    st.markdown(f"""
<div class='activity-card'>
    👤 <b>{username}</b> generated presentation<br>
    <small>📌 {topic} | 📄 {slides_count} slides</small><br>
    <small>🕒 {timestamp}</small>
</div>
                    """, unsafe_allow_html=True)
    
    # TAB 2: PPT GENERATOR (Admin also has access)
    with admin_tab2:
        st.markdown("## 📊 AI PowerPoint Generator")
        st.info("ℹ️ As admin, you can also create presentations")
        
        # API Keys Configuration
        st.markdown("### 🔑 API Configuration")
        
        col_config1, col_config2 = st.columns(2)
        
        with col_config1:
            with st.expander("AI Models", expanded=True):
                model_choice = st.selectbox(
                    "Select Model",
                    [
                        "Free (Google Gemini)",
                        "Free (Meta Llama 3.2)",
                        "Free (Mistral 7B)",
                        "Groq (Llama 3.3) - FREE",
                        "Groq (Mixtral) - FREE",
                        "Claude Sonnet (Paid)"
                    ],
                    key="admin_model"
                )
                
                groq_api_key = None
                if "Groq" in model_choice:
                    groq_api_key = st.text_input("Groq API Key", type="password", help="Get free from https://console.groq.com/", key="admin_groq")
                    if groq_api_key:
                        st.success("✅ Groq configured")
                else:
                    openrouter_key = st.text_input("OpenRouter API Key", type="password", help="For AI models", key="admin_openrouter")
        
        with col_config2:
            with st.expander("Image Settings"):
                google_api_key = st.text_input("Google API Key", type="password", key="admin_google_key")
                google_cx = st.text_input("Google CX ID", key="admin_google_cx")
                use_unsplash = st.checkbox("Use Unsplash", value=True, key="admin_unsplash")
        
        st.markdown("---")
        st.markdown("### 📝 Create Presentation")
        
        col1, col2 = st.columns(2)
        
        with col1:
            topic = st.text_input("📌 Topic", placeholder="e.g., AI in Healthcare", key="admin_topic")
            category = st.selectbox("📂 Category", ["Business", "Technical", "Marketing", "Sales", "Education"], key="admin_category")
            slide_count = st.number_input("📄 Slides", min_value=5, max_value=30, value=10, key="admin_slides")
        
        with col2:
            tone = st.selectbox("🎨 Tone", ["Professional", "Casual", "Formal", "Creative"], key="admin_tone")
            theme = st.selectbox("🎨 Theme", ["Corporate Blue", "Modern Purple", "Dark", "Soft Pastel", "Green"], key="admin_theme")
            image_mode = st.selectbox("🖼️ Images", ["With Images", "No Images"], key="admin_images")
        
        language = st.selectbox("🌍 Language", ["English", "Hindi", "Spanish", "French", "German"], key="admin_language")
        
        key_points = st.text_area("💡 Key Points (Optional)", placeholder="- Point 1\n- Point 2", key="admin_points")
        
        st.markdown("---")
        
        if st.button("🚀 Generate Presentation", type="primary", use_container_width=True, key="admin_generate"):
            if topic:
                # Check API keys
                has_api = False
                if "Groq" in model_choice and groq_api_key:
                    has_api = True
                elif "Groq" not in model_choice and 'openrouter_key' in locals() and openrouter_key:
                    has_api = True
                
                if not has_api:
                    st.error("⚠️ Please enter API key above")
                else:
                    with st.spinner("🤖 Generating content..."):
                        slides_content = generate_content_with_ai(
                            openrouter_key if 'openrouter_key' in locals() else "",
                            topic,
                            category,
                            slide_count,
                            tone,
                            "",
                            key_points,
                            model_choice,
                            language,
                            groq_api_key
                        )
                    
                    if slides_content:
                        log_usage(st.session_state.user['id'], 'generate_presentation', topic, len(slides_content))
                        
                        st.success(f"✅ Generated {len(slides_content)} slides!")
                        
                        with st.spinner("📊 Creating PowerPoint..."):
                            prs = create_powerpoint(
                                slides_content,
                                theme,
                                image_mode,
                                google_api_key if 'google_api_key' in locals() else "",
                                google_cx if 'google_cx' in locals() else "",
                                use_unsplash,
                                topic
                            )
                        
                        pptx_io = io.BytesIO()
                        prs.save(pptx_io)
                        pptx_io.seek(0)
                        
                        st.markdown("---")
                        st.markdown("### 🎉 Presentation Ready!")
                        
                        col_dl1, col_dl2, col_dl3 = st.columns([1, 2, 1])
                        with col_dl2:
                            st.download_button(
                                label="📥 DOWNLOAD POWERPOINT",
                                data=pptx_io.getvalue(),
                                file_name=f"{topic.replace(' ', '_')}.pptx",
                                mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                                use_container_width=True,
                                type="primary",
                                key="admin_download"
                            )
                        
                        st.balloons()
                        
                        # Preview
                        with st.expander("📄 Preview Slides"):
                            for idx, slide in enumerate(slides_content):
                                st.markdown(f"### Slide {idx + 1}: {slide['title']}")
                                if slide.get('bullets'):
                                    for bullet in slide['bullets']:
                                        st.markdown(f"• {bullet}")
                                st.markdown("---")
                    else:
                        st.error("❌ Failed to generate content. Try another model.")
            else:
                st.error("⚠️ Please enter a topic")
    
    # TAB 3: CREATE USER
    with admin_tab3:
        st.markdown("### ➕ Create New User")
        
        with st.form("create_user_form"):
            col_a, col_b = st.columns(2)
            with col_a:
                new_username = st.text_input("Username *", placeholder="john_doe")
                new_email = st.text_input("Email", placeholder="john@company.com")
            with col_b:
                new_password = st.text_input("Password *", type="password", placeholder="Min 6 chars")
                confirm_password = st.text_input("Confirm *", type="password")
            
            submitted = st.form_submit_button("✅ Create User", use_container_width=True, type="primary")
            
            if submitted:
                if new_username and new_password:
                    if new_password == confirm_password:
                        if len(new_password) >= 6:
                            success = create_user_by_admin(new_username, new_password, new_email)
                            if success:
                                st.success(f"""
### ✅ User Created!

**Share credentials:**

📧 Username: `{new_username}`  
🔑 Password: `{new_password}`
                                """)
                            else:
                                st.error("❌ Username exists!")
                        else:
                            st.error("❌ Password min 6 chars")
                    else:
                        st.error("❌ Passwords don't match")
                else:
                    st.warning("⚠️ Fill all fields")
    
    # TAB 4: MANAGE USERS
    with admin_tab4:
        st.markdown("### 👥 All Users")
        
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
            user_id_action = st.number_input("User ID", min_value=1, step=1)
        with col_m2:
            action_type = st.selectbox("Action", ["Enable", "Disable", "Delete"])
        with col_m3:
            st.write("")
            if st.button("▶️ Execute", use_container_width=True, type="primary"):
                if user_id_action == 1:
                    st.error("❌ Can't modify admin!")
                else:
                    if action_type == "Enable":
                        toggle_user_status(user_id_action, 1)
                        st.success(f"✅ User {user_id_action} enabled!")
                        time.sleep(1)
                        st.rerun()
                    elif action_type == "Disable":
                        toggle_user_status(user_id_action, 0)
                        st.warning(f"⚠️ User {user_id_action} disabled!")
                        time.sleep(1)
                        st.rerun()
                    elif action_type == "Delete":
                        delete_user(user_id_action)
                        st.error(f"🗑️ User {user_id_action} deleted!")
                        time.sleep(1)
                        st.rerun()
    
    # TAB 5: ACTIVITY LOG
    with admin_tab5:
        st.markdown("### 📊 Complete Activity Log")
        
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
            
            csv = df_activities.to_csv(index=False)
            st.download_button(
                "📥 Download CSV",
                csv,
                f"activity_{datetime.now().strftime('%Y%m%d')}.csv",
                "text/csv"
            )

# ============================================================================
# USER PANEL (Complete PPT Generator)
# ============================================================================

else:
    
    st.markdown('<div class="main-header"><h1>📊 AI PowerPoint Generator</h1><p>Create Professional Presentations</p></div>', unsafe_allow_html=True)
    
    # API Keys in Sidebar
    with st.sidebar:
        st.markdown("---")
        st.markdown("### 🔑 API Keys")
        
        with st.expander("AI Models", expanded=True):
            model_choice = st.selectbox(
                "Select Model",
                [
                    "Free (Google Gemini)",
                    "Free (Meta Llama 3.2)",
                    "Free (Mistral 7B)",
                    "Groq (Llama 3.3) - FREE",
                    "Groq (Mixtral) - FREE",
                    "Claude Sonnet (Paid)"
                ]
            )
            
            groq_api_key = None
            if "Groq" in model_choice:
                groq_api_key = st.text_input("Groq API Key", type="password", help="Get free from https://console.groq.com/")
                if groq_api_key:
                    st.success("✅ Groq configured")
            else:
                openrouter_key = st.text_input("OpenRouter API Key", type="password", help="For AI models")
        
        with st.expander("Image Settings"):
            google_api_key = st.text_input("Google API Key", type="password")
            google_cx = st.text_input("Google CX ID")
            use_unsplash = st.checkbox("Use Unsplash", value=True)
    
    # Main Content
    st.markdown("## 📝 Create Presentation")
    
    col1, col2 = st.columns(2)
    
    with col1:
        topic = st.text_input("📌 Topic", placeholder="e.g., AI in Healthcare")
        category = st.selectbox("📂 Category", ["Business", "Technical", "Marketing", "Sales", "Education"])
        slide_count = st.number_input("📄 Slides", min_value=5, max_value=30, value=10)
    
    with col2:
        tone = st.selectbox("🎨 Tone", ["Professional", "Casual", "Formal", "Creative"])
        theme = st.selectbox("🎨 Theme", ["Corporate Blue", "Modern Purple", "Dark", "Soft Pastel", "Green"])
        image_mode = st.selectbox("🖼️ Images", ["With Images", "No Images"])
    
    language = st.selectbox("🌍 Language", ["English", "Hindi", "Spanish", "French", "German"])
    
    key_points = st.text_area("💡 Key Points (Optional)", placeholder="- Point 1\n- Point 2")
    
    st.markdown("---")
    
    if st.button("🚀 Generate Presentation", type="primary", use_container_width=True):
        if topic:
            # Check API keys
            has_api = False
            if "Groq" in model_choice and groq_api_key:
                has_api = True
            elif "Groq" not in model_choice and 'openrouter_key' in locals() and openrouter_key:
                has_api = True
            
            if not has_api:
                st.error("⚠️ Please enter API key in sidebar")
            else:
                with st.spinner("🤖 Generating content..."):
                    slides_content = generate_content_with_ai(
                        openrouter_key if 'openrouter_key' in locals() else "",
                        topic,
                        category,
                        slide_count,
                        tone,
                        "",
                        key_points,
                        model_choice,
                        language,
                        groq_api_key
                    )
                
                if slides_content:
                    log_usage(st.session_state.user['id'], 'generate_presentation', topic, len(slides_content))
                    
                    st.success(f"✅ Generated {len(slides_content)} slides!")
                    
                    with st.spinner("📊 Creating PowerPoint..."):
                        prs = create_powerpoint(
                            slides_content,
                            theme,
                            image_mode,
                            google_api_key if 'google_api_key' in locals() else "",
                            google_cx if 'google_cx' in locals() else "",
                            use_unsplash,
                            topic
                        )
                    
                    pptx_io = io.BytesIO()
                    prs.save(pptx_io)
                    pptx_io.seek(0)
                    
                    st.markdown("---")
                    st.markdown("### 🎉 Presentation Ready!")
                    
                    col_dl1, col_dl2, col_dl3 = st.columns([1, 2, 1])
                    with col_dl2:
                        st.download_button(
                            label="📥 DOWNLOAD POWERPOINT",
                            data=pptx_io.getvalue(),
                            file_name=f"{topic.replace(' ', '_')}.pptx",
                            mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                            use_container_width=True,
                            type="primary"
                        )
                    
                    st.balloons()
                    
                    # Preview
                    with st.expander("📄 Preview Slides"):
                        for idx, slide in enumerate(slides_content):
                            st.markdown(f"### Slide {idx + 1}: {slide['title']}")
                            if slide.get('bullets'):
                                for bullet in slide['bullets']:
                                    st.markdown(f"• {bullet}")
                            st.markdown("---")
                else:
                    st.error("❌ Failed to generate content. Try another model.")
        else:
            st.error("⚠️ Please enter a topic")
    
    st.markdown("---")
    
    # User's Activity
    st.markdown("### 📊 Your Recent Activities")
    
    my_activities = get_user_activity_details(st.session_state.user['id'])
    
    if my_activities:
        for activity in my_activities[:10]:
            action, topic, slides_count, timestamp = activity
            if action == 'generate_presentation':
                st.markdown(f"""
<div class='activity-card'>
    <b>📊 Generated Presentation</b><br>
    <small>📌 {topic}</small><br>
    <small>📄 {slides_count} slides</small><br>
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
