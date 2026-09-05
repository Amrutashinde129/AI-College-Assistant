
import streamlit as st
import os
from datetime import datetime, date, timedelta

# =========================================================
# IMPORTS
# =========================================================
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
            exam_date = datetime.strptime(
                str(raw_exam_date),
                "%Y-%m-%d"
            ).date()
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
# HELPERS
# =========================================================
def safe_html(value):
    """Prevent profile/PDF names from breaking HTML."""
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def days_until_exam():
    if not exam_date:
        return None

    return (exam_date - date.today()).days


def progress_percent():
    tasks = st.session_state.get("generated_tasks", [])

    if not tasks:
        return 0

    completed = len(
        st.session_state.get("completed_tasks", set())
    )

    return min(
        100,
        int((completed / len(tasks)) * 100)
    )


def create_default_tasks():
    return [
        {
            "id": "task_1",
            "title": "Review today's lecture notes",
            "subject": branch,
        },
        {
            "id": "task_2",
            "title": "Practice 10 important questions",
            "subject": "Exam Preparation",
        },
        {
            "id": "task_3",
            "title": "Complete one focused study session",
            "subject": "Study Goal",
        },
        {
            "id": "task_4",
            "title": "Ask AI Assistant one doubt",
            "subject": "Smart Learning",
        },
    ]


def go_to(page):
    """Reliable Streamlit navigation."""
    st.session_state.page = page
    st.rerun()


def render_back_button():
    st.markdown("<br>", unsafe_allow_html=True)

    if st.button(
        "⬅️ Back to Dashboard",
        key=f"back_{st.session_state.page}",
        use_container_width=False,
    ):
        go_to("dashboard")

    st.markdown("<br>", unsafe_allow_html=True)


