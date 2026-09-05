import streamlit as st
import os
from datetime import datetime, date, timedelta

# NOTE: Ensure these modules exist in your project directory
from db_manager import (
    get_student_profile,
    get_chat_history,
    create_table,
    save_student_profile,
    save_chat,
)

from utils.pdf_processor import extract_text_from_pdf
from utils.ollama_client import ask_ollama
from utils.mcq_generator import generate_mcqs
from utils.important_questions import generate_important_questions
from utils.rag import answer_question
from utils.summarizer import summarize_text


# =========================================================
# PAGE CONFIG
# =========================================================
st.set_page_config(
    page_title="AI College Assistant",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)


# =========================================================
# DATABASE
# =========================================================
create_table()
profile = get_student_profile() or {}
history = get_chat_history()[:5]

name = profile.get("name") or "Student"
branch = profile.get("branch") or "Computer Engineering"
semester = profile.get("semester") or "Semester Not Set"
college = profile.get("college") or "College Not Set"

raw_exam_date = profile.get("exam_date")
exam_date = None

if raw_exam_date:
    try:
        if isinstance(raw_exam_date, date):
            exam_date = raw_exam_date
        else:
            exam_date = datetime.strptime(str(raw_exam_date), "%Y-%m-%d").date()
    except (ValueError, TypeError):
        exam_date = None

try:
    study_hours = float(profile.get("study_hours") or 0)
except (ValueError, TypeError):
    study_hours = 0.0


