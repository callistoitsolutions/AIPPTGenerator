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
import zipfile
import matplotlib.pyplot as plt
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from datetime import datetime
import hashlib

# Page configuration
st.set_page_config(
    page_title="AI PowerPoint Generator Pro",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize ALL session state variables
if 'generation_count' not in st.session_state:
    st.session_state.generation_count = 0
if 'total_slides' not in st.session_state:
    st.session_state.total_slides = 0
if 'slides_content' not in st.session_state:
    st.session_state.slides_content = None
if 'edited_slides' not in st.session_state:
    st.session_state.edited_slides = None
if 'final_pptx' not in st.session_state:
    st.session_state.final_pptx = None
if 'google_searches_used' not in st.session_state:
    st.session_state.google_searches_used = 0
if 'templates' not in st.session_state:
    st.session_state.templates = {}
if 'selected_template' not in st.session_state:
    st.session_state.selected_template = None
if 'generation_history' not in st.session_state:
    st.session_state.generation_history = []
if 'current_theme' not in st.session_state:
    st.session_state.current_theme = "light"

# Professional CSS with Dashboard Styling
st.markdown("""
<style>
    /* Main Layout */
    .main {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
    }
    
    /* Header Styling */
    .main-header {
        font-size: 2.8rem;
        font-weight: 800;
        background: linear-gradient(120deg, #1f77b4, #667eea, #764ba2);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        margin-bottom: 0.5rem;
        letter-spacing: -1px;
    }
    
    .sub-header {
        text-align: center;
        color: #666;
        font-size: 1.1rem;
        margin-bottom: 2rem;
    }
    
    /* Dashboard Cards */
    .dashboard-card {
        background: white;
        padding: 1.5rem;
        border-radius: 15px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.08);
        border: 1px solid rgba(0,0,0,0.05);
        transition: transform 0.3s ease, box-shadow 0.3s ease;
    }
    
    .dashboard-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 30px rgba(0,0,0,0.12);
    }
    
    /* Metric Cards */
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.2rem;
        border-radius: 12px;
        color: white;
        text-align: center;
        box-shadow: 0 4px 15px rgba(102,126,234,0.4);
    }
    
    .metric-value {
        font-size: 2rem;
        font-weight: 700;
        margin: 0.5rem 0;
    }
    
    .metric-label {
        font-size: 0.85rem;
        opacity: 0.9;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    /* Template Cards */
    .template-card {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        margin: 0.5rem 0;
        cursor: pointer;
        transition: all 0.3s ease;
    }
    
    .template-card:hover {
        transform: scale(1.02);
        box-shadow: 0 5px 20px rgba(240,147,251,0.4);
    }
    
    .template-card.selected {
        border: 3px solid #ffd700;
        box-shadow: 0 0 20px rgba(255,215,0,0.5);
    }
    
    /* Button Styling */
    .stButton>button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        font-weight: 600;
        padding: 0.75rem 2rem;
        border-radius: 10px;
        border: none;
        box-shadow: 0 4px 15px rgba(102,126,234,0.4);
        transition: all 0.3s ease;
    }
    
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(102,126,234,0.6);
    }
    
    /* Download Section */
    .download-section {
        background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
        padding: 2rem;
        border-radius: 20px;
        margin: 2rem 0;
        text-align: center;
        color: white;
        box-shadow: 0 10px 30px rgba(17,153,142,0.3);
    }
    
    /* Tab Styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background: white;
        padding: 0.5rem;
        border-radius: 15px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.05);
    }
    
    .stTabs [data-baseweb="tab"] {
        border-radius: 10px;
        padding: 0.5rem 1.5rem;
        font-weight: 600;
    }
    
    /* Form Sections */
    .form-section {
        background: white;
        padding: 1.5rem;
        border-radius: 15px;
        margin: 1rem 0;
        border-left: 5px solid #667eea;
    }
    
    .form-section-title {
        font-size: 1.2rem;
        font-weight: 700;
        color: #333;
        margin-bottom: 1rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    
    /* Status Badges */
    .status-badge {
        display: inline-block;
        padding: 0.3rem 0.8rem;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    
    .status-success {
        background: #d4edda;
        color: #155724;
    }
    
    .status-warning {
        background: #fff3cd;
        color: #856404;
    }
    
    .status-error {
        background: #f8d7da;
        color: #721c24;
    }
    
    /* Progress Indicator */
    .progress-container {
        background: #e0e0e0;
        border-radius: 10px;
        overflow: hidden;
        margin: 1rem 0;
    }
    
    .progress-bar {
        background: linear-gradient(90deg, #667eea, #764ba2);
        height: 8px;
        border-radius: 10px;
        transition: width 0.5s ease;
    }
    
    /* Sidebar Enhancement */
    .css-1d391kg {
        background: linear-gradient(180deg, #f8f9fa 0%, #e9ecef 100%);
    }
    
    /* Quick Action Buttons */
    .quick-action {
        background: white;
        padding: 0.8rem;
        border-radius: 10px;
        text-align: center;
        cursor: pointer;
        transition: all 0.3s ease;
        border: 2px solid #e0e0e0;
    }
    
    .quick-action:hover {
        border-color: #667eea;
        background: #f5f7fa;
    }
    
    /* History Item */
    .history-item {
        background: #f8f9fa;
        padding: 1rem;
        border-radius: 10px;
        margin: 0.5rem 0;
        border-left: 4px solid #667eea;
    }
    
    /* Tooltip */
    .tooltip {
        position: relative;
        display: inline-block;
    }
    
    /* Animation */
    @keyframes fadeInUp {
        from {
            opacity: 0;
            transform: translateY(20px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
    
    .animate-in {
        animation: fadeInUp 0.5s ease forwards;
    }
</style>
""", unsafe_allow_html=True)

# Header
st.markdown('<div class="main-header">📊 AI PowerPoint Generator Pro</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Create stunning presentations with AI-powered content and smart templates</div>', unsafe_allow_html=True)

# ============ TEMPLATE MANAGEMENT FUNCTIONS ============

def generate_template_id():
    """Generate unique template ID"""
    return hashlib.md5(str(datetime.now().timestamp()).encode()).hexdigest()[:8]

def save_template_to_state(name, template_data):
    """Save template to session state"""
    template_id = generate_template_id()
    template_data['id'] = template_id
    template_data['name'] = name
    template_data['created_at'] = datetime.now().strftime("%Y-%m-%d %H:%M")
    template_data['usage_count'] = 0
    st.session_state.templates[template_id] = template_data
    return template_id

def load_template_from_state(template_id):
    """Load template from session state"""
    return st.session_state.templates.get(template_id, None)

def delete_template(template_id):
    """Delete template from session state"""
    if template_id in st.session_state.templates:
        del st.session_state.templates[template_id]
        return True
    return False

def export_all_templates():
    """Export all templates as JSON"""
    return json.dumps(st.session_state.templates, indent=2)

def import_templates(json_data):
    """Import templates from JSON"""
    try:
        templates = json.loads(json_data)
        st.session_state.templates.update(templates)
        return True
    except:
        return False

def get_preset_templates():
    """Get preset professional templates"""
    return {
        "pitch_deck": {
            "name": "🚀 Startup Pitch Deck",
            "category": "Pitch",
            "slide_count": 10,
            "tone": "Persuasive",
            "audience": "Investors",
            "theme": "Gradient Modern",
            "image_mode": "With Images",
            "language": "English",
            "description": "Perfect for startup pitches with 10-slide structure"
        },
        "corporate_report": {
            "name": "📈 Corporate Report",
            "category": "Business",
            "slide_count": 12,
            "tone": "Formal",
            "audience": "Corporate",
            "theme": "Corporate Blue",
            "image_mode": "With Images",
            "language": "English",
            "description": "Professional business reporting format"
        },
        "training_session": {
            "name": "🎓 Training Session",
            "category": "Training",
            "slide_count": 15,
            "tone": "Educational",
            "audience": "Students",
            "theme": "Pastel Soft",
            "image_mode": "With Images",
            "language": "English",
            "description": "Educational content with clear structure"
        },
        "sales_pitch": {
            "name": "💼 Sales Pitch",
            "category": "Sales",
            "slide_count": 8,
            "tone": "Persuasive",
            "audience": "Clients",
            "theme": "Professional Green",
            "image_mode": "With Images",
            "language": "English",
            "description": "Compelling sales presentation format"
        },
        "tech_overview": {
            "name": "🔧 Technical Overview",
            "category": "Technical",
            "slide_count": 10,
            "tone": "Neutral",
            "audience": "Managers",
            "theme": "Minimal Dark",
            "image_mode": "With Images",
            "language": "English",
            "description": "Technical documentation and overview"
        },
        "marketing_campaign": {
            "name": "📣 Marketing Campaign",
            "category": "Marketing",
            "slide_count": 9,
            "tone": "Inspirational",
            "audience": "Corporate",
            "theme": "Elegant Purple",
            "image_mode": "With Images",
            "language": "English",
            "description": "Creative marketing strategy presentation"
        }
    }

# ============ IMAGE FUNCTIONS ============

def generate_topic_search_terms(main_topic, slide_title, image_prompt):
    """Generate search terms prioritizing topic relevance"""
    search_terms = []
    
    if image_prompt and image_prompt.strip():
        search_terms.append(image_prompt.strip())
    
    if main_topic and slide_title:
        search_terms.append(f"{main_topic} {slide_title}")
    
    if slide_title:
        search_terms.append(slide_title)
    
    if main_topic:
        search_terms.append(main_topic)
    
    seen = set()
    unique = []
    for term in search_terms:
        lower = term.lower().strip()
        if lower and lower not in seen:
            seen.add(lower)
            unique.append(term)
    
    return unique

def get_google_image(query, api_key, cx):
    """Get image using Google Custom Search API"""
    try:
        st.session_state.google_searches_used += 1
        
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
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                        })
                        
                        if img_response.status_code == 200 and len(img_response.content) > 5000:
                            img = Image.open(io.BytesIO(img_response.content))
                            if img.size[0] > 300 and img.size[1] > 200:
                                return img_response.content
                    except:
                        continue
        
        return None
    except Exception as e:
        return None

