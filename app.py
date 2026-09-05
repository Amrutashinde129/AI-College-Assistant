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
    background: linear-gradient(180deg, #17132e 0%, #25164a 55%, #17132e 100%);
    border-right: 1px solid rgba(255,255,255,.08);
}

[data-testid="stSidebar"] * {
    color: #f7f4ff !important;
}

.sidebar-logo {
    text-align: center;
    font-size: 1.55rem;
    font-weight: 800;
    padding: 0.7rem 0 1.4rem;
}

.sidebar-mini {
    background: rgba(255,255,255,.09);
    border: 1px solid rgba(255,255,255,.10);
    border-radius: 16px;
    padding: 14px;
    margin-top: 12px;
}

/* ---------- BUTTONS ---------- */
.stButton > button {
    border: 0 !important;
    border-radius: 11px !important;
    font-weight: 650 !important;
    min-height: 42px !important;
    transition: .2s ease !important;
}

.stButton > button:hover {
    transform: translateY(-1px);
    box-shadow: 0 7px 18px rgba(91, 54, 170, .15);
}

/* ---------- HERO ---------- */
.hero {
    position: relative;
    overflow: hidden;
    border-radius: 24px;
    padding: 30px 34px;
    margin-bottom: 20px;
    background: linear-gradient(135deg, #21153f 0%, #54329b 55%, #7c3aed 100%);
    color: white;
    box-shadow: 0 16px 35px rgba(62, 36, 122, .20);
}

.hero:after {
    content: "";
    position: absolute;
    width: 220px;
    height: 220px;
    right: -70px;
    top: -80px;
    border-radius: 50%;
    background: rgba(255,255,255,.10);
}

.hero h1 {
    margin: 0;
    font-size: 2.2rem;
    font-weight: 800;
}

.hero p {
    margin: 8px 0 0;
    color: #eee8ff;
}

/* ---------- CARDS ---------- */
.card {
    background: rgba(255,255,255,.96);
    border: 1px solid #eceaf5;
    border-radius: 18px;
    padding: 21px;
    box-shadow: 0 8px 25px rgba(25, 22, 45, .055);
    margin-bottom: 16px;
}

.profile-card {
    background: linear-gradient(145deg, #ffffff, #f7f3ff);
    border: 1px solid #e8defb;
    border-radius: 20px;
    padding: 22px;
    box-shadow: 0 9px 28px rgba(84, 50, 155, .09);
}

.avatar {
    width: 62px;
    height: 62px;
    border-radius: 18px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: linear-gradient(135deg, #7c3aed, #a78bfa);
    color: white;
    font-size: 1.8rem;
    font-weight: 800;
    margin-bottom: 12px;
}

.profile-name {
    font-size: 1.35rem;
    font-weight: 800;
    color: #21153f;
}

.profile-meta {
    color: #6b7280;
    margin-top: 4px;
}

/* ---------- STATS ---------- */
.stat-card {
    background: white;
    border: 1px solid #eceaf5;
    border-radius: 17px;
    padding: 19px 16px;
    box-shadow: 0 7px 22px rgba(25,22,45,.045);
    min-height: 112px;
}

.stat-icon {
    font-size: 1.25rem;
}

.stat-value {
    color: #6d28d9;
    font-size: 1.85rem;
    font-weight: 800;
    margin-top: 4px;
}

.stat-label {
    color: #73798a;
    font-size: .86rem;
}

/* ---------- COUNTDOWN ---------- */
.countdown {
    background: linear-gradient(135deg, #eef2ff, #f5f3ff);
    border: 1px solid #e3def9;
    border-radius: 18px;
    padding: 21px;
    text-align: center;
}

.count-number {
    font-size: 2.45rem;
    font-weight: 850;
    color: #5b21b6;
}

.count-label {
    color: #6b7280;
    font-size: .9rem;
}

/* ---------- PROGRESS ---------- */
.progress-wrap {
    background: #eeeafa;
    height: 11px;
    border-radius: 20px;
    overflow: hidden;
    margin: 9px 0 7px;
}

.progress-fill {
    height: 100%;
    border-radius: 20px;
    background: linear-gradient(90deg, #7c3aed, #a78bfa);
}

/* ---------- TASKS ---------- */
.task {
    background: #faf9ff;
    border: 1px solid #e9e4f5;
    border-radius: 13px;
    padding: 13px 15px;
    margin-bottom: 9px;
}

.task-title {
    color: #28233c;
    font-weight: 650;
}

.task-subject {
    color: #7c3aed;
    font-size: .78rem;
    margin-top: 3px;
}

/* ---------- CHAT ---------- */
.chat-bubble {
    background: white;
    padding: 15px 17px;
    border-radius: 13px;
    border-left: 4px solid #8b5cf6;
    margin-bottom: 10px;
    box-shadow: 0 3px 12px rgba(0,0,0,.035);
}

/* ---------- INFO ---------- */
.info-card {
    background: #f8f6ff;
    border: 1px solid #e7defb;
    border-radius: 15px;
    padding: 16px;
}

.feature-card {
    background: white;
    border: 1px solid #eceaf5;
    border-radius: 17px;
    padding: 18px;
    min-height: 145px;
    box-shadow: 0 7px 20px rgba(25,22,45,.04);
}

.feature-icon {
    font-size: 1.65rem;
}

.feature-title {
    color: #29223d;
    font-weight: 750;
    margin-top: 7px;
}

.feature-text {
    color: #74798a;
    font-size: .86rem;
    margin-top: 5px;
}

/* ---------- STREAMLIT INPUTS ---------- */
div[data-baseweb="input"] > div,
div[data-baseweb="select"] > div,
textarea {
    border-radius: 10px !important;
}

[data-testid="stMetricValue"] {
    color: #6d28d9;
}

/* ---------- MOBILE ---------- */
@media (max-width: 800px) {
    .hero h1 { font-size: 1.65rem; }
    .main-title { font-size: 1.75rem; }
}
</style>
""",
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
        '<div class="sidebar-logo">🎓 AI College Assistant</div>',
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
# PAGE 1 — ATTRACTIVE DASHBOARD
# =========================================================
if st.session_state.page == "dashboard":

    exam_days = days_until_exam()
    task_progress = progress_percent()

    if not st.session_state.generated_tasks:
        st.session_state.generated_tasks = create_default_tasks()

    total_tasks = len(st.session_state.generated_tasks)
    completed_tasks = len(st.session_state.completed_tasks)

    st.markdown(
        f"""
        <div class="hero">
            <h1>Welcome back, {safe_html(name)}! 👋</h1>
            <p>Your AI-powered academic workspace — plan smarter, learn faster,
            and stay ready for your exams.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Top statistics
    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.markdown(
            f"""
            <div class="stat-card">
                <div class="stat-icon">⏱️</div>
                <div class="stat-value">{study_hours:g}h</div>
                <div class="stat-label">Daily Study Goal</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c2:
        st.markdown(
            f"""
            <div class="stat-card">
                <div class="stat-icon">📚</div>
                <div class="stat-value">{len(st.session_state.uploaded_files)}</div>
                <div class="stat-label">Study Materials</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c3:
        countdown_text = "—" if exam_days is None else max(exam_days, 0)
        st.markdown(
            f"""
            <div class="stat-card">
                <div class="stat-icon">🎯</div>
                <div class="stat-value">{countdown_text}</div>
                <div class="stat-label">Days Until Exam</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c4:
        st.markdown(
            f"""
            <div class="stat-card">
                <div class="stat-icon">✅</div>
                <div class="stat-value">{completed_tasks}/{total_tasks}</div>
                <div class="stat-label">Tasks Completed</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("")

    # Profile + countdown + progress
    left, right = st.columns([1.15, 1.85])

    with left:
        st.markdown(
            f"""
            <div class="profile-card">
                <div class="avatar">{safe_html(name[:1].upper())}</div>
                <div class="profile-name">{safe_html(name)}</div>
                <div class="profile-meta">💻 {safe_html(branch)}</div>
                <div class="profile-meta">🎓 {safe_html(semester)}</div>
                <div class="profile-meta">🏫 {safe_html(college)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.button("⚙️ Edit Student Profile", use_container_width=True):
            st.session_state.page = "settings"
            st.rerun()

    with right:
        if exam_days is None:
            st.markdown(
                """
                <div class="countdown">
                    <div class="count-label">EXAM COUNTDOWN</div>
                    <div class="count-number">📅</div>
                    <div class="count-label">
                        Set your exam date in Student Profile
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        elif exam_days < 0:
            st.markdown(
                f"""
                <div class="countdown">
                    <div class="count-label">EXAM STATUS</div>
                    <div class="count-number">🎉</div>
                    <div class="count-label">
                        Your exam date was {abs(exam_days)} day(s) ago.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f"""
                <div class="countdown">
                    <div class="count-label">EXAM COUNTDOWN</div>
                    <div class="count-number">{exam_days}</div>
                    <div class="count-label">
                        days remaining • {exam_date.strftime("%d %b %Y")}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown(
            f"""
            <div class="card">
                <b>📈 Today's Progress</b>
                <div class="progress-wrap">
                    <div class="progress-fill" style="width:{task_progress}%"></div>
                </div>
                <div style="display:flex;justify-content:space-between;color:#73798a;font-size:.85rem;">
                    <span>{completed_tasks} completed</span>
                    <span>{task_progress}%</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Today's tasks
    st.markdown('<div class="section-title">📌 Today\'s Study Tasks</div>', unsafe_allow_html=True)

    task_col, action_col = st.columns([2.3, 1])

    with task_col:
        for task in st.session_state.generated_tasks:
            task_id = task["id"]
            checked = task_id in st.session_state.completed_tasks

            new_value = st.checkbox(
                task["title"],
                value=checked,
                key=f"dashboard_task_{task_id}",
            )

            if new_value:
                st.session_state.completed_tasks.add(task_id)
            else:
                st.session_state.completed_tasks.discard(task_id)

            st.caption(f"📘 {task['subject']}")

    with action_col:
        st.markdown(
            """
            <div class="info-card">
                <b>🤖 AI Study Coach</b>
                <p style="color:#73798a;font-size:.86rem;">
                Use the Study Planner to create a personalized plan based
                on your exam date, subjects and study hours.
                </p>
                </div>
            """,
            unsafe_allow_html=True,
        )

        if st.button("📅 Open Study Planner", use_container_width=True):
            st.session_state.page = "study_plan"
            st.rerun()

        if st.button("💬 Ask AI a Doubt", use_container_width=True):
            st.session_state.page = "smart_chat"
            st.rerun()

    # Feature shortcuts
    st.markdown('<div class="section-title">🚀 Quick Learning Tools</div>', unsafe_allow_html=True)

    f1, f2, f3, f4 = st.columns(4)

    feature_data = [
        ("📄", "Study Materials", "Upload notes and PDFs", "pdf_upload"),
        ("🧠", "Smart Chat", "Ask questions from notes", "smart_chat"),
        ("📝", "Summarizer", "Create quick revision notes", "summarizer"),
        ("✅", "MCQ Practice", "Test your preparation", "mcq_generator"),
    ]

    for col, (icon, title, desc, page_key) in zip(
        [f1, f2, f3, f4], feature_data
    ):
        with col:
            st.markdown(
                f"""
                <div class="feature-card">
                    <div class="feature-icon">{icon}</div>
                    <div class="feature-title">{title}</div>
                    <div class="feature-text">{desc}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button(
                f"Open {title}",
                key=f"quick_{page_key}",
                use_container_width=True,
            ):
                st.session_state.page = page_key
                st.rerun()

    # Recent conversations
    st.markdown('<div class="section-title">💬 Recent AI Activity</div>', unsafe_allow_html=True)

    if history:
        for q, a, chat_date in history:
            question = safe_html(str(q)[:110])
            st.markdown(
                f"""
                <div class="chat-bubble">
                    <strong>Q:</strong> {question}
                    <br>
                    <small style="color:#73798a;">{safe_html(chat_date)}</small>
                </div>
                """,
                unsafe_allow_html=True,
            )
    else:
        st.info("No recent AI conversations yet. Start with Smart Chat!")


# =========================================================
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

                with open(os.path.join("uploads", file.name), "wb") as f:
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
# PAGE 8 — STUDENT PROFILE / SETTINGS
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
                    float(new_hours)
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