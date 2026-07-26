"""
🤖 MY AI PRO — Your Complete ChatGPT Clone
Features: Streaming Chat | File Upload (PDF/DOCX/TXT/Images) | Web Search | 
          Voice Input | Image Generation | Vision | Chat History | Export
"""

import streamlit as st
import openai
import json
import os
import base64
import io
import textwrap
from datetime import datetime
from pathlib import Path
from duckduckgo_search import DDGS

# Optional dependencies with graceful fallback
try:
    import fitz  # PyMuPDF
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False

try:
    from docx import Document
    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import ollama
    HAS_OLLAMA = True
except ImportError:
    HAS_OLLAMA = False

# ============ CONFIG ============
CHATS_DIR = Path("chat_history")
CHATS_DIR.mkdir(exist_ok=True)
MAX_FILE_SIZE_MB = 25

VISION_MODELS = {
    "openai": ["gpt-4o", "gpt-4o-mini"],
    "ollama": ["llava", "llava-phi3", "llama3.2-vision", "bakllava", "moondream"]
}

# ============ PAGE SETUP ============
st.set_page_config(
    page_title="My AI Pro",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============ CUSTOM CSS ============
st.markdown("""
<style>
    .main { background-color: #0a0a0a; }
    .stChatMessage { border-radius: 16px; margin: 6px 0; }
    [data-testid="stSidebar"] { background-color: #111111; border-right: 1px solid #222; }
    .stChatInputContainer { border-radius: 12px; border: 1px solid #333; background: #1a1a1a; }
    pre { background-color: #1e1e1e; border-radius: 10px; padding: 16px; border: 1px solid #333; }
    code { font-family: 'SF Mono', Monaco, monospace; font-size: 0.9em; }
    .file-chip { background: #1e3a5f; color: #7ec8e3; padding: 4px 12px; border-radius: 12px; 
                 font-size: 0.85em; display: inline-block; margin: 2px; border: 1px solid #2a5a8a; }
    .feature-badge { padding: 2px 8px; border-radius: 6px; font-size: 0.75em; font-weight: 600; margin-right: 4px; }
    .badge-search { background: #1e3a2f; color: #4ade80; border: 1px solid #2a5a4a; }
    .badge-reason { background: #3a2a1e; color: #fbbf24; border: 1px solid #5a4a2a; }
    .badge-image { background: #3a1e3a; color: #f472b6; border: 1px solid #5a2a5a; }
    .badge-vision { background: #1e2a3a; color: #60a5fa; border: 1px solid #2a4a5a; }
    ::-webkit-scrollbar { width: 8px; }
    ::-webkit-scrollbar-track { background: #0a0a0a; }
    ::-webkit-scrollbar-thumb { background: #333; border-radius: 4px; }
    ::-webkit-scrollbar-thumb:hover { background: #555; }
    .voice-btn { background: linear-gradient(135deg, #ff4b4b, #ff6b6b); color: white; border: none; 
                 border-radius: 50%; width: 42px; height: 42px; font-size: 20px; cursor: pointer;
                 box-shadow: 0 4px 15px rgba(255,75,75,0.3); transition: all 0.2s; }
    .voice-btn:hover { transform: scale(1.05); box-shadow: 0 6px 20px rgba(255,75,75,0.5); }
    .voice-btn.recording { background: linear-gradient(135deg, #00cc88, #00ee99); 
                           box-shadow: 0 4px 15px rgba(0,204,136,0.3); animation: pulse 1.5s infinite; }
    @keyframes pulse { 0% { box-shadow: 0 0 0 0 rgba(0,204,136,0.4); } 
                       70% { box-shadow: 0 0 0 12px rgba(0,204,136,0); } 
                       100% { box-shadow: 0 0 0 0 rgba(0,204,136,0); } }
    .search-source { font-size: 0.8em; color: #888; border-left: 2px solid #444; padding-left: 8px; margin: 4px 0; }
    .cost-pill { background: #1a3a1a; color: #7ee787; padding: 2px 8px; border-radius: 10px; 
                 font-size: 0.75em; border: 1px solid #2a5a2a; }
</style>
""", unsafe_allow_html=True)

# ============ HELPERS ============
def extract_pdf(file_bytes):
    if not HAS_PYMUPDF:
        return "[Error: PyMuPDF not installed. Run: `pip install pymupdf` to read PDFs]"
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        text = []
        for page in doc:
            text.append(page.get_text())
        return "\n".join(text)
    except Exception as e:
        return f"[Error reading PDF: {e}]"

def extract_docx(file_bytes):
    if not HAS_DOCX:
        return "[Error: python-docx not installed. Run: `pip install python-docx` to read Word files]"
    try:
        doc = Document(io.BytesIO(file_bytes))
        return "\n".join([p.text for p in doc.paragraphs])
    except Exception as e:
        return f"[Error reading DOCX: {e}]"

def extract_text_file(file_bytes):
    try:
        return file_bytes.decode("utf-8")
    except:
        try:
            return file_bytes.decode("latin-1")
        except Exception as e:
            return f"[Error reading text file: {e}]"

def process_image(file_bytes):
    if not HAS_PIL:
        return None, "[Error: Pillow not installed. Run: `pip install pillow`]"
    try:
        img = Image.open(io.BytesIO(file_bytes))
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        buffered = io.BytesIO()
        img.save(buffered, format="JPEG", quality=85)
        b64 = base64.b64encode(buffered.getvalue()).decode()
        return b64, None
    except Exception as e:
        return None, f"[Error processing image: {e}]"

def perform_web_search(query, max_results=5):
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        if not results:
            return None
        formatted = []
        for i, r in enumerate(results, 1):
            title = r.get("title", "No title")
            body = r.get("body", "")[:300]
            href = r.get("href", "")
            formatted.append(f"[{i}] {title}\n{body}\nSource: {href}")
        return "\n\n".join(formatted)
    except Exception as e:
        return f"[Search error: {e}]"

def is_vision_capable(provider, model):
    return model in VISION_MODELS.get(provider, [])

def estimate_cost(model, input_tokens, output_tokens):
    # Rough estimates per 1K tokens
    rates = {
        "gpt-4o": (0.005, 0.015),
        "gpt-4o-mini": (0.00015, 0.0006),
        "gpt-3.5-turbo": (0.0005, 0.0015)
    }
    inp, out = rates.get(model, (0, 0))
    return (input_tokens / 1000 * inp) + (output_tokens / 1000 * out)

def save_chat():
    if st.session_state.messages:
        chat_file = CHATS_DIR / f"{st.session_state.current_chat_id}.json"
        with open(chat_file, "w") as f:
            json.dump({
                "id": st.session_state.current_chat_id,
                "title": st.session_state.get("chat_title", "Untitled"),
                "messages": st.session_state.messages,
                "timestamp": datetime.now().isoformat()
            }, f)

# ============ SESSION STATE ============
def init_state():
    defaults = {
        "messages": [],
        "current_chat_id": datetime.now().strftime("%Y-%m-%d_%H-%M-%S"),
        "chat_title": "New Chat",
        "model_provider": "openai",
        "uploaded_text": None,
        "uploaded_image_b64": None,
        "uploaded_filename": None,
        "pending_response": False,
        "total_cost": 0.0,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

init_state()

# ============ VOICE INPUT HANDLER ============
# JavaScript speech recognition that passes data back via query params
voice_html = """
<div style="text-align: center; margin: 8px 0;">
    <button id="mic-btn" class="voice-btn" title="Click to speak">🎙️</button>
    <p id="mic-status" style="color: #888; font-size: 11px; margin: 6px 0 0 0;">Click to speak</p>
</div>
<script>
    const btn = document.getElementById('mic-btn');
    const status = document.getElementById('mic-status');
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
        status.textContent = 'Browser not supported';
        btn.style.display = 'none';
    } else {
        const recognition = new SpeechRecognition();
        recognition.continuous = false;
        recognition.interimResults = false;
        recognition.lang = 'en-US';

        recognition.onstart = () => {
            status.textContent = 'Listening...';
            btn.classList.add('recording');
        };
        recognition.onend = () => {
            status.textContent = 'Click to speak';
            btn.classList.remove('recording');
        };
        recognition.onresult = (event) => {
            const transcript = event.results[0][0].transcript;
            status.textContent = 'Processing...';
            const url = new URL(window.location.href);
            url.searchParams.set('voice_input', transcript);
            window.location.href = url.toString();
        };
        recognition.onerror = (event) => {
            status.textContent = 'Error: ' + event.error;
            btn.classList.remove('recording');
        };
        btn.onclick = () => {
            try { recognition.start(); } 
            catch(e) { status.textContent = 'Click again'; }
        };
    }
</script>
"""

# Check for voice input from URL
if "voice_input" in st.query_params:
    voice_text = st.query_params["voice_input"]
    if voice_text:
        # Prevent duplicate processing
        last_user_msgs = [m["content"] for m in st.session_state.messages if m["role"] == "user"]
        if not last_user_msgs or voice_text != last_user_msgs[-1]:
            st.session_state.messages.append({"role": "user", "content": voice_text})
            st.session_state.pending_response = True
    # Clear param
    del st.query_params["voice_input"]
    st.rerun()

# ============ SIDEBAR ============
with st.sidebar:
    st.markdown("## 🤖 My AI Pro")
    st.markdown("<p style='color: #666; font-size: 0.9em;'>Your personal ChatGPT with superpowers</p>", unsafe_allow_html=True)
    st.markdown("---")

    # --- Provider & Model ---
    provider = st.radio(
        "AI Brain",
        ["OpenAI API", "Local Ollama (Free)"],
        index=0 if st.session_state.model_provider == "openai" else 1,
        help="OpenAI for smarts, Ollama for privacy and zero cost"
    )
    st.session_state.model_provider = "openai" if "OpenAI" in provider else "ollama"

    if st.session_state.model_provider == "openai":
        model = st.selectbox("Model", ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"], index=0)
        api_key = st.text_input("OpenAI API Key", type="password", 
                               help="Get at platform.openai.com")
        st.caption(f"💳 Est. cost: ~${estimate_cost(model, 2000, 500):.4f} per chat")
    else:
        model = st.selectbox("Local Model", 
                            ["qwen3:32b", "llama3.2", "llama3.1", "mistral", "codellama", "phi3", "llava"], 
                            index=0)
        api_key = None
        if not HAS_OLLAMA:
            st.error("❌ Ollama Python package not installed. Run: `pip install ollama`")
        st.info("📥 First time? Run: `ollama pull llama3.1` in terminal")
        st.caption("🆓 100% free, runs offline, fully private")

    # --- Personality & Mode ---
    st.markdown("---")
    system_prompt = st.text_area(
        "🎭 AI Personality",
        value="You are a helpful, knowledgeable, and friendly AI assistant. You provide clear, accurate, and well-structured responses.",
        height=70,
        help="Tell your AI how to behave"
    )

    col_t1, col_t2 = st.columns(2)
    with col_t1:
        temperature = st.slider("🌡️ Temp", 0.0, 1.0, 0.7, 
                               help="0 = factual, 1 = creative")
    with col_t2:
        max_tokens = st.slider("📏 Max Tokens", 256, 4096, 2048, 256,
                              help="Response length limit")

    # --- Feature Toggles ---
    st.markdown("---")
    st.markdown("### ⚡ Superpowers")

    enable_search = st.toggle("🌐 Web Search", value=False,
                             help="Searches the internet and includes results in context")
    enable_reasoning = st.toggle("🧠 Reasoning Mode", value=False,
                                help="Forces step-by-step thinking before answering")
    enable_image_gen = st.toggle("🎨 Image Gen", value=False,
                                help="Generate images with DALL-E 3 (OpenAI only)")

    if enable_image_gen and st.session_state.model_provider != "openai":
        st.warning("Image generation requires OpenAI. Switch provider to use this.")
        enable_image_gen = False

    # --- Voice Input ---
    st.markdown("---")
    st.markdown("### 🎙️ Voice Input")
    st.components.v1.html(voice_html, height=80)
    st.caption("Works in Chrome/Edge")

    # --- File Upload ---
    st.markdown("---")
    st.markdown("### 📎 File Upload")

    uploaded_file = st.file_uploader(
        "Drop PDF, Word, TXT, Code, or Image",
        type=["pdf", "docx", "txt", "py", "js", "html", "css", "md", "json", "png", "jpg", "jpeg", "webp"],
        help="Upload a file to discuss with the AI"
    )

    if uploaded_file is not None:
        file_size = len(uploaded_file.getvalue()) / (1024 * 1024)
        if file_size > MAX_FILE_SIZE_MB:
            st.error(f"File too large ({file_size:.1f}MB). Max: {MAX_FILE_SIZE_MB}MB")
        else:
            file_bytes = uploaded_file.getvalue()
            fname = uploaded_file.name.lower()

            if fname.endswith(".pdf"):
                extracted = extract_pdf(file_bytes)
                st.session_state.uploaded_text = extracted
                st.session_state.uploaded_image_b64 = None
                st.session_state.uploaded_filename = uploaded_file.name
                st.success(f"📄 PDF loaded ({len(extracted)} chars)")

            elif fname.endswith(".docx"):
                extracted = extract_docx(file_bytes)
                st.session_state.uploaded_text = extracted
                st.session_state.uploaded_image_b64 = None
                st.session_state.uploaded_filename = uploaded_file.name
                st.success(f"📄 Word doc loaded ({len(extracted)} chars)")

            elif fname.endswith((".txt", ".py", ".js", ".html", ".css", ".md", ".json")):
                extracted = extract_text_file(file_bytes)
                st.session_state.uploaded_text = extracted
                st.session_state.uploaded_image_b64 = None
                st.session_state.uploaded_filename = uploaded_file.name
                st.success(f"📄 Text file loaded ({len(extracted)} chars)")

            elif fname.endswith((".png", ".jpg", ".jpeg", ".webp")):
                b64, err = process_image(file_bytes)
                if err:
                    st.error(err)
                else:
                    st.session_state.uploaded_image_b64 = b64
                    st.session_state.uploaded_text = None
                    st.session_state.uploaded_filename = uploaded_file.name
                    st.success(f"🖼️ Image loaded")
                    if not is_vision_capable(st.session_state.model_provider, model):
                        st.warning(f"⚠️ {model} may not support vision. Try llama3.2-vision or gpt-4o.")

            # Show remove button
            if st.button("🗑️ Remove File", use_container_width=True):
                st.session_state.uploaded_text = None
                st.session_state.uploaded_image_b64 = None
                st.session_state.uploaded_filename = None
                st.rerun()

    # Show current file chip
    if st.session_state.uploaded_filename:
        st.markdown(f"<div class='file-chip'>📎 {st.session_state.uploaded_filename}</div>", 
                   unsafe_allow_html=True)

    # --- Chat Management ---
    st.markdown("---")
    st.markdown("### 💬 Chats")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("➕ New", use_container_width=True):
            save_chat()
            st.session_state.messages = []
            st.session_state.current_chat_id = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            st.session_state.chat_title = "New Chat"
            st.session_state.uploaded_text = None
            st.session_state.uploaded_image_b64 = None
            st.session_state.uploaded_filename = None
            st.rerun()
    with c2:
        if st.session_state.messages and st.button("🗑️ Clear", use_container_width=True):
            st.session_state.messages = []
            st.rerun()

    # Chat history list
    chat_files = sorted(CHATS_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)
    for chat_file in chat_files[:20]:
        try:
            with open(chat_file) as f:
                chat_data = json.load(f)
            msgs = chat_data.get("messages", [])
            title = chat_data.get("title", "Untitled")
            first_user = next((m["content"][:22] for m in msgs if m["role"] == "user"), "Empty")
            display = title if title != "New Chat" else (first_user + "..." if first_user != "Empty" else "Empty Chat")
            if st.button(f"📝 {display}", key=f"load_{chat_file.stem}", use_container_width=True):
                save_chat()  # Save current before switching
                st.session_state.messages = msgs
                st.session_state.current_chat_id = chat_data.get("id", chat_file.stem)
                st.session_state.chat_title = title
                st.rerun()
        except:
            pass

    # --- Export ---
    st.markdown("---")
    if st.session_state.messages:
        md_content = f"# My AI Pro — Chat Export\n\n**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n---\n\n"
        for msg in st.session_state.messages:
            role = "👤 User" if msg["role"] == "user" else "🤖 Assistant"
            md_content += f"## {role}\n{msg['content']}\n\n---\n\n"

        st.download_button(
            "📥 Export Markdown",
            md_content,
            file_name=f"my_ai_chat_{st.session_state.current_chat_id}.md",
            mime="text/markdown",
            use_container_width=True
        )

    # Total cost display
    if st.session_state.model_provider == "openai" and st.session_state.total_cost > 0:
        st.markdown(f"<div style='text-align:center; margin-top:10px;'>Total spent: <span class='cost-pill'>${st.session_state.total_cost:.4f}</span></div>", 
                   unsafe_allow_html=True)

# ============ MAIN CHAT AREA ============
# Header
st.markdown("<h1 style='text-align: center; margin-bottom: 0;'>🤖 My AI Pro</h1>", unsafe_allow_html=True)

# Feature badges
badges = []
if enable_search: badges.append("<span class='feature-badge badge-search'>🌐 Web Search</span>")
if enable_reasoning: badges.append("<span class='feature-badge badge-reason'>🧠 Reasoning</span>")
if enable_image_gen: badges.append("<span class='feature-badge badge-image'>🎨 Image Gen</span>")
if st.session_state.uploaded_image_b64: badges.append("<span class='feature-badge badge-vision'>🖼️ Vision</span>")
if badges:
    st.markdown(f"<div style='text-align: center; margin: 8px 0;'>{''.join(badges)}</div>", unsafe_allow_html=True)
else:
    st.markdown("<p style='text-align: center; color: #555; margin-top: 0;'>Your personal ChatGPT with superpowers</p>", unsafe_allow_html=True)

st.markdown("---")

# Display messages
for i, message in enumerate(st.session_state.messages):
    avatar = "👤" if message["role"] == "user" else "🤖"
    with st.chat_message(message["role"], avatar=avatar):
        # If this message has an image (for image generation)
        if message.get("image_url"):
            st.image(message["image_url"], use_container_width=True)
        st.markdown(message["content"])

        # Show search sources if present
        if message.get("search_sources"):
            with st.expander("🔍 Search Sources"):
                for src in message["search_sources"]:
                    st.markdown(f"<div class='search-source'><strong>{src['title']}</strong><br>{src['body'][:200]}...<br><a href='{src['href']}' target='_blank' style='color: #4ade80;'>{src['href']}</a></div>", 
                               unsafe_allow_html=True)

# Welcome screen
if not st.session_state.messages:
    st.markdown("""
    <div style='text-align: center; padding: 40px 20px; color: #666;'>
        <h2>👋 Welcome</h2>
        <p style='font-size: 1.1em;'>Start typing, upload a file, click the mic, or enable superpowers in the sidebar.</p>
        <div style='margin-top: 30px; display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; max-width: 700px; margin-left: auto; margin-right: auto;'>
            <div style='background: #151515; padding: 15px; border-radius: 12px; border: 1px solid #222;'>
                <div style='font-size: 1.5em; margin-bottom: 8px;'>📎</div>
                <strong>Upload Files</strong><br><span style='font-size: 0.85em; color: #888;'>PDF, Word, images, code</span>
            </div>
            <div style='background: #151515; padding: 15px; border-radius: 12px; border: 1px solid #222;'>
                <div style='font-size: 1.5em; margin-bottom: 8px;'>🌐</div>
                <strong>Web Search</strong><br><span style='font-size: 0.85em; color: #888;'>Real-time internet answers</span>
            </div>
            <div style='background: #151515; padding: 15px; border-radius: 12px; border: 1px solid #222;'>
                <div style='font-size: 1.5em; margin-bottom: 8px;'>🎙️</div>
                <strong>Voice Input</strong><br><span style='font-size: 0.85em; color: #888;'>Speak instead of type</span>
            </div>
            <div style='background: #151515; padding: 15px; border-radius: 12px; border: 1px solid #222;'>
                <div style='font-size: 1.5em; margin-bottom: 8px;'>🎨</div>
                <strong>Image Gen</strong><br><span style='font-size: 0.85em; color: #888;'>Create art with DALL-E 3</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

# ============ HANDLE PENDING RESPONSE ============
if st.session_state.pending_response and st.session_state.messages:
    st.session_state.pending_response = False

    # Get last user message
    last_msg = st.session_state.messages[-1]
    if last_msg["role"] != "user":
        st.stop()

    user_prompt = last_msg["content"]

    # Generate response
    with st.chat_message("assistant", avatar="🤖"):
        message_placeholder = st.empty()
        full_response = ""
        search_sources = []
        image_url = None

        try:
            # Build system and context
            system_msg = system_prompt
            if enable_reasoning:
                system_msg += "\n\nThink step by step. Show your reasoning process before giving your final answer."

            history = [{"role": "system", "content": system_msg}]

            # Inject uploaded text
            if st.session_state.uploaded_text:
                context = st.session_state.uploaded_text[:10000]  # Limit context
                fname = st.session_state.uploaded_filename or "document"
                history.append({
                    "role": "system",
                    "content": f"The user has uploaded a document named '{fname}'. Here is its content:\n\n{context}\n\nUse this context to answer their questions."
                })

            # Web search
            if enable_search and not enable_image_gen:
                with st.status("🔍 Searching the web...", expanded=False) as status_obj:
                    search_text = perform_web_search(user_prompt)
                    if search_text and not search_text.startswith("[Search error"):
                        history.append({
                            "role": "system",
                            "content": f"Here are recent web search results related to the user's question:\n\n{search_text}\n\nUse this information to answer accurately. Cite sources when possible."
                        })
                        # Parse sources for display
                        try:
                            with DDGS() as ddgs:
                                raw_results = list(ddgs.text(user_prompt, max_results=5))
                            search_sources = [{"title": r.get("title", ""), "href": r.get("href", ""), "body": r.get("body", "")} for r in raw_results]
                        except:
                            pass
                    status_obj.update(label="✅ Search complete", state="complete", expanded=False)

            # Image Generation Mode
            if enable_image_gen and st.session_state.model_provider == "openai":
                if not api_key:
                    st.error("🔑 Enter your OpenAI API key in the sidebar to generate images.")
                    st.stop()

                with st.status("🎨 Generating image...", expanded=False):
                    client = openai.OpenAI(api_key=api_key)
                    img_response = client.images.generate(
                        model="dall-e-3",
                        prompt=user_prompt,
                        size="1024x1024",
                        quality="standard",
                        n=1
                    )
                    image_url = img_response.data[0].url
                    full_response = f"Here is the image I generated based on your request: **{user_prompt}**"
                    st.session_state.total_cost += 0.04  # DALL-E 3 standard ~$0.04

                st.image(image_url, use_container_width=True)
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": full_response,
                    "image_url": image_url
                })
                save_chat()
                st.rerun()

            # Regular chat completion
            # Build message history (skip the last user message since we'll handle it specially if image)
            for msg in st.session_state.messages[:-1]:
                history.append({"role": msg["role"], "content": msg["content"]})

            # Handle vision (image upload)
            has_vision = is_vision_capable(st.session_state.model_provider, model)
            image_b64 = st.session_state.uploaded_image_b64

            if image_b64 and has_vision:
                if st.session_state.model_provider == "openai":
                    history.append({
                        "role": "user",
                        "content": [
                            {"type": "text", "text": user_prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}}
                        ]
                    })
                else:  # Ollama
                    history.append({
                        "role": "user",
                        "content": user_prompt,
                        "images": [image_b64]
                    })
            else:
                history.append({"role": "user", "content": user_prompt})

            # Streaming response
            if st.session_state.model_provider == "openai":
                if not api_key:
                    st.error("🔑 Please enter your OpenAI API key in the sidebar!")
                    st.stop()

                client = openai.OpenAI(api_key=api_key)

                # Estimate input tokens (rough)
                input_text = " ".join([m.get("content", "") if isinstance(m.get("content"), str) else str(m.get("content", "")) for m in history])
                input_tokens = len(input_text.split()) * 1.3  # rough estimate

                response = client.chat.completions.create(
                    model=model,
                    messages=history,
                    stream=True,
                    temperature=temperature,
                    max_tokens=max_tokens
                )

                output_tokens = 0
                for chunk in response:
                    delta = chunk.choices[0].delta
                    if delta.content:
                        full_response += delta.content
                        output_tokens += 1
                        message_placeholder.markdown(full_response + "▌")

                # Update cost
                cost = estimate_cost(model, int(input_tokens), output_tokens)
                st.session_state.total_cost += cost

            else:  # Ollama
                if not HAS_OLLAMA:
                    st.error("❌ Ollama package not installed. Run: `pip install ollama`")
                    st.stop()

                # Filter out images from history for non-vision models (safety)
                clean_history = []
                for h in history:
                    if "images" in h and not has_vision:
                        clean_h = {k: v for k, v in h.items() if k != "images"}
                        clean_history.append(clean_h)
                    else:
                        clean_history.append(h)

                response = ollama.chat(
                    model=model,
                    messages=clean_history,
                    stream=True,
                    options={"temperature": temperature, "num_predict": max_tokens}
                )

                for chunk in response:
                    content = chunk['message']['content']
                    if content:
                        full_response += content
                        message_placeholder.markdown(full_response + "▌")

            # Final display
            message_placeholder.markdown(full_response)

            # Save response
            msg_data = {"role": "assistant", "content": full_response}
            if search_sources:
                msg_data["search_sources"] = search_sources
            st.session_state.messages.append(msg_data)

            # Update chat title from first user message
            if st.session_state.chat_title == "New Chat" and len(st.session_state.messages) == 2:
                st.session_state.chat_title = user_prompt[:40]

            save_chat()

        except Exception as e:
            error_msg = str(e)
            if "connection" in error_msg.lower() and st.session_state.model_provider == "ollama":
                st.error("🔌 Cannot connect to Ollama. Run `ollama serve` in another terminal, or start the Ollama app.")
            elif "api_key" in error_msg.lower() or "authentication" in error_msg.lower():
                st.error("🔑 Invalid or missing API key. Check your OpenAI key in the sidebar.")
            else:
                st.error(f"❌ Error: {error_msg}")

            # Remove the pending user message on error so they can retry
            if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
                st.session_state.messages.pop()
            save_chat()

# ============ CHAT INPUT ============
if prompt := st.chat_input("Message My AI... (or upload a file, enable web search, or speak)"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.session_state.pending_response = True
    st.rerun()