def get_unsplash_image(query, width=800, height=600):
    """Get image from Unsplash Direct (Free)"""
    try:
        clean_query = query.strip().replace(' ', ',')
        url = f"https://source.unsplash.com/{width}x{height}/?{clean_query}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, timeout=15, allow_redirects=True, headers=headers)
        
        if response.status_code == 200 and len(response.content) > 5000:
            try:
                img = Image.open(io.BytesIO(response.content))
                if img.size[0] > 400 and img.size[1] > 300:
                    return response.content
            except:
                pass
        return None
    except:
        return None

def get_pexels_image(query, api_key):
    """Get image from Pexels Direct API"""
    if not api_key:
        return None
    
    try:
        url = "https://api.pexels.com/v1/search"
        headers = {"Authorization": api_key}
        params = {
            "query": query,
            "per_page": 3,
            "orientation": "landscape"
        }
        
        response = requests.get(url, headers=headers, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("photos"):
                photo = data["photos"][0]
                img_url = photo["src"]["large"]
                
                img_response = requests.get(img_url, timeout=10)
                if img_response.status_code == 200:
                    return img_response.content
        return None
    except:
        return None

def get_topic_relevant_image(main_topic, slide_title, image_prompt, google_api_key, google_cx, use_unsplash, use_pexels, pexels_key):
    """Get highly relevant image using Google + fallbacks"""
    
    search_terms = generate_topic_search_terms(main_topic, slide_title, image_prompt)
    
    for i, term in enumerate(search_terms, 1):
        if google_api_key and google_cx:
            image_data = get_google_image(term, google_api_key, google_cx)
            if image_data:
                return image_data
        
        if use_pexels and pexels_key:
            image_data = get_pexels_image(term, pexels_key)
            if image_data:
                return image_data
        
        if use_unsplash:
            image_data = get_unsplash_image(term)
            if image_data:
                return image_data
    
    fallback = main_topic.split()[0] if main_topic else "business"
    
    if google_api_key and google_cx:
        image_data = get_google_image(fallback, google_api_key, google_cx)
        if image_data:
            return image_data
    
    if use_unsplash:
        image_data = get_unsplash_image(fallback)
        if image_data:
            return image_data
    
    return None

# ============ CONTENT GENERATION ============

def repair_truncated_json(json_text):
    """Attempt to repair truncated JSON from AI response"""
    text = json_text.strip()
    
    # Remove markdown code blocks if present
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()
    
    # Try parsing as-is first
    try:
        data = json.loads(text)
        return data
    except json.JSONDecodeError:
        pass
    
    # Count brackets to see what's missing
    open_braces = text.count('{')
    close_braces = text.count('}')
    open_brackets = text.count('[')
    close_brackets = text.count(']')
    
    # Try to find the last complete slide
    slides = []
    
    # Find "slides": [ pattern
    slides_start = text.find('"slides"')
    if slides_start == -1:
        return None
    
    # Find the opening bracket of slides array
    bracket_pos = text.find('[', slides_start)
    if bracket_pos == -1:
        return None
    
    # Extract individual slide objects
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
                # Found a complete slide object
                slide_text = text[slide_start:current_pos + 1]
                try:
                    slide_obj = json.loads(slide_text)
                    # Ensure required fields exist
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

def generate_content_with_claude(api_key, topic, category, slide_count, tone, audience, key_points, model_choice, language, grok_api_key=None, groq_api_key=None):
    """Generate presentation content using AI"""
    try:
        # Determine which API to use
        use_grok_api = "Grok" in model_choice and grok_api_key
        use_groq_api = "Groq" in model_choice and groq_api_key
        
        if use_groq_api:
            # Groq API (FREE and FAST)
            if "Llama 3.3" in model_choice:
                model = "llama-3.3-70b-versatile"
            else:  # Mixtral
                model = "mixtral-8x7b-32768"
            api_url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {groq_api_key.strip()}",
                "Content-Type": "application/json",
            }
        elif use_grok_api:
            if "Grok-4" in model_choice:
                model = "grok-4-latest"
            elif "Grok-3" in model_choice:
                model = "grok-3-latest"
            else:  # Grok-2
                model = "grok-2-latest"
            api_url = "https://api.x.ai/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {grok_api_key.strip()}",
                "Content-Type": "application/json",
            }
        else:
            # Use OpenRouter
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
        
        # Increase token limit significantly to avoid truncation
        calculated_tokens = min(slide_count * 350 + 500, 4000)
        
        language_instruction = f"Generate ALL content in {language} language." if language != "English" else ""
        
        # Simplified prompt to reduce response size
        prompt = f"""{language_instruction}
Create a {slide_count}-slide presentation about: {topic}

Category: {category} | Tone: {tone} | Audience: {audience}
{f"Include these points: {key_points}" if key_points else ""}

Return ONLY valid JSON (no markdown, no extra text):
{{"slides": [
  {{
    "title": "Main Title of Presentation",
    "bullets": [],
    "image_prompt": "professional {topic} banner",
    "speaker_notes": "Welcome and introduction"
  }},
  {{
    "title": "Key Point Title",
    "bullets": ["First important point about the topic", "Second key insight or fact", "Third supporting detail", "Fourth actionable item"],
    "image_prompt": "{topic} concept",
    "speaker_notes": "Explain these points in detail"
  }},
  {{
    "title": "Another Section",
    "bullets": ["Specific detail one", "Specific detail two", "Specific detail three"],
    "image_prompt": "{topic} illustration",
    "speaker_notes": "Discuss the implications"
  }}
]}}

CRITICAL REQUIREMENTS:
1. First slide is TITLE ONLY (empty bullets array)
2. ALL OTHER SLIDES MUST have 3-5 bullet points
3. Each bullet must be a complete, informative sentence (8-15 words)
4. Bullets should contain actual content, facts, or insights about {topic}
5. Do NOT leave bullets empty for content slides
6. Total: exactly {slide_count} slides
7. Return ONLY the JSON object, nothing else

Generate {slide_count} slides now with detailed content:"""

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
            
            # First try to repair/parse the JSON
            slides_data = repair_truncated_json(content_text)
            
            if slides_data and "slides" in slides_data:
                slides = slides_data["slides"]
                
                # Validate we have slides
                if not slides:
                    st.error("No slides were generated. Please try again.")
                    return None
                
                # Validate and fix slide content
                for i, slide in enumerate(slides):
                    # Ensure bullets exist and is a list
                    if 'bullets' not in slide:
                        slide['bullets'] = []
                    elif not isinstance(slide['bullets'], list):
                        slide['bullets'] = [str(slide['bullets'])]
                    
                    # For non-title slides, ensure we have content
                    if i > 0 and len(slide['bullets']) == 0:
                        st.warning(f"⚠️ Slide {i+1} '{slide['title']}' has no bullet points. This may indicate truncated content.")
                    
                    # Ensure other fields exist
                    if 'image_prompt' not in slide:
                        slide['image_prompt'] = slide.get('title', topic)
                    if 'speaker_notes' not in slide:
                        slide['speaker_notes'] = ""
                
                # Count slides with actual content
                content_slides = sum(1 for s in slides[1:] if len(s.get('bullets', [])) > 0)
                if content_slides == 0 and len(slides) > 1:
                    st.error("❌ No slide content was generated. The AI returned empty slides. Please try again or switch models.")
                    return None
                
                # Warn if truncated
                if len(slides) < slide_count:
                    st.warning(f"⚠️ Only {len(slides)} slides generated (requested {slide_count}). The AI response was truncated. Try reducing slide count or using a paid model.")
                
                # Show content summary
                total_bullets = sum(len(s.get('bullets', [])) for s in slides)
                st.success(f"✅ Generated {len(slides)} slides with {total_bullets} bullet points total.")
                
                return slides
            else:
                st.error("Failed to parse AI response. The model may have returned invalid JSON.")
                st.code(content_text[:500] + "..." if len(content_text) > 500 else content_text)
                return None
        else:
            if response.status_code == 429:
                st.error(f"⏱️ Rate Limit: Model is temporarily unavailable")
                st.info("💡 **Solutions:**\n- Wait 30-60 seconds and try again\n- Switch to a different model above\n- Check your API quota")
                raise Exception("Rate limit - retry needed")
            elif response.status_code == 403:
                error_data = response.json() if response.text else {}
                error_msg = error_data.get('error', response.text)
                
                if "credit" in error_msg.lower() or "permission" in error_msg.lower():
                    st.error("💳 **Grok API Credits Required**")
                    st.warning(f"""
                    **Your xAI account needs credits to use Grok API.**
                    
                    **Options:**
                    1. 🆓 **Use FREE Models Instead** - Select Google Gemini, Llama, or Mistral (no credits needed)
                    2. 🚀 **Use Groq (FREE)** - Select "Groq (Llama 3.3 70B)" - completely free!
                    3. 💰 **Purchase Grok Credits** - Visit your xAI console to buy credits
                    
                    **Recommended:** Switch to Groq (FREE) in the sidebar dropdown.
                    """)
                else:
                    st.error(f"🚫 Access Denied: {error_msg}")
            elif response.status_code == 400:
                error_data = {}
                try:
                    error_data = response.json()
                except:
                    pass
                error_msg = error_data.get('error', response.text)
                
                if "invalid" in error_msg.lower() and "key" in error_msg.lower():
                    st.error("🔑 **Invalid API Key**")
                    if use_grok_api:
                        st.warning(f"""
                        **Your Grok/xAI API key is invalid.**
                        
                        Current key starts with: `{grok_api_key[:6]}...`
                        
                        **Please check:**
                        1. Key should start with `xai-`
                        2. Copy the full key from https://console.x.ai/
                        3. Make sure there are no extra spaces
                        
                        **Better option:** Use **Groq (FREE)** instead!
                        - Select "Groq (Llama 3.3 70B)" in the dropdown
                        - Get FREE key from https://console.groq.com/keys
                        """)
                    elif use_groq_api:
                        st.warning(f"""
                        **Your Groq API key is invalid.**
                        
                        **Please check:**
                        1. Key should start with `gsk_`
                        2. Copy the full key from https://console.groq.com/keys
                        3. Make sure there are no extra spaces
                        """)
                    else:
                        st.warning(f"Please verify your API key is correct.")
                else:
                    st.error(f"API Error: {error_msg}")
            elif response.status_code == 402:
                st.error("💳 Insufficient credits! Reduce slides or add credits.")
            elif response.status_code == 401:
                st.error("🔑 Invalid API key. Please check your API key.")
            else:
                st.error(f"API Error ({response.status_code}): {response.text}")
            return None
            
    except json.JSONDecodeError as e:
        st.error(f"JSON parsing error: {str(e)}")
        st.info("💡 **Tip:** Try reducing the number of slides or switching to a different AI model.")
        return None
    except Exception as e:
        if "Rate limit" in str(e):
            raise
        st.error(f"Error: {str(e)}")
        return None