# =========================================================
# UI / CSS
# =========================================================
st.markdown(
    """
<style>

#MainMenu {
    visibility: hidden;
}

header {
    visibility: hidden;
}

footer {
    visibility: hidden;
}

.stApp {
    background: #f8fafc;
}

.block-container {
    max-width: 1450px;
    padding-top: 1.5rem;
    padding-bottom: 3rem;
}

/* =====================================================
   TYPOGRAPHY
===================================================== */

.main-title {
    font-size: 2.25rem;
    font-weight: 800;
    color: #1e293b;
    margin-bottom: 0.15rem;
}

.subtitle {
    color: #64748b;
    font-size: 1rem;
    margin-bottom: 1.3rem;
}


/* =====================================================
   SIDEBAR
===================================================== */

[data-testid="stSidebar"] {
    background: #ffffff !important;
    border-right: 1px solid #e2e8f0 !important;
}

[data-testid="stSidebar"] .stButton > button {
    width: 100%;
    background: #f1f5f9 !important;
    color: #475569 !important;
    border: 1px solid transparent !important;
    border-radius: 12px !important;
    text-align: left !important;
    font-weight: 600 !important;
    padding: 12px 14px !important;
    margin: 4px 0 !important;
    transition: all .2s ease !important;
}

[data-testid="stSidebar"] .stButton > button:hover {
    background: #e2e8f0 !important;
    color: #4f46e5 !important;
    transform: translateX(2px);
}

[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] label {
    color: #334155 !important;
}

.sidebar-logo {
    text-align: left;
    font-size: 1.4rem;
    font-weight: 800;
    color: #4f46e5 !important;
    padding: .65rem .15rem .15rem;
}

.sidebar-subtitle {
    color: #94a3b8 !important;
    font-size: .8rem;
    margin: 0 0 1rem .15rem;
}

.sidebar-mini {
    background: #f8fafc !important;
    color: #334155 !important;
    border: 1px solid #e2e8f0 !important;
    border-radius: 12px;
    padding: 15px;
    margin-top: 14px;
}


/* =====================================================
   DASHBOARD HEADER
===================================================== */

.dash-header {
    background: linear-gradient(
        135deg,
        #4f46e5 0%,
        #7c3aed 100%
    );

    border-radius: 24px;
    padding: 32px;
    color: white;
    margin-bottom: 30px;

    box-shadow:
        0 20px 25px -5px
        rgba(79, 70, 229, 0.15);

    position: relative;
    overflow: hidden;
}

.dash-header::after {
    content: "";
    position: absolute;
    top: -50%;
    right: -10%;

    width: 300px;
    height: 300px;

    background: rgba(255,255,255,0.1);
    border-radius: 50%;
}

.dash-welcome {
    font-size: 2rem;
    font-weight: 800;
    margin-bottom: 8px;
}

.dash-date {
    opacity: 0.9;
    font-size: 1rem;
}


/* =====================================================
   STAT CARDS
===================================================== */

.stat-card {
    background: white;
    border-radius: 16px;
    padding: 20px;

    box-shadow:
        0 4px 6px -1px
        rgba(0, 0, 0, 0.05);

    border: 1px solid #f1f5f9;

    transition: transform 0.2s;
    height: 100%;
}

.stat-card:hover {
    transform: translateY(-3px);

    box-shadow:
        0 10px 15px -3px
        rgba(0, 0, 0, 0.1);
}

.stat-icon {
    font-size: 1.8rem;
    margin-bottom: 10px;
    display: block;
}

.stat-label {
    color: #64748b;
    font-size: 0.85rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.stat-value {
    color: #1e293b;
    font-size: 1.75rem;
    font-weight: 800;
    margin: 5px 0;
}

.stat-sub {
    color: #94a3b8;
    font-size: 0.8rem;
}


/* =====================================================
   SECTION
===================================================== */

.section-header {
    font-size: 1.25rem;
    font-weight: 700;
    color: #1e293b;

    margin: 30px 0 15px 0;

    display: flex;
    align-items: center;
    gap: 10px;
}


/* =====================================================
   PDF UPLOAD HERO
===================================================== */

.pdf-upload-card {
    background: linear-gradient(
        135deg,
        #eef2ff 0%,
        #f5f3ff 100%
    );

    border: 2px dashed #818cf8;

    border-radius: 20px;

    padding: 28px;

    margin-bottom: 20px;

    box-shadow:
        0 8px 20px
        rgba(79, 70, 229, 0.08);
}

.pdf-upload-icon {
    font-size: 2.8rem;
    margin-bottom: 8px;
}

.pdf-upload-title {
    font-size: 1.35rem;
    font-weight: 800;
    color: #312e81;
}

.pdf-upload-text {
    color: #6366f1;
    margin-top: 5px;
    font-size: .92rem;
}

.pdf-feature {
    background: white;
    border-radius: 14px;
    padding: 15px;

    border: 1px solid #e0e7ff;

    height: 100%;
}

.pdf-feature-icon {
    font-size: 1.5rem;
}

.pdf-feature-title {
    font-weight: 700;
    color: #1e293b;
    margin-top: 5px;
}

.pdf-feature-text {
    color: #64748b;
    font-size: .8rem;
    margin-top: 4px;
}


/* =====================================================
   FOCUS CARD
===================================================== */

.focus-card {
    background: linear-gradient(
        135deg,
        #fff1f2 0%,
        #ffe4e6 100%
    );

    border: 1px solid #fecdd3;
    border-radius: 16px;

    padding: 24px;
    color: #be123c;
}

.focus-title {
    font-weight: 800;
    font-size: 1.2rem;
    margin-bottom: 5px;
}

.focus-desc {
    opacity: 0.8;
    font-size: 0.95rem;
}


/* =====================================================
   QUICK ACTIONS
===================================================== */

.action-card {
    background: white;

    border: 1px solid #e2e8f0;

    border-radius: 14px;

    padding: 16px;

    text-align: center;

    min-height: 95px;

    transition: all 0.2s;
}

.action-card:hover {
    border-color: #818cf8;
    background: #eef2ff;
    transform: translateY(-2px);
}

.action-icon {
    font-size: 1.5rem;
    display: block;
}

.action-label {
    font-weight: 650;
    color: #334155;
    font-size: 0.85rem;
    margin-top: 6px;
}


/* =====================================================
   TASK
===================================================== */

.task-item {
    background: white;

    border: 1px solid #f1f5f9;

    border-radius: 12px;

    padding: 15px;

    margin-bottom: 10px;

    display: flex;
    align-items: center;
    justify-content: space-between;
}

.task-content {
    flex-grow: 1;
}

.task-title {
    font-weight: 600;
    color: #1e293b;
    font-size: 0.95rem;
}

.task-subject {
    font-size: 0.8rem;
    color: #64748b;
    margin-top: 2px;
}


/* =====================================================
   SUBJECT CARD
===================================================== */

.subject-card {
    background: white;

    border-radius: 16px;

    padding: 20px;

    border: 1px solid #f1f5f9;

    box-shadow:
        0 2px 4px
        rgba(0,0,0,0.02);

    margin-bottom: 12px;
}

.subject-name {
    font-weight: 800;
    color: #1e293b;
    font-size: 1.1rem;
}

.subject-full {
    color: #64748b;
    font-size: 0.85rem;
    margin-bottom: 12px;
}

.progress-bar-bg {
    background: #f1f5f9;

    height: 8px;

    border-radius: 4px;

    overflow: hidden;

    margin-bottom: 8px;
}

.progress-bar-fill {
    height: 100%;

    background: linear-gradient(
        90deg,
        #4f46e5,
        #818cf8
    );

    border-radius: 4px;
}

.progress-text {
    font-size: 0.8rem;
    color: #64748b;
    text-align: right;
}


/* =====================================================
   GENERAL CARD
===================================================== */

.card {
    background: white;

    border: 1px solid #e2e8f0;

    border-radius: 16px;

    padding: 20px;

    margin-bottom: 15px;

    box-shadow:
        0 2px 4px
        rgba(0,0,0,0.02);
}

.info-card {
    background: #eff6ff;

    border: 1px solid #dbeafe;

    border-radius: 12px;

    padding: 15px;

    color: #1e40af;

    margin-bottom: 20px;
}


/* =====================================================
   FILE CARD
===================================================== */

.file-card {
    background: white;

    border: 1px solid #e2e8f0;

    border-radius: 14px;

    padding: 15px;

    margin-bottom: 10px;

    display: flex;
    align-items: center;
    justify-content: space-between;
}

.file-name {
    font-weight: 700;
    color: #1e293b;
}

.file-meta {
    color: #64748b;
    font-size: .8rem;
}


/* =====================================================
   BUTTONS
===================================================== */

.stButton > button {
    border-radius: 10px !important;
    font-weight: 650 !important;
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


# Create uploads directory
os.makedirs("uploads", exist_ok=True)


def process_uploaded_pdf(uploaded_file):
    """
    Extract PDF text and create RAG vector store.
    """

    try:
        text = extract_text_from_pdf(uploaded_file)

        if text and text.strip():

            st.session_state.pdf_text += (
                f"\n\n--- {uploaded_file.name} ---\n{text}"
            )

        # -------------------------------------------------
        # RAG
        # -------------------------------------------------

        if LANGCHAIN_AVAILABLE and text and text.strip():

            try:
                api_key = st.secrets.get(
                    "GEMINI_API_KEY",
                    ""
                )

                if api_key:

                    splitter = RecursiveCharacterTextSplitter(
                        chunk_size=1000,
                        chunk_overlap=200,
                    )

                    chunks = splitter.create_documents(
                        [text]
                    )

                    embeddings = GoogleGenerativeAIEmbeddings(
                        model="models/embedding-001",
                        google_api_key=api_key,
                    )

                    new_store = FAISS.from_documents(
                        chunks,
                        embeddings
                    )

                    # If another vector store already exists,
                    # merge the new PDF into it.
                    if st.session_state.vector_store:

                        try:
                            st.session_state.vector_store.merge_from(
                                new_store
                            )
                        except Exception:
                            st.session_state.vector_store = new_store

                    else:
                        st.session_state.vector_store = new_store

            except Exception as e:

                st.warning(
                    f"RAG setup skipped: {e}"
                )

        return text or ""

    except Exception as e:

        st.error(
            f"Error processing PDF: {e}"
        )

        return ""


# =========================================================
# SIDEBAR NAVIGATION
# =========================================================
with st.sidebar:

    st.markdown(
        """
        <div class="sidebar-logo">
            🎓 AI College Assistant
        </div>

        <div class="sidebar-subtitle">
            Your intelligent study companion
        </div>

        <div style="
            font-size:.82rem;
            color:#64748b!important;
            margin-bottom:14px;
        ">
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
            go_to(key)

    st.markdown("---")

    st.markdown(
        f"""
        <div class="sidebar-mini">

            <div style="
                font-size:.8rem;
                opacity:.75;
            ">
                SIGNED IN AS
            </div>

            <div style="
                font-size:1.05rem;
                font-weight:750;
                margin-top:4px;
            ">
                {safe_html(name)}
            </div>

            <div style="
                font-size:.8rem;
                opacity:.75;
                margin-top:3px;
            ">
                {safe_html(branch)}
            </div>

        </div>
        """,
        unsafe_allow_html=True,
    )


# =========================================================
# PAGE 1 — DASHBOARD
# =========================================================
if st.session_state.page == "dashboard":

    today = date.today()

    display_name = (
        name.strip()
        if name and name.strip()
        else "Student"
    )

    days_left = (
        max((exam_date - today).days, 0)
        if exam_date
        else 0
    )

    # -----------------------------------------------------
    # TASKS
    # -----------------------------------------------------

    tasks = st.session_state.get(
        "generated_tasks",
        []
    )

    if not isinstance(tasks, list) or not tasks:

        tasks = create_default_tasks()

        st.session_state.generated_tasks = tasks

    total_tasks = len(tasks)

    completed_count = len(
        st.session_state.get(
            "completed_tasks",
            set()
        )
    )

    task_progress = (
        round(
            (completed_count / total_tasks) * 100
        )
        if total_tasks
        else 0
    )

    # -----------------------------------------------------
    # HERO
    # -----------------------------------------------------

    st.markdown(
        f"""
        <div class="dash-header">

            <div class="dash-welcome">
                Hello, {safe_html(display_name)}! 👋
            </div>

            <div class="dash-date">
                📅 {today.strftime('%A, %d %B %Y')}
                •
                🎯 Your personal academic command center
            </div>

        </div>
        """,
        unsafe_allow_html=True,
    )

    # -----------------------------------------------------
    # STATISTICS
    # -----------------------------------------------------

    stats_cols = st.columns(4)

    stat_data = [
        {
            "icon": "🔥",
            "label": "Study Streak",
            "value": "7 days",
            "sub": "Keep momentum",
            "color": "#f59e0b",
        },
        {
            "icon": "⏳",
            "label": "Exam Countdown",
            "value": f"{days_left} days",
            "sub": "Stay consistent",
            "color": "#3b82f6",
        },
        {
            "icon": "📄",
            "label": "Study Materials",
            "value": str(
                len(
                    st.session_state.uploaded_files
                )
            ),
            "sub": "PDFs uploaded",
            "color": "#6366f1",
        },
        {
            "icon": "📈",
            "label": "Overall Progress",
            "value": f"{task_progress}%",
            "sub": "Learning journey",
            "color": "#10b981",
        },
    ]

    for col, data in zip(
        stats_cols,
        stat_data
    ):

        with col:

            st.markdown(
                f"""
                <div class="stat-card"
                     style="
                     border-top:4px solid
                     {data['color']};
                     ">

                    <span class="stat-icon">
                        {data['icon']}
                    </span>

                    <div class="stat-label">
                        {data['label']}
                    </div>

                    <div class="stat-value">
                        {data['value']}
                    </div>

                    <div class="stat-sub">
                        {data['sub']}
                    </div>

                </div>
                """,
                unsafe_allow_html=True,
            )

    # =====================================================
    # IMPORTANT PDF UPLOAD SECTION
    # =====================================================

    st.markdown(
        '<div class="section-header">'
        '📄 Study Materials'
        '</div>',
        unsafe_allow_html=True,
    )

    pdf_left, pdf_right = st.columns(
        [2.2, 1]
    )

    with pdf_left:

        st.markdown(
            """
            <div class="pdf-upload-card">

                <div class="pdf-upload-icon">
                    📚
                </div>

                <div class="pdf-upload-title">
                    Upload Your Study Materials
                </div>

                <div class="pdf-upload-text">
                    Add lecture notes, textbooks,
                    question papers and other PDF
                    study materials to make your
                    AI Assistant smarter.
                </div>

            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.button(
            "📄 Upload PDF / Study Material",
            key="dashboard_pdf_upload",
            use_container_width=True,
            type="primary",
        ):
            go_to("pdf_upload")

    with pdf_right:

        st.markdown(
            """
            <div class="pdf-feature">

                <div class="pdf-feature-icon">
                    🤖
                </div>

                <div class="pdf-feature-title">
                    What can AI do?
                </div>

                <div class="pdf-feature-text">
                    • Ask questions from PDFs<br>
                    • Generate MCQs<br>
                    • Create summaries<br>
                    • Generate important questions
                </div>

            </div>
            """,
            unsafe_allow_html=True,
        )

    # =====================================================
    # MAIN CONTENT
    # =====================================================

    main_left, main_right = st.columns(
        [2, 1]
    )

    with main_left:

        # -------------------------------------------------
        # TODAY'S PRIORITY
        # -------------------------------------------------

        st.markdown(
            '<div class="section-header">'
            '🎯 Today\'s Priority'
            '</div>',
            unsafe_allow_html=True,
        )

        st.markdown(
            """
            <div class="focus-card">

                <div class="focus-title">
                    📚 Deep Study Session
                </div>

                <div class="focus-desc">
                    Recommended: 45 minutes
                    • One topic
                    • Zero distractions
                </div>

            </div>
            """,
            unsafe_allow_html=True,
        )

        # -------------------------------------------------
        # QUICK ACTIONS
        # -------------------------------------------------

        st.markdown(
            '<div class="section-header">'
            '⚡ Quick Actions'
            '</div>',
            unsafe_allow_html=True,
        )

        action_cols = st.columns(5)

        actions = [
            (
                "📄",
                "Study Materials",
                "pdf_upload"
            ),
            (
                "🤖",
                "Smart Chat",
                "smart_chat"
            ),
            (
                "📝",
                "Summarizer",
                "summarizer"
            ),
            (
                "✅",
                "MCQ Gen",
                "mcq_generator"
            ),
            (
                "❓",
                "Important Qs",
                "important_questions"
            ),
        ]

        for col, (
            icon,
            label,
            page_name
        ) in zip(
            action_cols,
            actions
        ):

            with col:

                st.markdown(
                    f"""
                    <div class="action-card">

                        <span class="action-icon">
                            {icon}
                        </span>

                        <span class="action-label">
                            {label}
                        </span>

                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                if st.button(
                    f"Open",
                    key=f"dashboard_action_{page_name}",
                    use_container_width=True,
                ):
                    go_to(page_name)

        # -------------------------------------------------
        # TASK LIST
        # -------------------------------------------------

        st.markdown(
            '<div class="section-header">'
            '📋 Today\'s Tasks'
            '</div>',
            unsafe_allow_html=True,
        )

        for i, task in enumerate(tasks):

            task_id = task.get(
                "id",
                f"task_{i}"
            )

            is_completed = (
                task_id
                in st.session_state.completed_tasks
            )

            new_value = st.checkbox(
                task.get(
                    "title",
                    "Task"
                ),
                value=is_completed,
                key=f"check_{task_id}",
            )

            if new_value != is_completed:

                if new_value:
                    st.session_state.completed_tasks.add(
                        task_id
                    )
                else:
                    st.session_state.completed_tasks.discard(
                        task_id
                    )

                st.rerun()

            st.markdown(
                f"""
                <div class="task-item"
                     style="
                     border-left:4px solid
                     {'#10b981' if is_completed else '#cbd5e1'};
                     ">

                    <div class="task-content">

                        <div class="task-title"
                             style="
                             {'text-decoration:line-through;color:#94a3b8;'
                             if is_completed else ''}
                             ">

                            {safe_html(
                                task.get(
                                    'title',
                                    'Task'
                                )
                            )}

                        </div>

                        <div class="task-subject">
                            {safe_html(
                                task.get(
                                    'subject',
                                    ''
                                )
                            )}
                        </div>

                    </div>

                </div>
                """,
                unsafe_allow_html=True,
            )

    # =====================================================
    # RIGHT SIDE
    # =====================================================

    with main_right:

        st.markdown(
            '<div class="section-header">'
            '📚 Subject Progress'
            '</div>',
            unsafe_allow_html=True,
        )

        subjects = [
            {
                "short": "DBMS",
                "full": "Database Management",
                "prog": 78,
            },
            {
                "short": "OOP",
                "full": "Object Oriented Programming",
                "prog": 68,
            },
            {
                "short": "DSU",
                "full": "Data Structures",
                "prog": 61,
            },
            {
                "short": "DTE",
                "full": "Digital Techniques",
                "prog": 52,
            },
        ]

        for sub in subjects:

            st.markdown(
                f"""
                <div class="subject-card">

                    <div class="subject-name">
                        {sub['short']}
                    </div>

                    <div class="subject-full">
                        {sub['full']}
                    </div>

                    <div class="progress-bar-bg">

                        <div class="progress-bar-fill"
                             style="
                             width:{sub['prog']}%;
                             ">
                        </div>

                    </div>

                    <div class="progress-text">
                        {sub['prog']}% Completed
                    </div>

                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown("<br>", unsafe_allow_html=True)

        # -------------------------------------------------
        # AI TIP
        # -------------------------------------------------

        st.markdown(
            """
            <div class="info-card">

                <b>🤖 AI Coach Tip</b>
                <br><br>

                Based on your recent activity,
                try focusing on
                <b>Data Structures</b> today.

                Use the
                <b>MCQ Generator</b>
                after studying to test your knowledge.

            </div>
            """,
            unsafe_allow_html=True,
        )


# =========================================================
# PAGE 2 — PDF UPLOAD
# =========================================================
elif st.session_state.page == "pdf_upload":

    st.markdown(
        '<h1 class="main-title">'
        '📄 Study Materials'
        '</h1>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<p class="subtitle">'
        'Upload lecture notes and PDFs to power '
        'your AI learning tools.'
        '</p>',
        unsafe_allow_html=True,
    )

    render_back_button()

    # -----------------------------------------------------
    # UPLOAD AREA
    # -----------------------------------------------------

    st.markdown(
        """
        <div class="pdf-upload-card">

            <div class="pdf-upload-icon">
                📚
            </div>

            <div class="pdf-upload-title">
                Upload Study Materials
            </div>

            <div class="pdf-upload-text">
                Upload one or multiple PDF files.
                Your documents can be used for
                Smart Chat, summaries, MCQs and
                important exam questions.
            </div>

        </div>
        """,
        unsafe_allow_html=True,
    )

    uploaded = st.file_uploader(
        "Choose PDF files",
        type=["pdf"],
        accept_multiple_files=True,
        key="pdf_uploader",
    )

    # -----------------------------------------------------
    # PROCESS FILES
    # -----------------------------------------------------

    if uploaded:

        for file in uploaded:

            existing_names = [
                f.name
                for f in st.session_state.uploaded_files
            ]

            if file.name not in existing_names:

                with st.spinner(
                    f"Processing {file.name}..."
                ):

                    st.session_state.uploaded_files.append(
                        file
                    )

                    text = process_uploaded_pdf(
                        file
                    )

                    # Save physical PDF
                    safe_filename = os.path.basename(
                        file.name
                    )

                    save_path = os.path.join(
                        "uploads",
                        safe_filename
                    )

                    with open(
                        save_path,
                        "wb"
                    ) as f:

                        f.write(
                            file.getbuffer()
                        )

                st.success(
                    f"✅ Processed: {file.name} "
                    f"({len(text):,} characters)"
                )

    # -----------------------------------------------------
    # UPLOADED FILES
    # -----------------------------------------------------

    if st.session_state.uploaded_files:

        st.markdown(
            "### 📚 Your Uploaded Files"
        )

        st.info(
            f"You currently have "
            f"**{len(st.session_state.uploaded_files)} "
            f"PDF(s)** uploaded."
        )

        for index, file in enumerate(
            st.session_state.uploaded_files
        ):

            file_col, delete_col = st.columns(
                [5, 1]
            )

            with file_col:

                st.markdown(
                    f"""
                    <div class="file-card">

                        <div>

                            <div class="file-name">
                                📄 {safe_html(file.name)}
                            </div>

                            <div class="file-meta">
                                {file.size / 1024:.1f} KB
                                • PDF Study Material
                            </div>

                        </div>

                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            with delete_col:

                if st.button(
                    "🗑️",
                    key=f"delete_pdf_{index}",
                    help=f"Remove {file.name}",
                ):

                    # Remove text belonging to the file
                    marker = (
                        f"\n\n--- {file.name} ---\n"
                    )

                    if marker in st.session_state.pdf_text:

                        before, after = (
                            st.session_state.pdf_text.split(
                                marker,
                                1
                            )
                        )

                        # Remove until next PDF marker
                        if "\n\n--- " in after:

                            after = (
                                "\n\n--- "
                                + after.split(
                                    "\n\n--- ",
                                    1
                                )[1]
                            )

                        else:

                            after = ""

                        st.session_state.pdf_text = (
                            before + after
                        )

                    # Remove from session
                    st.session_state.uploaded_files.pop(
                        index
                    )

                    # Remove physical file
                    physical_path = os.path.join(
                        "uploads",
                        os.path.basename(file.name)
                    )

                    try:

                        if os.path.exists(
                            physical_path
                        ):

                            os.remove(
                                physical_path
                            )

                    except Exception:
                        pass

                    # Rebuild vector store
                    st.session_state.vector_store = None

                    st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)

        # -------------------------------------------------
        # CLEAR ALL
        # -------------------------------------------------

        if st.button(
            "🗑️ Clear All Files",
            use_container_width=True,
        ):

            for file in st.session_state.uploaded_files:

                physical_path = os.path.join(
                    "uploads",
                    os.path.basename(file.name)
                )

                try:

                    if os.path.exists(
                        physical_path
                    ):

                        os.remove(
                            physical_path
                        )

                except Exception:
                    pass

            st.session_state.uploaded_files = []
            st.session_state.pdf_text = ""
            st.session_state.vector_store = None
            st.session_state.rag_chat = []

            st.success(
                "All uploaded files cleared."
            )

            st.rerun()

        # -------------------------------------------------
        # RAG STATUS
        # -------------------------------------------------

        if (
            LANGCHAIN_AVAILABLE
            and st.session_state.vector_store
        ):

            st.success(
                "🤖 RAG vector store is ready "
                "for Smart Chat."
            )

        else:

            st.info(
                "ℹ️ PDF text extraction is ready. "
                "RAG will be used when the required "
                "embedding configuration is available."
            )

    else:

        st.markdown(
            """
            <div class="card"
                 style="
                 text-align:center;
                 padding:35px;
                 ">

                <div style="font-size:3rem;">
                    📂
                </div>

                <h3>
                    No study materials uploaded yet
                </h3>

                <p style="color:#64748b;">
                    Upload your first PDF above
                    to start learning with AI.
                </p>

            </div>
            """,
            unsafe_allow_html=True,
        )


# =========================================================
# PAGE 3 — SMART CHAT
# =========================================================
elif st.session_state.page == "smart_chat":

    st.markdown(
        '<h1 class="main-title">'
        '💬 Smart Chat'
        '</h1>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<p class="subtitle">'
        'Ask questions about your uploaded '
        'study materials.'
        '</p>',
        unsafe_allow_html=True,
    )

    render_back_button()

    if not st.session_state.uploaded_files:

        st.warning(
            "📄 Please upload PDFs first from "
            "Study Materials."
        )

        if st.button(
            "📄 Go to Study Materials",
            type="primary",
        ):

            go_to("pdf_upload")

    else:

        st.success(
            f"📚 Using "
            f"{len(st.session_state.uploaded_files)} "
            f"uploaded PDF(s)."
        )

        for msg in st.session_state.rag_chat:

            with st.chat_message(
                msg["role"]
            ):

                st.markdown(
                    msg["content"]
                )

        prompt = st.chat_input(
            "Ask anything about your uploaded notes..."
        )

        if prompt:

            st.session_state.rag_chat.append(
                {
                    "role": "user",
                    "content": prompt,
                }
            )

            with st.chat_message("user"):

                st.markdown(prompt)

            with st.chat_message("assistant"):

                with st.spinner(
                    "🔍 Searching your documents..."
                ):

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

                        response = (
                            f"AI response failed: {e}"
                        )

                    st.markdown(response)

                    save_chat(
                        prompt,
                        response
                    )

            st.session_state.rag_chat.append(
                {
                    "role": "assistant",
                    "content": response,
                }
            )


# =========================================================
# PAGE 4 — SUMMARIZER
# =========================================================
elif st.session_state.page == "summarizer":

    st.markdown(
        '<h1 class="main-title">'
        '📝 Study Notes Summarizer'
        '</h1>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<p class="subtitle">'
        'Turn long study materials into concise '
        'revision notes.'
        '</p>',
        unsafe_allow_html=True,
    )

    render_back_button()

    if not st.session_state.uploaded_files:

        st.warning(
            "📄 Please upload PDFs first."
        )

        if st.button(
            "📄 Upload Study Material",
            type="primary",
        ):

            go_to("pdf_upload")

    else:

        if st.button(
            "📝 Generate Study Notes",
            use_container_width=True,
            type="primary",
        ):

            with st.spinner(
                "Creating summary..."
            ):

                try:

                    summary = summarize_text(
                        st.session_state.pdf_text
                    )

                    st.markdown(
                        f"""
                        <div class="card">
                            {summary}
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                    save_chat(
                        "Generate study notes",
                        summary,
                    )

                except Exception as e:

                    st.error(
                        f"Summary generation failed: {e}"
                    )


# =========================================================
# PAGE 5 — MCQ GENERATOR
# =========================================================
elif st.session_state.page == "mcq_generator":

    st.markdown(
        '<h1 class="main-title">'
        '✅ MCQ Generator'
        '</h1>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<p class="subtitle">'
        'Generate practice questions from your '
        'uploaded materials.'
        '</p>',
        unsafe_allow_html=True,
    )

    render_back_button()

    if not st.session_state.uploaded_files:

        st.warning(
            "📄 Please upload PDFs first."
        )

        if st.button(
            "📄 Upload Study Material",
            type="primary",
        ):

            go_to("pdf_upload")

    else:

        num_questions = st.slider(
            "Number of Questions",
            3,
            15,
            5,
        )

        if st.button(
            "🎯 Generate MCQs",
            use_container_width=True,
            type="primary",
        ):

            with st.spinner(
                "Creating MCQs..."
            ):

                try:

                    mcqs = generate_mcqs(
                        st.session_state.pdf_text,
                        num_questions,
                    )

                    st.markdown(
                        f"""
                        <div class="card">
                            {mcqs}
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                    save_chat(
                        f"Generate {num_questions} MCQs",
                        mcqs,
                    )

                except Exception as e:

                    st.error(
                        f"MCQ generation failed: {e}"
                    )


# =========================================================
# PAGE 6 — IMPORTANT QUESTIONS
# =========================================================
elif st.session_state.page == "important_questions":

    st.markdown(
        '<h1 class="main-title">'
        '❓ Important Exam Questions'
        '</h1>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<p class="subtitle">'
        'Generate high-priority questions for '
        'examination preparation.'
        '</p>',
        unsafe_allow_html=True,
    )

    render_back_button()

    if not st.session_state.uploaded_files:

        st.warning(
            "📄 Please upload PDFs first."
        )

        if st.button(
            "📄 Upload Study Material",
            type="primary",
        ):

            go_to("pdf_upload")

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
            type="primary",
        ):

            with st.spinner(
                "Creating exam questions..."
            ):

                try:

                    questions = (
                        generate_important_questions(
                            st.session_state.pdf_text,
                            num_questions,
                        )
                    )

                    st.markdown(
                        f"""
                        <div class="card">
                            {questions}
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                    save_chat(
                        f"Generate "
                        f"{num_questions} important questions",
                        questions,
                    )

                except Exception as e:

                    st.error(
                        "Question generation failed: "
                        f"{e}"
                    )


# =========================================================
# PAGE 7 — STUDY PLANNER
# =========================================================
elif st.session_state.page == "study_plan":

    st.markdown(
        '<h1 class="main-title">'
        '📅 Smart Study Planner'
        '</h1>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<p class="subtitle">'
        'Create a structured preparation plan and '
        'track your daily tasks.'
        '</p>',
        unsafe_allow_html=True,
    )

    render_back_button()

    default_exam = (
        exam_date
        or (
            date.today()
            + timedelta(days=12)
        )
    )

    if default_exam < date.today():

        default_exam = (
            date.today()
            + timedelta(days=12)
        )

    c1, c2, c3 = st.columns(3)

    with c1:

        planner_exam_date = st.date_input(
            "Exam Date",
            value=default_exam,
            min_value=date.today(),
            max_value=(
                date.today()
                + timedelta(days=3650)
            ),
        )

    with c2:

        default_hours = max(
            1,
            min(
                8,
                int(study_hours)
                if study_hours
                else 3
            )
        )

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
            default=[
                "Data Structures",
                "DBMS"
            ],
        )

    if st.button(
        "🎯 Generate Smart Plan",
        use_container_width=True,
        type="primary",
    ):

        days = (
            planner_exam_date
            - date.today()
        ).days

        if days <= 0:

            st.error(
                "Exam date must be in the future."
            )

        elif not subjects:

            st.warning(
                "Select at least one subject."
            )

        else:

            plan = []

            plan_days = min(
                days,
                14
            )

            for day_number in range(
                1,
                plan_days + 1
            ):

                current_date = (
                    date.today()
                    + timedelta(
                        days=day_number
                    )
                )

                subject = subjects[
                    (day_number - 1)
                    % len(subjects)
                ]

                next_subject = (
                    subjects[
                        day_number
                        % len(subjects)
                    ]
                    if len(subjects) > 1
                    else subject
                )

                plan.append(
                    {
                        "day": day_number,
                        "date": current_date.strftime(
                            "%A, %d %b"
                        ),
                        "subjects": [
                            subject,
                            next_subject
                        ],
                        "tasks": [
                            f"Study {subject} concepts",
                            f"Practice questions from {subject}",
                            "Take a short self-review",
                        ],
                    }
                )

            st.session_state.study_plan = plan

            generated = []

            for p in plan[:7]:

                for index, task in enumerate(
                    p["tasks"]
                ):

                    generated.append(
                        {
                            "id":
                                f"plan_{p['day']}_{index}",

                            "title":
                                task,

                            "subject":
                                ", ".join(
                                    p["subjects"]
                                ),
                        }
                    )

            st.session_state.generated_tasks = (
                generated
            )

            st.session_state.completed_tasks = set()

            st.success(
                "✅ Smart study plan generated successfully."
            )

    if st.session_state.study_plan:

        st.markdown(
            "### 📚 Your Plan"
        )

        for p in st.session_state.study_plan:

            task_text = " • ".join(
                p["tasks"]
            )

            st.markdown(
                f"""
                <div class="card">

                    <div style="
                        font-size:1.1rem;
                        font-weight:800;
                        color:#6d28d9;
                    ">
                        📅 Day {p['day']}
                        — {p['date']}
                    </div>

                    <div style="margin-top:8px;">
                        <b>📚 Subjects:</b>
                        {safe_html(
                            ", ".join(
                                p["subjects"]
                            )
                        )}
                    </div>

                    <div style="margin-top:7px;">
                        <b>⏱️ Duration:</b>
                        {hours_per_day} hour(s)
                    </div>

                    <div style="margin-top:7px;">
                        <b>✅ Tasks:</b>
                        {safe_html(task_text)}
                    </div>

                </div>
                """,
                unsafe_allow_html=True,
            )

        st.info(
            "Your first 7 days of tasks are also "
            "available on the Dashboard for "
            "progress tracking."
        )


# =========================================================
# PAGE 8 — STUDENT PROFILE
# =========================================================
elif st.session_state.page == "settings":

    st.markdown(
        '<h1 class="main-title">'
        '⚙️ Student Profile'
        '</h1>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<p class="subtitle">'
        'Manage your academic information and '
        'study preferences.'
        '</p>',
        unsafe_allow_html=True,
    )

    render_back_button()

    st.markdown(
        """
        <div class="info-card">

            <b>🎓 Why complete your profile?</b>
            <br><br>

            Your branch, semester, exam date and
            study goal help the dashboard and
            Study Planner provide more relevant
            information.

        </div>
        """,
        unsafe_allow_html=True,
    )

    profile_exam_default = (
        exam_date
        or (
            date.today()
            + timedelta(days=12)
        )
    )

    if profile_exam_default < date.today():

        profile_exam_default = (
            date.today()
            + timedelta(days=12)
        )

    with st.form(
        "profile_form"
    ):

        p1, p2 = st.columns(2)

        with p1:

            new_name = st.text_input(
                "👤 Student Name",
                value=(
                    name
                    if name != "Student"
                    else ""
                ),
            )

            new_branch = st.text_input(
                "💻 Branch",
                value=branch,
            )

            new_semester = st.text_input(
                "📚 Semester",
                value=semester,
            )

        with p2:

            new_college = st.text_input(
                "🏫 College",
                value=(
                    college
                    if college != "College Not Set"
                    else ""
                ),
            )

            new_exam_date = st.date_input(
                "📅 Exam Date",
                value=profile_exam_default,
                min_value=date.today(),
                max_value=(
                    date.today()
                    + timedelta(days=3650)
                ),
            )

            new_hours = st.number_input(
                "⏱️ Daily Study Goal (Hours)",
                min_value=0.0,
                max_value=12.0,
                value=max(
                    0.0,
                    min(
                        study_hours,
                        12.0
                    )
                ),
                step=0.5,
            )

            current_time = profile.get(
                "preferred_study_time",
                "Morning"
            )

            time_options = [
                "Morning",
                "Afternoon",
                "Evening",
                "Night",
            ]

            preferred_study_time = st.selectbox(
                "🕒 Preferred Study Time",
                time_options,
                index=(
                    time_options.index(
                        current_time
                    )
                    if current_time
                    in time_options
                    else 0
                ),
            )

        save_profile = st.form_submit_button(
            "💾 Save Student Profile",
            use_container_width=True,
        )

    if save_profile:

        if not new_name.strip():

            st.error(
                "⚠️ Please enter your name."
            )

        else:

            try:

                save_student_profile(
                    new_name.strip(),
                    new_branch.strip(),
                    new_semester.strip(),
                    new_college.strip(),
                    new_exam_date.strftime(
                        "%Y-%m-%d"
                    ),
                    float(new_hours),
                    preferred_study_time,
                )

                st.success(
                    "✅ Student profile saved successfully!"
                )

                st.session_state.page = (
                    "dashboard"
                )

                st.rerun()

            except Exception as e:

                st.error(
                    "❌ Could not save the profile. "
                    f"Database error: {e}"
                )