# =========================================================
# SESSION STATE
# =========================================================
defaults = {
    "page": "dashboard",
    "chat_messages": [],
    "rag_chat": [],
    "study_plan": None,
    "uploaded_files": [],
    "pdf_text": "",
    "vector_store": None,
    "completed_tasks": set(),
    "generated_tasks": [],
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


# =========================================================
# GENERAL HELPERS
# =========================================================
def safe_html(value):
    """Prevent user-entered profile data from breaking HTML."""
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def days_until_exam():
    if not exam_date:
        return None
    return (exam_date - date.today()).days


def progress_percent():
    tasks = st.session_state.get("generated_tasks", [])
    if not tasks:
        return 0
    completed = len(st.session_state.get("completed_tasks", set()))
    return min(100, int((completed / len(tasks)) * 100))


def create_default_tasks():
    """Create useful dashboard tasks when the user has not generated a plan."""
    return [
        {"id": "task_1", "title": "Review today's lecture notes", "subject": branch},
        {"id": "task_2", "title": "Practice 10 important questions", "subject": "Exam Preparation"},
        {"id": "task_3", "title": "Complete one focused study session", "subject": "Study Goal"},
        {"id": "task_4", "title": "Ask AI Assistant one doubt", "subject": "Smart Learning"},
    ]


def render_back_button():
    """Renders a 'Back to Dashboard' button for sub-pages."""
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("⬅️ Back to Dashboard", key=f"back_{st.session_state.page}"):
        st.session_state.page = "dashboard"
        st.rerun()
    st.markdown("<br>", unsafe_allow_html=True)


# =========================================================
# BEAUTIFUL MODERN UI
# =========================================================
st.markdown(
    """
<style>
/* ---------- GLOBAL ---------- */
#MainMenu {visibility: hidden;}
header {visibility: hidden;}
footer {visibility: hidden;}

.stApp {
    background:
        radial-gradient(circle at 10% 0%, rgba(124,58,237,.08), transparent 30%),
        radial-gradient(circle at 100% 10%, rgba(59,130,246,.07), transparent 28%),
        #f7f8fc;
}

.block-container {
    max-width: 1450px;
    padding-top: 1.5rem;
    padding-bottom: 3rem;
}

/* ---------- TYPOGRAPHY ---------- */
.main-title {
    font-size: 2.25rem;
    font-weight: 800;
    color: #17152f;
    margin-bottom: 0.15rem;
    letter-spacing: -0.7px;
}

.subtitle {
    color: #697386;
    font-size: 1rem;
    margin-bottom: 1.3rem;
}

.section-title {
    color: #17152f;
    font-size: 1.35rem;
    font-weight: 750;
    margin: 1.1rem 0 .7rem;
}

/* ---------- SIDEBAR ---------- */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #f8fafc 0%, #eef2ff 52%, #f8fafc 100%) !important;
    border-right: 1px solid #e2e8f0 !important;
}
[data-testid="stSidebar"] > div:first-child,
[data-testid="stSidebarContent"] { background: transparent !important; }

[data-testid="stSidebar"] .stButton > button {
    width: 100%;
    background: rgba(255,255,255,.78) !important;
    color: #334155 !important;
    border: 1px solid transparent !important;
    border-radius: 14px !important;
    text-align: left !important;
    font-weight: 650 !important;
    padding: 12px 14px !important;
    margin: 4px 0 !important;
    box-shadow: 0 2px 8px rgba(15,23,42,.03) !important;
    transition: all .2s ease !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background: linear-gradient(90deg, #eef2ff, #ffffff) !important;
    color: #4338ca !important;
    border-color: #c7d2fe !important;
    transform: translateX(4px);
    box-shadow: 0 5px 14px rgba(79,70,229,.10) !important;
}
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3,
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] label { color: #334155 !important; }

.sidebar-logo {
    text-align: left;
    font-size: 1.38rem;
    font-weight: 850;
    color: #172554 !important;
    padding: .65rem .15rem .15rem;
    letter-spacing: -.4px;
}
.sidebar-subtitle {
    color: #64748b !important;
    font-size: .78rem;
    margin: 0 0 1rem .15rem;
}
.sidebar-mini {
    background: rgba(255,255,255,.9) !important;
    color: #334155 !important;
    border: 1px solid #e2e8f0 !important;
    border-radius: 18px;
    padding: 15px;
    margin-top: 14px;
    box-shadow: 0 8px 24px rgba(15,23,42,.07);
}
.sidebar-mini * { color: #334155 !important; }
[data-testid="stSidebar"] hr { border-color: #e2e8f0 !important; }

.main-title {
    font-size: 2.25rem;
    font-weight: 850;
    letter-spacing: -1.2px;
    color: #172554;
    margin-bottom: .15rem;
}
.main-subtitle {
    color: #64748b;
    font-size: 1rem;
    margin-bottom: 1.25rem;
}
.hero-card {
    position: relative;
    overflow: hidden;
    border-radius: 24px;
    padding: 28px 30px;
    margin: 4px 0 22px;
    background: linear-gradient(120deg, #4338ca 0%, #6366f1 55%, #818cf8 100%);
    color: white;
    box-shadow: 0 16px 36px rgba(67,56,202,.22);
}
.hero-card:after {
    content: "";
    position: absolute;
    width: 210px;
    height: 210px;
    right: -65px;
    top: -90px;
    border-radius: 50%;
    background: rgba(255,255,255,.13);
}
.hero-card h2 { margin: 0; font-size: 1.9rem; }
.hero-card p { margin: 7px 0 0; color: rgba(255,255,255,.86); }

.metric-card {
    background: rgba(255,255,255,.96);
    border: 1px solid #e2e8f0;
    border-radius: 20px;
    padding: 20px;
    min-height: 125px;
    box-shadow: 0 8px 24px rgba(15,23,42,.055);
    transition: transform .2s ease, box-shadow .2s ease;
}
.metric-card:hover {
    transform: translateY(-3px);
    box-shadow: 0 14px 30px rgba(15,23,42,.09);
}
.metric-icon { font-size: 1.65rem; }
.metric-label { color: #64748b; font-size: .82rem; margin-top: 8px; }
.metric-value { color: #172554; font-size: 1.55rem; font-weight: 800; margin-top: 2px; }

.section-card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 20px;
    padding: 22px;
    box-shadow: 0 7px 22px rgba(15,23,42,.045);
    margin-bottom: 16px;
}
.section-card h3 { color: #172554; margin: 0 0 5px; font-size: 1.08rem; }
.section-card .muted { color: #64748b; font-size: .86rem; }

.progress-ring {
    width: 126px;
    height: 126px;
    border-radius: 50%;
    background: conic-gradient(#4f46e5 0deg, #818cf8 280deg, #e2e8f0 280deg 360deg);
    display: flex;
    align-items: center;
    justify-content: center;
    margin: 8px auto 12px;
}
.progress-ring-inner {
    width: 94px;
    height: 94px;
    border-radius: 50%;
    background: white;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-direction: column;
}
.progress-number { font-size: 1.45rem; font-weight: 850; color: #172554; }
.progress-caption { font-size: .68rem; color: #64748b; }

#MainMenu {visibility: hidden;}
footer {visibility: hidden;}""",
    unsafe_allow_html=True,
)


# =========================================================
# PDF PROCESSING & RAG
# =========================================================
try:
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    from langchain.vectorstores import FAISS
    from langchain_google_genai import GoogleGenerativeAIEmbeddings

    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False


os.makedirs("uploads", exist_ok=True)


def process_uploaded_pdf(uploaded_file):
    """Extract PDF text and create a RAG vector store when available."""
    try:
        text = extract_text_from_pdf(uploaded_file)

        if text and text.strip():
            st.session_state.pdf_text += (
                f"\n\n--- {uploaded_file.name} ---\n{text}"
            )

        if LANGCHAIN_AVAILABLE and text and text.strip():
            try:
                api_key = st.secrets.get("GEMINI_API_KEY", "")

                if api_key:
                    splitter = RecursiveCharacterTextSplitter(
                        chunk_size=1000,
                        chunk_overlap=200,
                    )
                    chunks = splitter.create_documents([text])

                    embeddings = GoogleGenerativeAIEmbeddings(
                        model="models/embedding-001",
                        google_api_key=api_key,
                    )

                    st.session_state.vector_store = FAISS.from_documents(
                        chunks, embeddings
                    )
            except Exception as e:
                st.warning(f"RAG setup skipped: {e}")

        return text or ""

    except Exception as e:
        st.error(f"Error processing PDF: {e}")
        return ""


# =========================================================
# SIDEBAR
# =========================================================
with st.sidebar:
    st.markdown(
        """
        <div class="sidebar-logo">🎓 AI College Assistant</div><div class="sidebar-subtitle">Your intelligent study companion</div>
        <div style="font-size:.82rem;color:#64748b!important;margin-bottom:14px;">
            Your Smart Academic Companion
        </div>
        """,
        unsafe_allow_html=True,
    )

    pages = [
        ("dashboard", "🏠 Dashboard"),
        ("pdf_upload", "📄 Study Materials"),
        ("smart_chat", "💬 Smart Chat"),
        ("summarizer", "📝 Summarizer"),
        ("mcq_generator", "✅ MCQ Generator"),
        ("important_questions", "❓ Important Questions"),
        ("study_plan", "📅 Study Planner"),
        ("settings", "⚙️ Student Profile"),
    ]

    for key, label in pages:
        if st.button(
            label,
            key=f"nav_{key}",
            use_container_width=True,
        ):
            st.session_state.page = key
            st.rerun()

    st.markdown("---")

    st.markdown(
        f"""
        <div class="sidebar-mini">
            <div style="font-size:.8rem;opacity:.75;">SIGNED IN AS</div>
            <div style="font-size:1.05rem;font-weight:750;margin-top:4px;">
                {safe_html(name)}
            </div>
            <div style="font-size:.8rem;opacity:.75;margin-top:3px;">
                {safe_html(branch)}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# =========================================================
# PAGE 1 — DASHBOARD
if st.session_state.page == "dashboard":
    today = date.today()
    display_name = name.strip() if name and name.strip() else "Student"
    days_left = max((exam_date - today).days, 0) if exam_date else 0

    tasks = st.session_state.get("tasks", [])
    if not isinstance(tasks, list):
        tasks = []

    total_tasks = len(tasks)
    completed_tasks = sum(
        1 for t in tasks
        if isinstance(t, dict)
        and str(t.get("status", "")).lower() in {"done", "completed", "complete"}
    )
    task_progress = round((completed_tasks / total_tasks) * 100) if total_tasks else 72

    st.markdown(
        f"""
        <div class="dash-welcome">
            <div class="hello">Hello, {safe_html(display_name)}! 👋</div>
            <div class="date">{today.strftime("%A, %d %B %Y")} • Your personal academic command center</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    stats = st.columns(4)
    stat_data = [
        ("🔥", "Study streak", "7 days", "Keep the momentum"),
        ("⏳", "Exam countdown", f"{days_left} days", "Stay consistent"),
        ("✅", "Tasks completed", f"{completed_tasks}/{total_tasks}" if total_tasks else "0", "Today's progress"),
        ("📈", "Overall progress", f"{task_progress}%", "Learning journey"),
    ]

    for col, (icon, label, value, hint) in zip(stats, stat_data):
        with col:
            st.markdown(
                f"""
                <div class="stat-tile">
                    <div class="icon">{icon}</div>
                    <div class="label">{label}</div>
                    <div class="value">{value}</div>
                    <div class="hint">{hint}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown('<div class="dash-section-title">Today at a glance</div>', unsafe_allow_html=True)
    left, right = st.columns([1.7, 1])

    with left:
        st.markdown(
            """
            <div class="panel">
                <div class="panel-title">🎯 Today's Focus</div>
                <div class="panel-subtitle">Your most important study session</div>
                <div class="focus-card">
                    <div class="small">RECOMMENDED FOCUS</div>
                    <div class="subject">📚 Deep Study Session</div>
                    <div class="time">45 minutes • One topic • Zero distractions</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("### ")
        st.markdown('<div class="panel"><div class="panel-title">⚡ Quick Actions</div><div class="panel-subtitle">Jump directly into your study tools</div>', unsafe_allow_html=True)
        qa = st.columns(4)
        quick_actions = [
            ("🤖", "Smart Chat", "smart_chat"),
            ("📝", "Generate MCQ", "mcq_generator"),
            ("📄", "Summarize", "summarizer"),
            ("🎯", "Important Qs", "important_questions"),
        ]
        for col, (icon, label, target) in zip(qa, quick_actions):
            with col:
                if st.button(f"{icon} {label}", use_container_width=True):
                    st.session_state.page = target
                    st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        st.markdown(
            """
            <div class="ai-panel">
                <div class="ai-title">🤖 AI Coach</div>
                <div class="ai-text">
                    Based on your learning activity, start with one focused
                    revision session and then test yourself with MCQs.
                </div>
                <br><span class="badge">Personalized recommendation</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("### ")
        st.markdown(
            """
            <div class="panel">
                <div class="panel-title">📅 Upcoming</div>
                <div class="panel-subtitle">Your next academic actions</div>
                <div class="event-card">
                    <div class="event-title">🧠 Study Planner</div>
                    <div class="event-meta">Review today's tasks and priorities</div>
                </div>
                <div class="event-card">
                    <div class="event-title">📚 Revision</div>
                    <div class="event-meta">Use Smart Chat to clear doubts</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown('<div class="dash-section-title">📚 My Learning Progress</div>', unsafe_allow_html=True)
    subjects = [
        ("DBMS", "Database Management", 78),
        ("OOP", "Object Oriented Programming", 68),
        ("DSU", "Data Structures", 61),
        ("DTE", "Digital Techniques", 52),
    ]

    subject_cols = st.columns(4)
    for col, (short_name, full_name, progress) in zip(subject_cols, subjects):
        with col:
            st.markdown(
                f"""
                <div class="subject-card">
                    <div class="subject-name">{short_name}</div>
                    <div class="subject-meta">{full_name}</div>
                    <div style="display:flex;justify-content:space-between;font-size:.73rem;color:#64748b;">
                        <span>Progress</span><b>{progress}%</b>
                    </div>
                    <div class="progress-line">
                        <div class="progress-fill" style="width:{progress}%"></div>
                    </div>
                    <span class="badge">Keep improving</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown('<div class="dash-section-title">🚀 Your Study Journey</div>', unsafe_allow_html=True)
    journey_left, journey_right = st.columns([1, 2])

    with journey_left:
        degree = int(task_progress * 3.6)
        st.markdown(
            f"""
            <div class="panel" style="text-align:center;">
                <div class="panel-title">Weekly Progress</div>
                <div class="progress-ring" style="background:conic-gradient(#4f46e5 0deg, #8b5cf6 {degree}deg, #e2e8f0 {degree}deg 360deg);">
                    <div class="progress-ring-inner">
                        <div class="progress-number">{task_progress}%</div>
                        <div class="progress-caption">COMPLETED</div>
                    </div>
                </div>
                <div style="color:#64748b;font-size:.78rem;">Small steps every day create big results.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with journey_right:
        st.markdown(
            """
            <div class="panel">
                <div class="panel-title">🏆 Achievements</div>
                <div class="panel-subtitle">Milestones for your learning journey</div>
                <div class="event-card">
                    <div class="event-title">🔥 Consistency Starter</div>
                    <div class="event-meta">Study regularly and build your streak</div>
                </div>
                <div class="event-card">
                    <div class="event-title">🧠 Quiz Master</div>
                    <div class="event-meta">Practice with generated MCQs</div>
                </div>
                <div class="event-card">
                    <div class="event-title">🎯 Exam Ready</div>
                    <div class="event-meta">Complete your planned revision targets</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

# PAGE 2 — PDF UPLOAD
# PAGE 2 — PDF UPLOAD
# =========================================================
elif st.session_state.page == "pdf_upload":
    st.markdown('<h1 class="main-title">📄 Study Materials</h1>', unsafe_allow_html=True)
    st.markdown(
        '<p class="subtitle">Upload lecture notes and PDFs to power your AI learning tools.</p>',
        unsafe_allow_html=True,
    )
    render_back_button()

    uploaded = st.file_uploader(
        "Choose PDF files",
        type=["pdf"],
        accept_multiple_files=True,
    )

    if uploaded:
        for file in uploaded:
            existing_names = [f.name for f in st.session_state.uploaded_files]

            if file.name not in existing_names:
                st.session_state.uploaded_files.append(file)
                text = process_uploaded_pdf(file)

                with open(os.path.join("uploads", os.path.basename(file.name)), "wb") as f:
                    f.write(file.getbuffer())

                st.success(
                    f"Processed: {file.name} ({len(text):,} characters)"
                )

    if st.session_state.uploaded_files:
        st.markdown("### 📚 Your Uploaded Files")

        for file in st.session_state.uploaded_files:
            st.markdown(
                f"""
                <div class="card">
                    📄 <b>{safe_html(file.name)}</b>
                    <span style="color:#73798a;">
                    • {file.size / 1024:.1f} KB
                    </span>
                </div>
                """,
                unsafe_allow_html=True,
            )

        if st.button("🗑️ Clear All Files"):
            st.session_state.uploaded_files = []
            st.session_state.pdf_text = ""
            st.session_state.vector_store = None
            st.rerun()

        if LANGCHAIN_AVAILABLE and st.session_state.vector_store:
            st.success("RAG vector store is ready for Smart Chat.")


# =========================================================
# PAGE 3 — SMART CHAT
# =========================================================
elif st.session_state.page == "smart_chat":
    st.markdown('<h1 class="main-title">💬 Smart Chat</h1>', unsafe_allow_html=True)
    st.markdown(
        '<p class="subtitle">Ask questions about your uploaded study materials.</p>',
        unsafe_allow_html=True,
    )
    render_back_button()

    if not st.session_state.uploaded_files:
        st.warning("Please upload PDFs first from Study Materials.")
    else:
        for msg in st.session_state.rag_chat:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        if prompt := st.chat_input("Ask anything about your uploaded notes..."):
            st.session_state.rag_chat.append(
                {"role": "user", "content": prompt}
            )

            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                with st.spinner("🔍 Searching your documents..."):
                    try:
                        if st.session_state.vector_store:
                            response = answer_question(
                                st.session_state.vector_store,
                                prompt,
                            )
                        else:
                            response = ask_ollama(
                                "Answer based on this study material:\n"
                                f"{st.session_state.pdf_text}\n\n"
                                f"Question: {prompt}"
                            )
                    except Exception as e:
                        response = f"AI response failed: {e}"

                    st.markdown(response)
                    save_chat(prompt, response)

            st.session_state.rag_chat.append(
                {"role": "assistant", "content": response}
            )


# =========================================================
# PAGE 4 — SUMMARIZER
# =========================================================
elif st.session_state.page == "summarizer":
    st.markdown('<h1 class="main-title">📝 Study Notes Summarizer</h1>', unsafe_allow_html=True)
    st.markdown(
        '<p class="subtitle">Turn long study materials into concise revision notes.</p>',
        unsafe_allow_html=True,
    )
    render_back_button()

    if not st.session_state.uploaded_files:
        st.warning("Please upload PDFs first.")
    else:
        if st.button("📝 Generate Study Notes", use_container_width=True):
            with st.spinner("Creating summary..."):
                try:
                    summary = summarize_text(st.session_state.pdf_text)
                    st.markdown(
                        f'<div class="card">{summary}</div>',
                        unsafe_allow_html=True,
                    )
                    save_chat("Generate study notes", summary)
                except Exception as e:
                    st.error(f"Summary generation failed: {e}")


# =========================================================
# PAGE 5 — MCQ GENERATOR
# =========================================================
elif st.session_state.page == "mcq_generator":
    st.markdown('<h1 class="main-title">✅ MCQ Generator</h1>', unsafe_allow_html=True)
    st.markdown(
        '<p class="subtitle">Generate practice questions from your uploaded materials.</p>',
        unsafe_allow_html=True,
    )
    render_back_button()

    if not st.session_state.uploaded_files:
        st.warning("Please upload PDFs first.")
    else:
        num_questions = st.slider(
            "Number of Questions",
            3,
            15,
            5,
        )

        if st.button("🎯 Generate MCQs", use_container_width=True):
            with st.spinner("Creating MCQs..."):
                try:
                    mcqs = generate_mcqs(
                        st.session_state.pdf_text,
                        num_questions,
                    )
                    st.markdown(
                        f'<div class="card">{mcqs}</div>',
                        unsafe_allow_html=True,
                    )
                    save_chat(
                        f"Generate {num_questions} MCQs",
                        mcqs,
                    )
                except Exception as e:
                    st.error(f"MCQ generation failed: {e}")


# =========================================================
# PAGE 6 — IMPORTANT QUESTIONS
# =========================================================
elif st.session_state.page == "important_questions":
    st.markdown('<h1 class="main-title">❓ Important Exam Questions</h1>', unsafe_allow_html=True)
    st.markdown(
        '<p class="subtitle">Generate high-priority questions for examination preparation.</p>',
        unsafe_allow_html=True,
    )
    render_back_button()

    if not st.session_state.uploaded_files:
        st.warning("Please upload PDFs first.")
    else:
        num_questions = st.slider(
            "Number of Questions",
            5,
            20,
            10,
        )

        if st.button(
            "📋 Generate Important Questions",
            use_container_width=True,
        ):
            with st.spinner("Creating exam questions..."):
                try:
                    questions = generate_important_questions(
                        st.session_state.pdf_text,
                        num_questions,
                    )
                    st.markdown(
                        f'<div class="card">{questions}</div>',
                        unsafe_allow_html=True,
                    )
                    save_chat(
                        f"Generate {num_questions} important questions",
                        questions,
                    )
                except Exception as e:
                    st.error(f"Question generation failed: {e}")


# =========================================================
# PAGE 7 — STUDY PLANNER + TASK TRACKING
# =========================================================
elif st.session_state.page == "study_plan":
    st.markdown('<h1 class="main-title">📅 Smart Study Planner</h1>', unsafe_allow_html=True)
    st.markdown(
        '<p class="subtitle">Create a structured preparation plan and track your daily tasks.</p>',
        unsafe_allow_html=True,
    )
    render_back_button()

    default_exam = exam_date or (date.today() + timedelta(days=12))

    # Never allow a past date as the default.
    if default_exam < date.today():
        default_exam = date.today() + timedelta(days=12)

    c1, c2, c3 = st.columns(3)

    with c1:
        planner_exam_date = st.date_input(
            "Exam Date",
            value=default_exam,
            min_value=date.today(),
            max_value=date.today() + timedelta(days=3650),
        )

    with c2:
        default_hours = max(1, min(8, int(study_hours) if study_hours else 3))
        hours_per_day = st.slider(
            "Study Hours / Day",
            1,
            8,
            default_hours,
        )

    with c3:
        subjects = st.multiselect(
            "Subjects",
            [
                "Data Structures",
                "Operating Systems",
                "DBMS",
                "Mathematics",
                "Computer Networks",
                "AI / ML",
                "OOP Using C++",
                "Other",
            ],
            default=["Data Structures", "DBMS"],
        )

    if st.button(
        "🎯 Generate Smart Plan",
        use_container_width=True,
    ):
        days = (planner_exam_date - date.today()).days

        if days <= 0:
            st.error("Exam date must be in the future.")
        elif not subjects:
            st.warning("Select at least one subject.")
        else:
            plan = []

            plan_days = min(days, 14)

            for day_number in range(1, plan_days + 1):
                current_date = date.today() + timedelta(days=day_number)
                subject = subjects[(day_number - 1) % len(subjects)]

                next_subject = subjects[
                    day_number % len(subjects)
                ] if len(subjects) > 1 else subject

                plan.append(
                    {
                        "day": day_number,
                        "date": current_date.strftime("%A, %d %b"),
                        "subjects": [subject, next_subject],
                        "tasks": [
                            f"Study {subject} concepts",
                            f"Practice questions from {subject}",
                            "Take a short self-review",
                        ],
                    }
                )

            st.session_state.study_plan = plan

            # Dashboard task tracker is updated from the plan.
            generated = []

            for p in plan[:7]:
                for index, task in enumerate(p["tasks"]):
                    generated.append(
                        {
                            "id": f"plan_{p['day']}_{index}",
                            "title": task,
                            "subject": ", ".join(p["subjects"]),
                        }
                    )

            st.session_state.generated_tasks = generated
            st.session_state.completed_tasks = set()

            st.success("Smart study plan generated successfully.")

    if st.session_state.study_plan:
        st.markdown("### 📚 Your Plan")

        for p in st.session_state.study_plan:
            task_text = " • ".join(p["tasks"])

            st.markdown(
                f"""
                <div class="card">
                    <div style="font-size:1.1rem;font-weight:800;color:#6d28d9;">
                        📅 Day {p['day']} — {p['date']}
                    </div>
                    <div style="margin-top:8px;">
                        <b>📚 Subjects:</b> {safe_html(", ".join(p["subjects"]))}
                    </div>
                    <div style="margin-top:7px;">
                        <b>⏱️ Duration:</b> {hours_per_day} hour(s)
                    </div>
                    <div style="margin-top:7px;">
                        <b>✅ Tasks:</b> {safe_html(task_text)}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.info(
            "Your first 7 days of tasks are also available on the Dashboard "
            "for progress tracking."
        )


# =========================================================
elif st.session_state.page == "settings":
    st.markdown('<h1 class="main-title">⚙️ Student Profile</h1>', unsafe_allow_html=True)
    st.markdown(
        '<p class="subtitle">Keep your academic information updated for a more personalized assistant.</p>',
        unsafe_allow_html=True,
    )
    render_back_button()

    st.markdown(
        """
        <div class="info-card">
            <b>🎓 Why complete your profile?</b>
            <span style="color:#73798a;">
            Your branch, semester, exam date and study goal help the
            dashboard and Study Planner provide more relevant information.
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("")

    profile_exam_default = exam_date or (date.today() + timedelta(days=12))

    if profile_exam_default < date.today():
        profile_exam_default = date.today() + timedelta(days=12)

    with st.form("profile_form"):

        p1, p2 = st.columns(2)

        with p1:
            new_name = st.text_input(
                "Student Name",
                value=name if name != "Student" else "",
            )
            new_branch = st.text_input(
                "Branch",
                value=branch,
            )
            new_semester = st.text_input(
                "Semester",
                value=semester,
            )

        with p2:
            new_college = st.text_input(
                "College",
                value=college if college != "College Not Set" else "",
            )
            new_exam_date = st.date_input(
                "Exam Date",
                value=profile_exam_default,
                min_value=date.today(),
                max_value=date.today() + timedelta(days=3650),
            )
            new_hours = st.number_input(
                "Daily Study Goal (Hours)",
                min_value=0.0,
                max_value=12.0,
                value=max(0.0, min(study_hours, 12.0)),
                step=0.5,
            )

        # Fixed typo: form_submitstre_button -> form_submit_button
        save_profile = st.form_submit_button(
    "💾 Save Student Profile",
    use_container_width=True,
)

elif st.session_state.page == "settings":

    st.markdown(
        '<h1 class="main-title">⚙️ Student Profile</h1>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<p class="subtitle">Manage your academic information and study preferences.</p>',
        unsafe_allow_html=True
    )

    # Make sure exam date is valid for Streamlit
    profile_exam_default = exam_date or (
        date.today() + timedelta(days=12)
    )

    if profile_exam_default < date.today():
        profile_exam_default = date.today() + timedelta(days=12)

    # ---------------------------------------------
    # PROFILE FORM
    # ---------------------------------------------

    with st.form("profile_form"):

        p1, p2 = st.columns(2)

        with p1:

            new_name = st.text_input(
                "👤 Student Name",
                value=name if name != "Student" else ""
            )

            new_branch = st.text_input(
                "💻 Branch",
                value=branch
            )

            new_semester = st.text_input(
                "📚 Semester",
                value=semester
            )

        with p2:

            new_college = st.text_input(
                "🏫 College",
                value=college if college != "College Not Set" else ""
            )

            new_exam_date = st.date_input(
                "📅 Exam Date",
                value=profile_exam_default,
                min_value=date.today(),
                max_value=date.today() + timedelta(days=3650)
            )

            new_hours = st.number_input(
                "⏱️ Daily Study Goal (Hours)",
                min_value=0.0,
                max_value=12.0,
                value=max(
                    0.0,
                    min(study_hours, 12.0)
                ),
                step=0.5
            )
            preferred_study_time = st.selectbox(
                "🕒 Preferred Study Time",
                ["Morning", "Afternoon", "Evening", "Night"],
                index=["Morning", "Afternoon", "Evening", "Night"].index(
                    profile.get("preferred_study_time", "Morning")
                    if profile.get("preferred_study_time", "Morning")
                    in ["Morning", "Afternoon", "Evening", "Night"]
                    else "Morning"
                )
            )

        # ---------------------------------------------
        # SAVE BUTTON
        # ---------------------------------------------

        save_profile = st.form_submit_button(
            "💾 Save Student Profile",
            use_container_width=True
        )

    # ---------------------------------------------
    # SAVE PROFILE
    # ---------------------------------------------

    if save_profile:

        if not new_name.strip():

            st.error("⚠️ Please enter your name.")

        else:

            try:

                save_student_profile(
                    new_name.strip(),
                    new_branch.strip(),
                    new_semester.strip(),
                    new_college.strip(),
                    new_exam_date.strftime("%Y-%m-%d"),
                    float(new_hours),
                    preferred_study_time
                )

                st.success(
                    "✅ Student profile saved successfully!"
                )

                # Return to dashboard
                st.session_state.page = "dashboard"

                st.rerun()

            except Exception as e:

                st.error(
                    f"❌ Could not save the profile. "
                    f"Database error: {e}"
                )