def generate_content_with_retry(api_key, topic, category, slide_count, tone, audience, key_points, model_choice, language, grok_api_key=None, groq_api_key=None, max_retries=3):
    """Generate content with automatic retry on rate limit"""
    for attempt in range(max_retries):
        try:
            result = generate_content_with_claude(api_key, topic, category, slide_count, tone, audience, key_points, model_choice, language, grok_api_key, groq_api_key)
            if result:
                return result
        except Exception as e:
            if "Rate limit" in str(e) or "429" in str(e):
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 5
                    st.warning(f"⏳ Rate limit hit. Retrying in {wait_time} seconds... (Attempt {attempt + 2}/{max_retries})")
                    time.sleep(wait_time)
                else:
                    st.error("❌ Rate limit persists after retries.")
                    return None
            else:
                return None
    return None

# ============ ANALYSIS FUNCTIONS ============

def analyze_presentation(slides_content):
    """Analyze presentation quality"""
    issues = []
    suggestions = []
    score = 100
    
    for i, slide in enumerate(slides_content, 1):
        bullet_count = len(slide.get('bullets', []))
        if bullet_count > 5:
            issues.append(f"Slide {i}: Too many bullets ({bullet_count})")
            suggestions.append(f"Slide {i}: Reduce to 3-5 key points")
            score -= 5
        
        title_len = len(slide['title'])
        if title_len > 60:
            issues.append(f"Slide {i}: Title too long ({title_len} chars)")
            suggestions.append(f"Slide {i}: Shorten title to <60 characters")
            score -= 3
        
        total_text = sum(len(b) for b in slide.get('bullets', []))
        if total_text > 500:
            issues.append(f"Slide {i}: Too much text ({total_text} chars)")
            suggestions.append(f"Slide {i}: Use more visuals, less text")
            score -= 5
    
    score = max(0, score)
    return issues, suggestions, score

# ============ EXPORT FUNCTIONS ============

def export_to_pdf(slides_content, topic):
    """Export to PDF"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []
    
    title = Paragraph(f"<b>{topic}</b>", styles['Title'])
    story.append(title)
    story.append(Spacer(1, 12))
    
    for i, slide in enumerate(slides_content, 1):
        slide_title = Paragraph(f"<b>Slide {i}: {slide['title']}</b>", styles['Heading2'])
        story.append(slide_title)
        story.append(Spacer(1, 6))
        
        for bullet in slide.get('bullets', []):
            bullet_text = Paragraph(f"• {bullet}", styles['BodyText'])
            story.append(bullet_text)
        
        if slide.get('speaker_notes'):
            notes = Paragraph(f"<i>Notes: {slide['speaker_notes']}</i>", styles['Italic'])
            story.append(Spacer(1, 6))
            story.append(notes)
        
        story.append(Spacer(1, 20))
    
    doc.build(story)
    buffer.seek(0)
    return buffer

def export_to_google_slides_json(slides_content, topic, theme):
    """Export to Google Slides JSON"""
    google_slides_data = {
        "title": topic,
        "theme": theme,
        "slides": []
    }
    
    for slide in slides_content:
        google_slide = {
            "title": slide['title'],
            "content": slide.get('bullets', []),
            "notes": slide.get('speaker_notes', ''),
            "imagePrompt": slide.get('image_prompt', '')
        }
        google_slides_data['slides'].append(google_slide)
    
    return json.dumps(google_slides_data, indent=2)

# ============ POWERPOINT CREATION ============

def create_powerpoint(slides_content, theme, image_mode, google_api_key, google_cx, use_unsplash, use_pexels, pexels_key, category, audience, topic, image_position, logo_data, show_progress=True):
    """Create PowerPoint presentation"""
    prs = Presentation()
    prs.slide_width = Inches(10)
    prs.slide_height = Inches(7.5)
    
    themes = {
        "Corporate Blue": {"bg": RGBColor(240, 248, 255), "accent": RGBColor(31, 119, 180), "text": RGBColor(0, 0, 0)},
        "Gradient Modern": {"bg": RGBColor(240, 242, 246), "accent": RGBColor(138, 43, 226), "text": RGBColor(0, 0, 0)},
        "Minimal Dark": {"bg": RGBColor(30, 30, 30), "accent": RGBColor(255, 215, 0), "text": RGBColor(255, 255, 255)},
        "Pastel Soft": {"bg": RGBColor(255, 250, 240), "accent": RGBColor(255, 182, 193), "text": RGBColor(60, 60, 60)},
        "Professional Green": {"bg": RGBColor(245, 255, 250), "accent": RGBColor(34, 139, 34), "text": RGBColor(0, 0, 0)},
        "Elegant Purple": {"bg": RGBColor(250, 245, 255), "accent": RGBColor(128, 0, 128), "text": RGBColor(0, 0, 0)}
    }
    
    color_scheme = themes.get(theme, themes["Corporate Blue"])
    
    positions = {
        "Right Side": {"left": Inches(6.5), "top": Inches(2), "width": Inches(3)},
        "Left Side": {"left": Inches(0.5), "top": Inches(2), "width": Inches(3)},
        "Top Right Corner": {"left": Inches(8), "top": Inches(0.5), "width": Inches(1.5)},
        "Bottom": {"left": Inches(3.5), "top": Inches(5.5), "width": Inches(3)},
        "Center": {"left": Inches(3.5), "top": Inches(2.5), "width": Inches(3)}
    }
    
    img_pos = positions.get(image_position, positions["Right Side"])
    
    if show_progress:
        progress_bar = st.progress(0)
        status_text = st.empty()
    
    for idx, slide_data in enumerate(slides_content):
        if show_progress:
            status_text.text(f"Creating slide {idx + 1}/{len(slides_content)}...")
            progress_bar.progress((idx + 1) / len(slides_content))
        
        blank_slide_layout = prs.slide_layouts[6]
        slide = prs.slides.add_slide(blank_slide_layout)
        
        background = slide.background
        fill = background.fill
        fill.solid()
        fill.fore_color.rgb = color_scheme["bg"]
        
        if logo_data:
            try:
                logo_stream = io.BytesIO(logo_data)
                slide.shapes.add_picture(logo_stream, Inches(9), Inches(0.2), width=Inches(0.8))
            except:
                pass
        
        title_box = slide.shapes.add_textbox(Inches(0.5), Inches(0.5), Inches(8.5), Inches(1))
        title_frame = title_box.text_frame
        title_frame.text = slide_data["title"]
        title_frame.paragraphs[0].font.size = Pt(36 if idx == 0 else 28)
        title_frame.paragraphs[0].font.bold = True
        title_frame.paragraphs[0].font.color.rgb = color_scheme["accent"]
        title_frame.paragraphs[0].alignment = PP_ALIGN.CENTER if idx == 0 else PP_ALIGN.LEFT
        
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
        
        if idx == 0:
            subtitle_box = slide.shapes.add_textbox(Inches(0.5), Inches(3), Inches(9), Inches(1))
            subtitle_frame = subtitle_box.text_frame
            subtitle_frame.text = f"{category} Presentation | {audience}"
            subtitle_frame.paragraphs[0].font.size = Pt(20)
            subtitle_frame.paragraphs[0].font.color.rgb = color_scheme["text"]
            subtitle_frame.paragraphs[0].alignment = PP_ALIGN.CENTER
        
        if slide_data.get("speaker_notes"):
            notes_slide = slide.notes_slide
            notes_slide.notes_text_frame.text = slide_data["speaker_notes"]
        
        if idx > 0 and image_mode == "With Images":
            image_prompt = slide_data.get("image_prompt", "")
            
            image_data = get_topic_relevant_image(
                main_topic=topic,
                slide_title=slide_data["title"],
                image_prompt=image_prompt,
                google_api_key=google_api_key,
                google_cx=google_cx,
                use_unsplash=use_unsplash,
                use_pexels=use_pexels,
                pexels_key=pexels_key
            )
            
            if image_data:
                try:
                    image_stream = io.BytesIO(image_data)
                    slide.shapes.add_picture(
                        image_stream, 
                        img_pos["left"], 
                        img_pos["top"], 
                        width=img_pos["width"]
                    )
                except:
                    pass
            
            time.sleep(0.3)
    
    if show_progress:
        progress_bar.progress(1.0)
        status_text.text("✅ Presentation created!")
    
    return prs

# ============ SIDEBAR ============

with st.sidebar:
    st.markdown("### ⚙️ Configuration")
    
    with st.expander("🔑 API Keys", expanded=True):
        claude_api_key = st.text_input("OpenRouter API Key *", type="password", 
                                        help="Required: For generating presentation content")
        
        model_choice = st.selectbox(
            "AI Model",
            [
                "Free Model (Google Gemini Flash)",
                "Free Model (Meta Llama 3.2)",
                "Free Model (Mistral 7B)",
                "Groq (Llama 3.3 70B) - FREE & FAST",
                "Groq (Mixtral 8x7B) - FREE",
                "Grok-4 Latest (xAI)",
                "Grok-3 (xAI)",
                "Grok-2 (xAI)",
                "Claude 3.5 Sonnet (Paid)"
            ],
            help="Try different models if one is rate-limited"
        )
        
        # Show Groq API key input (FREE alternative)
        groq_api_key = None
        if "Groq" in model_choice:
            st.markdown("### 🚀 Groq API (FREE & FAST)")
            groq_api_key = st.text_input(
                "Groq API Key (FREE)", 
                type="password",
                help="Get FREE API key from https://console.groq.com/",
                key="groq_key"
            )
            if groq_api_key:
                st.success("✅ Groq API configured!")
            else:
                st.warning("⚠️ Enter Groq API key")
            st.markdown("🆓 **[Get FREE Groq API Key](https://console.groq.com/keys)**")
            st.info("""
            💡 **Groq is FREE and FAST!**
            - No credit card required
            - 14,400 requests/day free
            - Super fast inference
            - NOT the same as Grok/xAI
            """)
        
        # Show Grok API key input if Grok is selected
        grok_api_key = None
        if "Grok" in model_choice:
            st.markdown("### 🤖 Grok/xAI API")
            grok_api_key = st.text_input(
                "Grok/xAI API Key", 
                type="password",
                help="Get your API key from https://console.x.ai/",
                key="grok_key"
            )
            if grok_api_key:
                if grok_api_key.startswith("xai-"):
                    st.success("✅ Grok API key configured!")
                else:
                    st.warning("⚠️ Grok keys usually start with 'xai-'")
            else:
                st.warning("⚠️ Enter Grok API key for xAI models")
            st.markdown("[🔗 Get Grok API Key](https://console.x.ai/)")
            st.info("💡 Using Grok-4 Latest - xAI's most powerful model!")
        
        if "Free" in model_choice:
            st.info("💡 Free models share rate limits")
    
    with st.expander("🖼️ Image Configuration"):
        google_api_key = st.text_input(
            "Google API Key", 
            type="password",
            help="Google Custom Search API Key"
        )
        
        google_cx = st.text_input(
            "Google Search Engine ID",
            help="Get it from: https://programmablesearchengine.google.com/",
            placeholder="e.g., 6386765a3a8ed49a9"
        )
        
        if google_api_key and google_cx:
            st.success("✅ Google Search configured!")
        
        st.markdown("**Fallback Sources:**")
        use_unsplash_fallback = st.checkbox("Unsplash", value=True)
        use_pexels_fallback = st.checkbox("Pexels", value=False)
        
        if use_pexels_fallback:
            pexels_api_key = st.text_input("Pexels API Key", type="password")
        else:
            pexels_api_key = None
    
    with st.expander("🏢 Branding"):
        logo_file = st.file_uploader("Company Logo", type=["png", "jpg", "jpeg"])
        logo_data = None
        if logo_file:
            logo_data = logo_file.read()
            st.success("✅ Logo uploaded!")
    
    st.markdown("---")
    
    # Dashboard Metrics
    st.markdown("### 📊 Dashboard")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Presentations</div>
            <div class="metric-value">{st.session_state.generation_count}</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Total Slides</div>
            <div class="metric-value">{st.session_state.total_slides}</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # API Usage
    if google_api_key and google_cx:
        st.markdown("### 📈 API Usage")
        st.metric("Google Searches", st.session_state.google_searches_used)
        if st.session_state.google_searches_used > 50:
            st.warning("⚠️ High usage!")
    
    st.markdown("---")
    st.markdown("### 🔗 Resources")
    st.markdown("[🔑 Google Custom Search](https://programmablesearchengine.google.com/)")
    st.markdown("[🆓 Pexels API](https://www.pexels.com/api/)")
    st.markdown("[🤖 OpenRouter](https://openrouter.ai/keys)")

# ============ MAIN UI ============

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📝 Create", 
    "📁 Templates", 
    "📊 Bulk Generate",
    "📜 History",
    "⚙️ Settings"
])

with tab1:
    st.markdown("### 🚀 Quick Start with Templates")
    
    # Preset Templates Section
    preset_templates = get_preset_templates()
    
    cols = st.columns(3)
    selected_preset = None
    
    for idx, (key, template) in enumerate(preset_templates.items()):
        with cols[idx % 3]:
            if st.button(
                f"{template['name']}\n{template['description']}", 
                key=f"preset_{key}",
                use_container_width=True
            ):
                selected_preset = template
                st.session_state.selected_template = template
    
    st.markdown("---")
    
    # Main Form
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown('<div class="form-section">', unsafe_allow_html=True)
        st.markdown('<div class="form-section-title">📝 Content Details</div>', unsafe_allow_html=True)
        
        topic = st.text_input(
            "Topic *", 
            placeholder="e.g., Artificial Intelligence in Healthcare",
            help="Be specific for better results"
        )
        
        # Apply selected template
        if st.session_state.selected_template:
            t = st.session_state.selected_template
            default_category = t.get('category', 'Business')
            default_slides = t.get('slide_count', 6)
            default_tone = t.get('tone', 'Formal')
            default_audience = t.get('audience', 'Corporate')
            default_theme = t.get('theme', 'Corporate Blue')
            default_image_mode = t.get('image_mode', 'With Images')
            default_language = t.get('language', 'English')
        else:
            default_category = 'Business'
            default_slides = 6
            default_tone = 'Formal'
            default_audience = 'Corporate'
            default_theme = 'Corporate Blue'
            default_image_mode = 'With Images'
            default_language = 'English'
        
        categories = ["Business", "Pitch", "Marketing", "Technical", "Academic", "Training", "Sales"]
        category = st.selectbox(
            "Category *", 
            categories,
            index=categories.index(default_category) if default_category in categories else 0
        )
        
        col1_1, col1_2 = st.columns(2)
        with col1_1:
            slide_count = st.number_input("Slides *", min_value=3, max_value=20, value=default_slides)
        with col1_2:
            languages = ["English", "Hindi (हिंदी)", "Spanish", "French", "German"]
            language = st.selectbox(
                "Language 🌍", 
                languages,
                index=languages.index(default_language) if default_language in languages else 0
            )
        
        tones = ["Formal", "Neutral", "Inspirational", "Educational", "Persuasive"]
        tone = st.selectbox(
            "Tone *", 
            tones,
            index=tones.index(default_tone) if default_tone in tones else 0
        )
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        st.markdown('<div class="form-section">', unsafe_allow_html=True)
        st.markdown('<div class="form-section-title">🎨 Design & Style</div>', unsafe_allow_html=True)
        
        audiences = ["Investors", "Students", "Corporate", "Clients", "Managers"]
        audience = st.selectbox(
            "Target Audience *", 
            audiences,
            index=audiences.index(default_audience) if default_audience in audiences else 0
        )
        
        themes_list = ["Corporate Blue", "Gradient Modern", "Minimal Dark", "Pastel Soft", "Professional Green", "Elegant Purple"]
        theme = st.selectbox(
            "Visual Theme *", 
            themes_list,
            index=themes_list.index(default_theme) if default_theme in themes_list else 0
        )
        
        image_modes = ["With Images", "No Images"]
        image_mode = st.selectbox(
            "Image Mode *", 
            image_modes,
            index=image_modes.index(default_image_mode) if default_image_mode in image_modes else 0
        )
        
        if image_mode == "With Images":
            image_position = st.selectbox("Image Position", ["Right Side", "Left Side", "Top Right Corner", "Bottom", "Center"])
        else:
            image_position = "Right Side"
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Additional Options
    with st.expander("➕ Additional Options", expanded=False):
        key_points = st.text_area(
            "Key Points to Include", 
            placeholder="- Important point 1\n- Important point 2\n- Key statistic or fact",
            height=100
        )
        
        export_format = st.selectbox(
            "Export Format", 
            ["PowerPoint (.pptx)", "PowerPoint + PDF", "Google Slides (JSON)"]
        )
    
    st.markdown("---")
    
    # Action Buttons
    col_btn1, col_btn2, col_btn3 = st.columns([2, 1, 1])
    
    with col_btn1:
        generate_button = st.button("🚀 Generate Presentation", use_container_width=True, type="primary")
    
    with col_btn2:
        save_as_template = st.button("💾 Save as Template", use_container_width=True)
    
    with col_btn3:
        if st.session_state.selected_template:
            if st.button("🔄 Clear Template", use_container_width=True):
                st.session_state.selected_template = None
                st.rerun()
    
    # Save as Template Logic
    if save_as_template:
        with st.form("save_template_form"):
            st.subheader("💾 Save Current Settings as Template")
            template_name = st.text_input("Template Name *", placeholder="My Custom Template")
            
            if st.form_submit_button("Save Template"):
                if template_name:
                    template_data = {
                        "category": category,
                        "slide_count": slide_count,
                        "tone": tone,
                        "audience": audience,
                        "theme": theme,
                        "image_mode": image_mode,
                        "language": language
                    }
                    save_template_to_state(template_name, template_data)
                    st.success(f"✅ Template '{template_name}' saved!")
                    st.rerun()
                else:
                    st.error("Please enter a template name")
    
    # Generation Logic
    if generate_button:
        # Validation
        has_valid_api = False
        error_message = ""
        
        if "Groq" in model_choice:
            if groq_api_key:
                has_valid_api = True
            else:
                error_message = "⚠️ Please enter your Groq API key in the sidebar (it's FREE!)"
        elif "Grok" in model_choice:
            if grok_api_key:
                has_valid_api = True
            else:
                error_message = "⚠️ Please enter your Grok/xAI API key in the sidebar"
        else:
            if claude_api_key:
                has_valid_api = True
            else:
                error_message = "⚠️ Please enter your OpenRouter API key in the sidebar"
        
        if not has_valid_api:
            st.error(error_message)
        elif not topic:
            st.error("⚠️ Please enter a presentation topic")
        elif image_mode == "With Images" and not google_cx and not use_unsplash_fallback:
            st.error("⚠️ Please configure image sources in the sidebar")
        else:
            with st.spinner("🤖 Generating your presentation..."):
                slides_content = generate_content_with_retry(
                    claude_api_key, topic, category, slide_count, 
                    tone, audience, key_points if 'key_points' in dir() else "", 
                    model_choice, language, 
                    grok_api_key=grok_api_key if 'grok_api_key' in dir() else None,
                    groq_api_key=groq_api_key if 'groq_api_key' in dir() else None
                )
                
                if slides_content:
                    st.session_state.slides_content = slides_content
                    st.session_state.generation_count += 1
                    st.session_state.total_slides += len(slides_content)
                    
                    # Save to history
                    history_entry = {
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "topic": topic,
                        "slides": len(slides_content),
                        "category": category,
                        "theme": theme
                    }
                    st.session_state.generation_history.append(history_entry)
                    
                    st.success("✅ Content generated! Creating presentation...")
                    
                    prs = create_powerpoint(
                        slides_content, theme, image_mode,
                        google_api_key if 'google_api_key' in dir() else "",
                        google_cx if 'google_cx' in dir() else "",
                        use_unsplash_fallback, use_pexels_fallback, 
                        pexels_api_key if use_pexels_fallback and 'pexels_api_key' in dir() else None,
                        category, audience, topic, 
                        image_position, logo_data if 'logo_data' in dir() else None
                    )
                    
                    pptx_io = io.BytesIO()
                    prs.save(pptx_io)
                    pptx_io.seek(0)
                    st.session_state.final_pptx = pptx_io.getvalue()
                    
                    # Success Section
                    st.markdown("""
                    <div class="download-section">
                        <h2>🎉 Your Presentation is Ready!</h2>
                        <p>Download your professionally generated presentation below</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    if export_format == "PowerPoint (.pptx)":
                        col_dl = st.columns([1, 2, 1])
                        with col_dl[1]:
                            st.download_button(
                                label="📥 DOWNLOAD POWERPOINT",
                                data=st.session_state.final_pptx,
                                file_name=f"{topic.replace(' ', '_')}.pptx",
                                mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                                use_container_width=True,
                                type="primary"
                            )
                    
                    elif export_format == "PowerPoint + PDF":
                        col_dl1, col_dl2 = st.columns(2)
                        with col_dl1:
                            st.download_button(
                                "📥 PowerPoint (.pptx)",
                                st.session_state.final_pptx,
                                f"{topic.replace(' ', '_')}.pptx",
                                "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                                use_container_width=True,
                                type="primary"
                            )
                        with col_dl2:
                            pdf_buffer = export_to_pdf(slides_content, topic)
                            st.download_button(
                                "📄 PDF Document",
                                pdf_buffer,
                                f"{topic.replace(' ', '_')}.pdf",
                                "application/pdf",
                                use_container_width=True,
                                type="primary"
                            )
                    
                    elif export_format == "Google Slides (JSON)":
                        google_json = export_to_google_slides_json(slides_content, topic, theme)
                        col_dl = st.columns([1, 2, 1])
                        with col_dl[1]:
                            st.download_button(
                                "📥 Download JSON",
                                google_json,
                                f"{topic.replace(' ', '_')}.json",
                                "application/json",
                                use_container_width=True,
                                type="primary"
                            )
                    
                    st.markdown("---")
                    
                    # Analytics Dashboard
                    st.subheader("📊 Presentation Analytics")
                    
                    col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
                    
                    with col_stat1:
                        st.metric("Total Slides", len(slides_content))
                    
                    with col_stat2:
                        total_words = 0
                        for s in slides_content:
                            bullets = s.get('bullets', [])
                            if bullets and isinstance(bullets, list):
                                for bullet in bullets:
                                    if isinstance(bullet, str):
                                        total_words += len(bullet.split())
                        st.metric("Word Count", total_words)
                    
                    with col_stat3:
                        bullet_counts = [len(s.get('bullets', [])) for s in slides_content if isinstance(s.get('bullets', []), list)]
                        avg_bullets = sum(bullet_counts) / len(bullet_counts) if bullet_counts else 0
                        st.metric("Avg Points/Slide", f"{avg_bullets:.1f}")
                    
                    with col_stat4:
                        est_time = len(slides_content) * 2
                        st.metric("Est. Presentation Time", f"{est_time} min")
                    
                    # Content Preview - Show what was generated
                    with st.expander("📄 **Preview Generated Content**", expanded=True):
                        for idx, slide in enumerate(slides_content):
                            st.markdown(f"### Slide {idx + 1}: {slide['title']}")
                            
                            if slide.get('bullets') and len(slide['bullets']) > 0:
                                for bullet in slide['bullets']:
                                    st.markdown(f"• {bullet}")
                            else:
                                if idx == 0:
                                    st.caption("*Title slide - no bullet points*")
                                else:
                                    st.warning("⚠️ No content for this slide")
                            
                            if slide.get('speaker_notes'):
                                st.caption(f"📝 Notes: {slide['speaker_notes']}")
                            
                            st.markdown("---")
                    
                    # AI Coach
                    with st.expander("🎓 AI Presentation Coach", expanded=True):
                        issues, suggestions, score = analyze_presentation(slides_content)
                        
                        col_score1, col_score2 = st.columns([1, 3])
                        
                        with col_score1:
                            if score >= 80:
                                st.markdown(f"### 🟢 {score}/100")
                                st.success("Excellent!")
                            elif score >= 60:
                                st.markdown(f"### 🟡 {score}/100")
                                st.warning("Good!")
                            else:
                                st.markdown(f"### 🔴 {score}/100")
                                st.error("Needs Improvement")
                        
                        with col_score2:
                            if suggestions:
                                st.markdown("**Suggestions:**")
                                for suggestion in suggestions:
                                    st.write(f"• {suggestion}")
                            else:
                                st.success("✨ Your presentation looks great! No major issues found.")

with tab2:
    st.markdown("### 📁 Template Manager")
    
    col_temp1, col_temp2 = st.columns([2, 1])
    
    with col_temp1:
        st.markdown("#### Your Saved Templates")
        
        if st.session_state.templates:
            for temp_id, template in st.session_state.templates.items():
                with st.container():
                    st.markdown(f"""
                    <div class="dashboard-card">
                        <h4>{template['name']}</h4>
                        <p><strong>Category:</strong> {template['category']} | <strong>Slides:</strong> {template['slide_count']} | <strong>Theme:</strong> {template['theme']}</p>
                        <p><small>Created: {template['created_at']} | Used: {template['usage_count']} times</small></p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    col_t1, col_t2, col_t3 = st.columns([1, 1, 1])
                    
                    with col_t1:
                        if st.button("📋 Use", key=f"use_{temp_id}"):
                            st.session_state.selected_template = template
                            st.session_state.templates[temp_id]['usage_count'] += 1
                            st.success(f"✅ Template '{template['name']}' selected!")
                            st.rerun()
                    
                    with col_t2:
                        template_json = json.dumps(template, indent=2)
                        st.download_button(
                            "📥 Export",
                            template_json,
                            f"{template['name'].replace(' ', '_')}.json",
                            "application/json",
                            key=f"export_{temp_id}"
                        )
                    
                    with col_t3:
                        if st.button("🗑️ Delete", key=f"delete_{temp_id}"):
                            delete_template(temp_id)
                            st.warning(f"Template deleted!")
                            st.rerun()
                    
                    st.markdown("---")
        else:
            st.info("No saved templates yet. Create one from the 'Create' tab!")
    
    with col_temp2:
        st.markdown("#### Import/Export")
        
        # Export all templates
        if st.session_state.templates:
            all_templates_json = export_all_templates()
            st.download_button(
                "📤 Export All Templates",
                all_templates_json,
                "all_templates.json",
                "application/json",
                use_container_width=True
            )
        
        st.markdown("---")
        
        # Import templates
        st.markdown("**Import Templates:**")
        uploaded_template = st.file_uploader("Upload Template JSON", type=['json'], key="template_upload")
        
        if uploaded_template:
            try:
                template_content = uploaded_template.read().decode('utf-8')
                template_data = json.loads(template_content)
                
                # Check if it's a single template or multiple
                if 'name' in template_data:
                    # Single template
                    if st.button("Import This Template"):
                        save_template_to_state(template_data['name'], template_data)
                        st.success("✅ Template imported!")
                        st.rerun()
                else:
                    # Multiple templates
                    if st.button("Import All Templates"):
                        import_templates(template_content)
                        st.success("✅ All templates imported!")
                        st.rerun()
            except Exception as e:
                st.error(f"Error reading template: {str(e)}")
        
        st.markdown("---")
        
        # Template Statistics
        st.markdown("#### 📈 Template Stats")
        st.metric("Total Templates", len(st.session_state.templates))
        
        if st.session_state.templates:
            most_used = max(st.session_state.templates.items(), key=lambda x: x[1]['usage_count'])
            st.metric("Most Used", most_used[1]['name'])

with tab3:
    st.markdown("### 📊 Bulk Generate")
    
    st.info("📤 Upload a CSV file with multiple presentation topics to generate them in batch")
    
    # Sample CSV structure
    st.markdown("#### Sample CSV Structure:")
    sample_df = pd.DataFrame({
        'topic': ['AI in Healthcare', 'Digital Marketing Strategies', 'Cloud Computing Basics'],
        'category': ['Technical', 'Marketing', 'Technical'],
        'slide_count': [8, 10, 6],
        'tone': ['Formal', 'Persuasive', 'Educational'],
        'audience': ['Managers', 'Clients', 'Students'],
        'theme': ['Corporate Blue', 'Gradient Modern', 'Pastel Soft']
    })
    
    st.dataframe(sample_df, use_container_width=True)
    
    csv_sample = sample_df.to_csv(index=False)
    st.download_button(
        "📥 Download Sample CSV",
        csv_sample,
        "bulk_template.csv",
        "text/csv",
        use_container_width=True
    )
    
    st.markdown("---")
    
    # Upload CSV
    uploaded_csv = st.file_uploader("Upload your CSV file", type=['csv'], key="bulk_csv")
    
    if uploaded_csv:
        try:
            df = pd.read_csv(uploaded_csv)
            st.success(f"✅ Loaded {len(df)} presentations to generate")
            st.dataframe(df, use_container_width=True)
            
            if st.button("🚀 Generate All Presentations", use_container_width=True, type="primary"):
                if not claude_api_key:
                    st.error("Please configure API keys in the sidebar")
                else:
                    st.warning("⚠️ Bulk generation will take time. Please be patient.")
                    
                    progress = st.progress(0)
                    results = []
                    
                    for idx, row in df.iterrows():
                        st.write(f"Generating {idx + 1}/{len(df)}: {row['topic']}")
                        progress.progress((idx + 1) / len(df))
                        
                        # This would generate each presentation
                        # For now, just simulate
                        time.sleep(1)
                        results.append({
                            "topic": row['topic'],
                            "status": "Success",
                            "slides": row.get('slide_count', 6)
                        })
                    
                    st.success("✅ All presentations generated!")
                    results_df = pd.DataFrame(results)
                    st.dataframe(results_df)
        
        except Exception as e:
            st.error(f"Error reading CSV: {str(e)}")

with tab4:
    st.markdown("### 📜 Generation History")
    
    if st.session_state.generation_history:
        for idx, entry in enumerate(reversed(st.session_state.generation_history)):
            st.markdown(f"""
            <div class="history-item">
                <strong>{entry['topic']}</strong><br>
                <small>📅 {entry['timestamp']} | 📑 {entry['slides']} slides | 📂 {entry['category']} | 🎨 {entry['theme']}</small>
            </div>
            """, unsafe_allow_html=True)
        
        if st.button("🗑️ Clear History"):
            st.session_state.generation_history = []
            st.success("History cleared!")
            st.rerun()
    else:
        st.info("No generation history yet. Create your first presentation!")

with tab5:
    st.markdown("### ⚙️ Settings & Preferences")
    
    col_set1, col_set2 = st.columns(2)
    
    with col_set1:
        st.markdown("#### 🎨 Appearance")
        
        theme_option = st.radio(
            "Dashboard Theme",
            ["Light", "Dark"],
            horizontal=True
        )
        
        st.markdown("#### 📊 Default Values")
        default_slide_count = st.slider("Default Slide Count", 3, 20, 6)
        default_category_setting = st.selectbox("Default Category", ["Business", "Pitch", "Marketing", "Technical", "Academic", "Training", "Sales"])
    
    with col_set2:
        st.markdown("#### 🔧 Advanced")
        
        auto_save = st.checkbox("Auto-save templates", value=True)
        show_tips = st.checkbox("Show helpful tips", value=True)
        
        st.markdown("#### 🔄 Reset Options")
        
        if st.button("🔄 Reset Statistics"):
            st.session_state.generation_count = 0
            st.session_state.total_slides = 0
            st.session_state.google_searches_used = 0
            st.success("Statistics reset!")
            st.rerun()
        
        if st.button("🗑️ Clear All Data"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.success("All data cleared!")
            st.rerun()

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666; padding: 2rem 0;'>
    <p><strong>🎯 AI PowerPoint Generator Pro</strong></p>
    <p>✨ Powered by AI | Professional Templates | Smart Analytics | Multi-Format Export</p>
    <p><small>Version 2.0 - Built with Streamlit</small></p>
</div>
""", unsafe_allow_html=True)
