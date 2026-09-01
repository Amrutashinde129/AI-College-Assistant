import streamlit as st
from streamlit_option_menu import option_menu
from datetime import date, datetime, timedelta
from google import genai
import json
import re

from utils.pdf_processor import extract_text_from_pdf
from utils.vector_store import create_vector_store
from utils.summarizer import summarize_text
from utils.mcq_generator import generate_mcqs
from utils.important_questions import generate_important_questions

from db_manager import (
    create_table, save_chat, get_chat_history, clear_chat_history,
    save_student_profile, get_student_profile,
    save_study_plan, get_study_plan, get_study_plan_by_date,
    update_study_plan_status, delete_study_plan, clear_study_plan
)

# ------------------------------------------------------------
# SETUP
# ------------------------------------------------------------

st.set_page_config(
    page_title="AI College Assistant",
    page_icon="🎓",
    layout="wide"
)

# ------------------------------------------------------------
# MODERN UI THEME
# ------------------------------------------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.stApp { background: #f6f8fc; }
.block-container { padding-top: 1.4rem; padding-bottom: 2rem; max-width: 1450px; }
section[data-testid="stSidebar"] { background: linear-gradient(180deg,#111827 0%,#172033 55%,#0f172a 100%); border-right:1px solid rgba(255,255,255,.08); }
section[data-testid="stSidebar"] > div { padding-top:1.2rem; }
section[data-testid="stSidebar"] * { color:#e5e7eb; }
section[data-testid="stSidebar"] .stCaption { color:#94a3b8 !important; }
section[data-testid="stSidebar"] hr { border-color:rgba(255,255,255,.10); }
div[data-testid="stSidebarNav"] { display:none; }
h1 { font-size:2.15rem !important; font-weight:800 !important; color:#111827 !important; letter-spacing:-.03em; }
h2 { font-weight:750 !important; color:#111827 !important; }
h3 { font-weight:700 !important; color:#1f2937 !important; }
div[data-testid="stMetric"] { background:white; border:1px solid #e5e7eb; border-radius:18px; padding:18px 20px; box-shadow:0 5px 20px rgba(15,23,42,.05); }
div[data-testid="stMetricLabel"] { color:#64748b !important; font-weight:600; }
div[data-testid="stMetricValue"] { color:#111827 !important; font-weight:800; }
div[data-testid="stVerticalBlockBorderWrapper"] { background:#fff; border:1px solid #e5e7eb !important; border-radius:18px !important; box-shadow:0 6px 22px rgba(15,23,42,.05); }
.stButton > button, .stFormSubmitButton > button { border-radius:12px !important; border:1px solid #dbe2ea !important; min-height:42px; font-weight:650 !important; transition:all .18s ease; box-shadow:0 2px 7px rgba(15,23,42,.04); }
.stButton > button:hover, .stFormSubmitButton > button:hover { transform:translateY(-1px); box-shadow:0 7px 18px rgba(15,23,42,.10); border-color:#94a3b8 !important; }
input, textarea, [data-baseweb="select"], [data-baseweb="input"] { border-radius:11px !important; }
div[data-baseweb="select"] > div, textarea, input { border-color:#dbe2ea !important; }
div[data-testid="stProgressBar"] > div > div { border-radius:20px; }
div[data-testid="stAlert"] { border-radius:14px; }
[data-testid="stFileUploader"] { border-radius:15px; }
.hero { background:linear-gradient(135deg,#111827 0%,#1e293b 58%,#334155 100%); padding:28px 30px; border-radius:22px; color:white; margin-bottom:24px; box-shadow:0 12px 35px rgba(15,23,42,.16); }
.hero h2 { color:white !important; margin:0 0 6px 0; font-size:1.8rem; }
.hero p { color:#cbd5e1; margin:0; font-size:1rem; }
.section-label { color:#64748b; font-size:.78rem; font-weight:750; text-transform:uppercase; letter-spacing:.11em; margin-bottom:4px; }
#MainMenu { visibility:hidden; } footer { visibility:hidden; } header[data-testid="stHeader"] { background:transparent; }
</style>
""", unsafe_allow_html=True)

create_table()

MODEL = "gemini-3.6-flash"


# ------------------------------------------------------------
# GEMINI
# ------------------------------------------------------------

def ask_ai(prompt):
    try:
        client = genai.Client(
            api_key=st.secrets["GEMINI_API_KEY"]
        )
        response = client.models.generate_content(
            model=MODEL,
            contents=prompt
        )
        return response.text or "No response generated."

    except KeyError:
        return "❌ GEMINI_API_KEY is not configured."

    except Exception as e:
        if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
            return "⚠️ Gemini API quota has been reached."
        return f"❌ Gemini error: {e}"


# ------------------------------------------------------------
# RAG
# ------------------------------------------------------------

def answer_question(store, question):
    try:
        docs = store.similarity_search(question, k=5)

        if not docs:
            return "This information is not available in the uploaded document."

        context = "\n\n".join(d.page_content for d in docs)

        prompt = f"""
You are an AI College Assistant.

Answer using ONLY the college notes below.

NOTES:
{context}

QUESTION:
{question}

Rules:
- Give a simple and clear answer.
- Do not invent information.
- If the answer is not in the notes, say:
This information is not available in the uploaded document.
"""

        return ask_ai(prompt)

    except Exception as e:
        return f"❌ RAG error: {e}"


# ------------------------------------------------------------
# AI STUDY PLAN
# ------------------------------------------------------------

def generate_tasks(profile):

    subjects = [
        x.strip()
        for x in profile["subjects"].split(",")
        if x.strip()
    ]

    today = date.today()

    try:
        exam = date.fromisoformat(profile["exam_date"])
        days = max((exam - today).days, 1)
    except:
        exam = today
        days = 1

    days = min(days, 7)

    prompt = f"""
Create a study plan for a college student.

Name: {profile["name"]}
Course: {profile["course"]}
Semester: {profile["semester"]}
Subjects: {", ".join(subjects)}
Daily hours: {profile["daily_study_hours"]}
Preferred time: {profile["preferred_study_time"]}
Exam date: {profile["exam_date"]}
Today: {today}

Create a realistic plan for {days} days.

Rules:
- Use only the given subjects.
- Each task: 0.5 to 2 hours.
- Include learning, revision and practice.
- Use High, Medium or Low priority.
- Do not create tasks after the exam.
- Return ONLY JSON.

Format:
[
 {{
  "subject": "Subject",
  "topic": "Topic",
  "study_date": "YYYY-MM-DD",
  "start_time": "18:00",
  "end_time": "19:00",
  "duration": 1.0,
  "priority": "High"
 }}
]
"""

    result = ask_ai(prompt)
    result = result.replace("```json", "").replace("```", "").strip()

    match = re.search(r"\[.*\]", result, re.DOTALL)

    if not match:
        raise Exception("AI did not return valid JSON.")

    tasks = json.loads(match.group())

    valid = []

    for task in tasks:
        if not all(
            key in task
            for key in [
                "subject", "topic", "study_date",
                "start_time", "end_time",
                "duration", "priority"
            ]
        ):
            continue

        if task["subject"] not in subjects:
            continue

        try:
            task_date = date.fromisoformat(task["study_date"])

            if today <= task_date <= exam:
                task["duration"] = min(
                    max(float(task["duration"]), 0.5),
                    2.0
                )

                if task["priority"] not in [
                    "High", "Medium", "Low"
                ]:
                    task["priority"] = "Medium"

                valid.append(task)

        except:
            continue

    return valid


# ------------------------------------------------------------
# SIDEBAR
# ------------------------------------------------------------

with st.sidebar:

    st.markdown("""
    <div style="padding:8px 4px 16px 4px;">
      <div style="font-size:1.55rem;font-weight:800;color:white;">🎓 AI College</div>
      <div style="font-size:1.55rem;font-weight:800;color:#a5b4fc;margin-top:-5px;">Assistant</div>
      <div style="font-size:.78rem;color:#94a3b8;margin-top:7px;">Your personal study workspace</div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    page = option_menu(
        "Navigation",
        [
            "🏠 Dashboard",
            "👤 Student Profile",
            "📅 Study Planner",
            "✅ Tasks & Tracking",
            "💬 AI Chat",
            "📝 Study Summary",
            "❓ MCQ Generator",
            "🎯 Important Questions",
            "💾 Chat History"
        ],
        icons=[
            "house",
            "person",
            "calendar",
            "check-circle",
            "chat",
            "file-text",
            "question-circle",
            "bullseye",
            "clock-history"
        ],
        default_index=0
    )

    st.divider()

    st.subheader("📚 Study Material")

    pdf = st.file_uploader(
        "Upload College PDF",
        type=["pdf"]
    )

    if pdf:
        st.caption(f"📄 {pdf.name}")


# ------------------------------------------------------------
# PDF PROCESSING
# ------------------------------------------------------------

if pdf:

    if st.session_state.get("pdf_name") != pdf.name:

        with st.spinner("Processing PDF..."):

            text = extract_text_from_pdf(pdf)

            if text.strip():

                st.session_state.pdf_text = text
                st.session_state.vector_store = create_vector_store(text)
                st.session_state.pdf_name = pdf.name

                st.success("PDF processed successfully.")

            else:
                st.error("Could not extract text from PDF.")


# ------------------------------------------------------------
# DASHBOARD
# ------------------------------------------------------------

if page == "🏠 Dashboard":

    profile = get_student_profile()
    plans = get_study_plan()
    today_str = date.today().isoformat()
    today_plans = get_study_plan_by_date(today_str)

    total = len(plans)
    completed = sum(1 for p in plans if p[8] == "Completed")
    pending = total - completed
    progress = completed / total if total else 0

    # ---------- HEADER ----------
    if profile:
        first_name = profile["name"].split()[0] if profile["name"].strip() else "Student"
        st.markdown(
            f"""
            <div style="padding:8px 0 22px 0;">
                <div style="font-size:14px;letter-spacing:2px;font-weight:700;color:#6b7280;">
                    STUDENT COMMAND CENTER
                </div>
                <div style="font-size:36px;font-weight:800;margin-top:4px;">
                    Good to see you, {first_name} 👋
                </div>
                <div style="font-size:16px;color:#6b7280;margin-top:5px;">
                    Here is your study focus for today.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            """
            <div style="padding:8px 0 22px 0;">
                <div style="font-size:14px;letter-spacing:2px;font-weight:700;color:#6b7280;">
                    STUDENT COMMAND CENTER
                </div>
                <div style="font-size:36px;font-weight:800;margin-top:4px;">
                    Welcome to your study space 👋
                </div>
                <div style="font-size:16px;color:#6b7280;margin-top:5px;">
                    Create your profile to unlock your personalized dashboard.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # ---------- TOP WORKSPACE ----------
    left, right = st.columns([1.7, 1], gap="large")

    with left:
        if profile:
            try:
                exam = date.fromisoformat(profile["exam_date"])
                days_left = (exam - date.today()).days
            except Exception:
                exam = None
                days_left = None

            if days_left is not None:
                if days_left > 0:
                    countdown = str(days_left)
                    label = "DAYS UNTIL EXAM"
                    sub = exam.strftime("%d %B %Y")
                elif days_left == 0:
                    countdown = "TODAY"
                    label = "EXAM DAY"
                    sub = exam.strftime("%d %B %Y")
                else:
                    countdown = "—"
                    label = "EXAM DATE PASSED"
                    sub = exam.strftime("%d %B %Y")

                st.markdown(
                    f"""
                    <div style="
                        background:linear-gradient(135deg,#111827 0%,#273449 100%);
                        border-radius:24px;padding:28px 30px;color:white;
                        min-height:190px;box-shadow:0 10px 30px rgba(17,24,39,.12);
                    ">
                        <div style="font-size:13px;letter-spacing:2px;font-weight:700;opacity:.7;">
                            EXAM COUNTDOWN
                        </div>
                        <div style="font-size:58px;font-weight:850;line-height:1;margin-top:16px;">
                            {countdown}
                        </div>
                        <div style="font-size:14px;font-weight:700;letter-spacing:1px;margin-top:8px;">
                            {label}
                        </div>
                        <div style="font-size:14px;opacity:.7;margin-top:5px;">
                            {sub}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                st.warning("Your exam date could not be read. Please update your Student Profile.")

        else:
            st.info("👤 Complete your Student Profile to activate the exam countdown.")

    with right:
        # CSS conic-gradient gives a visual progress ring without extra libraries.
        pct = int(progress * 100)
        st.markdown(
            f"""
            <div style="
                background:#ffffff;border:1px solid #e5e7eb;border-radius:24px;
                padding:24px;text-align:center;min-height:190px;
            ">
                <div style="font-size:13px;letter-spacing:1.5px;font-weight:700;color:#6b7280;">
                    OVERALL PROGRESS
                </div>
                <div style="
                    width:118px;height:118px;border-radius:50%;
                    background:conic-gradient(#6366f1 {pct * 3.6}deg,#eef0f4 0deg);
                    margin:18px auto 10px;display:flex;align-items:center;justify-content:center;
                ">
                    <div style="
                        width:88px;height:88px;border-radius:50%;background:white;
                        display:flex;align-items:center;justify-content:center;
                        font-size:25px;font-weight:850;color:#111827;
                    ">{pct}%</div>
                </div>
                <div style="font-size:13px;color:#6b7280;">
                    {completed} completed · {pending} pending
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)

    # ---------- TODAY'S FOCUS + PROFILE ----------
    focus_col, profile_col = st.columns([1.55, 1], gap="large")

    with focus_col:
        st.markdown("### 🎯 Today's Focus")
        if today_plans:
            for i, p in enumerate(today_plans):
                pid, subject, topic, pdate, start, end, duration, priority, status, created = p
                status_badge = "✓ COMPLETED" if status == "Completed" else "● PENDING"
                badge_bg = "#ecfdf5" if status == "Completed" else "#f3f4f6"
                badge_text = "#047857" if status == "Completed" else "#4b5563"

                st.markdown(
                    f"""
                    <div style="
                        background:#fff;border:1px solid #e5e7eb;border-radius:18px;
                        padding:17px 20px;margin-bottom:10px;
                    ">
                        <div style="display:flex;justify-content:space-between;gap:10px;">
                            <div>
                                <div style="font-size:17px;font-weight:800;">{subject}</div>
                                <div style="color:#6b7280;font-size:14px;margin-top:3px;">{topic}</div>
                            </div>
                            <div style="
                                background:{badge_bg};color:{badge_text};padding:6px 9px;
                                border-radius:999px;font-size:10px;font-weight:800;height:max-content;
                            ">{status_badge}</div>
                        </div>
                        <div style="margin-top:12px;color:#6b7280;font-size:13px;">
                            ⏰ {start} – {end} &nbsp; · &nbsp; {duration} hrs &nbsp; · &nbsp; {priority} priority
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                if status != "Completed":
                    if st.button("Mark complete", key=f"new_dash_complete_{pid}", use_container_width=False):
                        update_study_plan_status(pid, "Completed")
                        st.rerun()
        else:
            st.markdown(
                """
                <div style="
                    border:1px dashed #cbd5e1;border-radius:18px;padding:30px;
                    text-align:center;color:#64748b;background:#f8fafc;
                ">
                    <div style="font-size:30px;">📅</div>
                    <div style="font-weight:750;color:#334155;margin-top:8px;">Nothing scheduled today</div>
                    <div style="font-size:13px;margin-top:5px;">
                        Open Study Planner and add your next focus session.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    with profile_col:
        st.markdown("### 👤 Student Snapshot")
        if profile:
            subjects = [x.strip() for x in profile["subjects"].split(",") if x.strip()]
            initials = "".join(part[0] for part in profile["name"].split()[:2]).upper() or "ST"

            st.markdown(
                f"""
                <div style="
                    background:#fff;border:1px solid #e5e7eb;border-radius:22px;
                    padding:24px;
                ">
                    <div style="display:flex;align-items:center;gap:16px;">
                        <div style="
                            width:62px;height:62px;border-radius:18px;background:#111827;color:white;
                            display:flex;align-items:center;justify-content:center;
                            font-size:21px;font-weight:800;
                        ">{initials}</div>
                        <div>
                            <div style="font-size:20px;font-weight:800;">{profile["name"]}</div>
                            <div style="font-size:13px;color:#6b7280;">
                                {profile["course"]} · Semester {profile["semester"]}
                            </div>
                        </div>
                    </div>
                    <div style="height:1px;background:#eef0f3;margin:20px 0;"></div>
                    <div style="display:grid;grid-template-columns:1fr 1fr;gap:18px;">
                        <div>
                            <div style="font-size:11px;color:#9ca3af;font-weight:700;">SUBJECTS</div>
                            <div style="font-size:22px;font-weight:800;margin-top:3px;">{len(subjects)}</div>
                        </div>
                        <div>
                            <div style="font-size:11px;color:#9ca3af;font-weight:700;">DAILY STUDY</div>
                            <div style="font-size:22px;font-weight:800;margin-top:3px;">{profile["daily_study_hours"]}h</div>
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)

    # ---------- AI COACH ----------
    st.markdown("### 🤖 AI Coach")
    coach_left, coach_right = st.columns([1.8, 1], gap="large")

    with coach_left:
        if profile:
            if today_plans:
                pending_today = [p for p in today_plans if p[8] != "Completed"]
                if pending_today:
                    focus_subject = pending_today[0][1]
                    recommendation = (
                        f"Your next priority is **{focus_subject}**. "
                        f"Complete the first pending session before moving to another subject."
                    )
                else:
                    recommendation = "Excellent! 🎉 You completed today's planned sessions. Use the Study Planner to prepare tomorrow's focus."
            elif pending:
                recommendation = "You have pending tasks. Open Tasks & Tracking and choose one task to make today's main focus."
            else:
                recommendation = "Your workspace is ready. Generate an AI Study Plan to create personalized sessions."
        else:
            recommendation = "Create your Student Profile first so the AI Coach can personalize your study recommendations."

        st.markdown(
            f"""
            <div style="
                background:#eef2ff;border:1px solid #c7d2fe;border-radius:20px;
                padding:23px 25px;min-height:120px;
            ">
                <div style="font-size:12px;font-weight:800;letter-spacing:1.5px;color:#4f46e5;">
                    PERSONALIZED RECOMMENDATION
                </div>
                <div style="font-size:16px;line-height:1.6;color:#1f2937;margin-top:10px;">
                    {recommendation}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with coach_right:
        st.markdown(
            f"""
            <div style="
                background:#111827;color:white;border-radius:20px;padding:22px 24px;
                min-height:120px;
            ">
                <div style="font-size:12px;letter-spacing:1.5px;font-weight:800;opacity:.6;">
                    WORKLOAD
                </div>
                <div style="font-size:30px;font-weight:850;margin-top:8px;">{total} tasks</div>
                <div style="font-size:13px;opacity:.65;margin-top:3px;">
                    {pending} still need attention
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # ---------- SUBJECTS ----------
    if profile:
        st.markdown("### 📚 Subject Focus")
        subjects = [x.strip() for x in profile["subjects"].split(",") if x.strip()]
        subject_cols = st.columns(min(len(subjects), 4) or 1)

        for i, subject in enumerate(subjects):
            subject_tasks = [p for p in plans if p[1].strip().lower() == subject.strip().lower()]
            subject_total = len(subject_tasks)
            subject_done = sum(1 for p in subject_tasks if p[8] == "Completed")
            subject_pct = int((subject_done / subject_total) * 100) if subject_total else 0

            with subject_cols[i % len(subject_cols)]:
                st.markdown(
                    f"""
                    <div style="
                        background:#fff;border:1px solid #e5e7eb;border-radius:17px;padding:17px;
                        margin-bottom:12px;
                    ">
                        <div style="font-weight:800;">{subject}</div>
                        <div style="font-size:12px;color:#6b7280;margin-top:4px;">
                            {subject_done}/{subject_total} tasks complete
                        </div>
                        <div style="height:7px;background:#eef0f4;border-radius:99px;margin-top:13px;">
                            <div style="
                                height:7px;width:{subject_pct}%;background:#6366f1;border-radius:99px;
                            "></div>
                        </div>
                        <div style="text-align:right;font-size:11px;color:#6b7280;margin-top:6px;">
                            {subject_pct}%
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    # ---------- QUICK ACTIONS ----------
    st.markdown("### ⚡ Quick Actions")
    q1, q2, q3, q4 = st.columns(4)

    with q1:
        st.info("📅 **Study Planner**\n\nBuild or update your study schedule.")
    with q2:
        st.info("✅ **Tasks & Tracking**\n\nManage pending and completed work.")
    with q3:
        st.info("💬 **AI Chat**\n\nAsk questions from your college notes.")
    with q4:
        st.info("❓ **MCQ Generator**\n\nPractice with AI-generated questions.")


# ------------------------------------------------------------
# STUDENT PROFILE
# ------------------------------------------------------------


    st.title("👤 Student Profile")
    st.caption("Build your personalized learning profile and exam timeline.")

    profile = get_student_profile()

    if profile:
        name_default = profile["name"]
        course_default = profile["course"]
        semester_default = profile["semester"]
        subjects_default = profile["subjects"]
        exam_default = date.fromisoformat(profile["exam_date"])
        hours_default = float(profile["daily_study_hours"])
        time_default = profile["preferred_study_time"]
    else:
        name_default = ""
        course_default = ""
        semester_default = ""
        subjects_default = ""
        exam_default = date.today()
        hours_default = 2.0
        time_default = "Evening"

    with st.form("profile"):

        name = st.text_input(
            "Student Name",
            value=name_default
        )

        course = st.text_input(
            "Course / Branch",
            value=course_default
        )

        semester = st.text_input(
            "Semester",
            value=semester_default
        )

        subjects = st.text_area(
            "Subjects",
            value=subjects_default,
            placeholder="OOP, DBMS, DSU, DTE"
        )

         
        min_exam_date = date.today()
        max_exam_date = date(2036, 8, 26)

        # Keep the saved exam date if it is still valid.
        if exam_default < min_exam_date:
            exam_default = min_exam_date
        elif exam_default > max_exam_date:
            exam_default = max_exam_date

        exam_date = st.date_input(
            "Exam Date",
            value=exam_default,
            min_value=min_exam_date,
            max_value=max_exam_date
        )
       

        hours = st.number_input(
            "Daily Study Hours",
            0.5,
            12.0,
            hours_default,
            0.5
        )

        times = [
            "Morning",
            "Afternoon",
            "Evening",
            "Night"
        ]

        preferred = st.selectbox(
            "Preferred Study Time",
            times,
            index=times.index(time_default)
            if time_default in times else 2
        )

        save = st.form_submit_button(
            "💾 Save Profile",
            use_container_width=True
        )

        if save:

            if not name.strip():
                st.warning("Enter your name.")

            elif not course.strip():
                st.warning("Enter your course.")

            elif not semester.strip():
                st.warning("Enter your semester.")

            elif not subjects.strip():
                st.warning("Enter at least one subject.")

            else:

                save_student_profile(
                    name.strip(),
                    course.strip(),
                    semester.strip(),
                    subjects.strip(),
                    exam_date.isoformat(),
                    hours,
                    preferred
                )

                st.success("Student profile saved.")
                st.rerun()

    profile = get_student_profile()

    if profile:

        st.divider()
        st.subheader("Saved Information")

        st.write(f"**Name:** {profile['name']}")
        st.write(f"**Course:** {profile['course']}")
        st.write(f"**Semester:** {profile['semester']}")
        st.write(f"**Subjects:** {profile['subjects']}")
        st.write(f"**Exam Date:** {profile['exam_date']}")
        st.write(
            f"**Daily Study:** "
            f"{profile['daily_study_hours']} hours"
        )
        st.write(
            f"**Preferred Time:** "
            f"{profile['preferred_study_time']}"
        )


# ------------------------------------------------------------
# STUDY PLANNER
# ------------------------------------------------------------

elif page == "📅 Study Planner":

    st.title("📅 Smart Study Planner")
    st.caption("Turn your academic goals into a practical day-by-day plan.")

    profile = get_student_profile()

    if not profile:

        st.warning(
            "Please complete your Student Profile first."
        )

    else:

        subjects = [
            x.strip()
            for x in profile["subjects"].split(",")
            if x.strip()
        ]

        c1, c2, c3 = st.columns(3)

        c1.metric("📚 Subjects", len(subjects))
        c2.metric(
            "⏱️ Daily Study",
            f"{profile['daily_study_hours']} hrs"
        )
        c3.metric(
            "📅 Exam",
            profile["exam_date"]
        )

        st.divider()

        plans = get_study_plan()

        total = len(plans)
        completed = sum(
            1 for p in plans if p[8] == "Completed"
        )

        st.subheader("📊 Progress")

        c1, c2, c3 = st.columns(3)

        c1.metric("Total", total)
        c2.metric("Completed", completed)
        c3.metric("Pending", total - completed)

        if total:
            st.progress(
                completed / total
            )

        st.divider()

        st.subheader("🤖 AI Study Plan")

        if st.button(
            "Generate AI Study Plan",
            use_container_width=True
        ):

            with st.spinner("Creating study plan..."):

                try:

                    tasks = generate_tasks(profile)

                    for task in tasks:

                        save_study_plan(
                            task["subject"],
                            task["topic"],
                            task["study_date"],
                            task["start_time"],
                            task["end_time"],
                            task["duration"],
                            task["priority"],
                            "Pending"
                        )

                    st.success(
                        f"{len(tasks)} study tasks created."
                    )

                    st.rerun()

                except Exception as e:
                    st.error(str(e))

        st.divider()

        st.subheader("➕ Add Study Task")

        with st.form("study"):

            subject = st.selectbox(
                "Subject",
                subjects
            )

            topic = st.text_input(
                "Topic / Chapter"
            )

            study_date = st.date_input(
                "Study Date",
                value=date.today(),
                min_value=date.today(),
                max_value=date(2036, 8, 26)
            )

            c1, c2 = st.columns(2)

            start = c1.time_input("Start Time")
            end = c2.time_input("End Time")

            duration = st.number_input(
                "Duration (hours)",
                0.25,
                12.0,
                1.0,
                0.25
            )

            priority = st.selectbox(
                "Priority",
                ["High", "Medium", "Low"]
            )

            add = st.form_submit_button(
                "Add Study Task",
                use_container_width=True
            )

            if add:

                if not topic.strip():
                    st.warning("Enter a topic.")

                elif end <= start:
                    st.warning(
                        "End time must be after start time."
                    )

                else:

                    save_study_plan(
                        subject,
                        topic.strip(),
                        study_date.isoformat(),
                        start.strftime("%H:%M"),
                        end.strftime("%H:%M"),
                        duration,
                        priority,
                        "Pending"
                    )

                    st.success("Task added.")
                    st.rerun()

        st.divider()

        st.subheader("📋 Today's Plan")

        today_plans = get_study_plan_by_date(
            date.today().isoformat()
        )

        if today_plans:

            for p in today_plans:

                (
                    pid, subject, topic, pdate,
                    start, end, duration,
                    priority, status, created
                ) = p

                with st.container(border=True):

                    st.write(
                        f"📚 **{subject}** — {topic}"
                    )

                    st.write(
                        f"⏰ {start} - {end} | "
                        f"⏱️ {duration} hrs | "
                        f"🔥 {priority}"
                    )

                    c1, c2 = st.columns(2)

                    if status != "Completed":

                        if c1.button(
                            "✅ Complete",
                            key=f"complete_{pid}"
                        ):
                            update_study_plan_status(
                                pid,
                                "Completed"
                            )
                            st.rerun()

                    else:
                        c1.success("Completed")

                    if c2.button(
                        "🗑️ Delete",
                        key=f"delete_{pid}"
                    ):
                        delete_study_plan(pid)
                        st.rerun()

        else:
            st.info("No tasks for today.")

        st.divider()

        st.subheader("📚 All Study Plans")

        plans = get_study_plan()

        if plans:

            for p in plans:

                status = "✅" if p[8] == "Completed" else "⏳"

                st.write(
                    f"{status} **{p[3]}** | "
                    f"**{p[1]}** | {p[2]} | "
                    f"{p[4]}-{p[5]} | {p[7]}"
                )

            if st.button("🗑️ Clear All Study Plans"):
                clear_study_plan()
                st.rerun()

        else:
            st.info("No study plans available.")


# ------------------------------------------------------------
# TASKS & TRACKING
# ------------------------------------------------------------

elif page == "✅ Tasks & Tracking":

    st.title("✅ Tasks & Tracking")
    st.caption("Manage deadlines, complete tasks and monitor your study progress.")

    profile = get_student_profile()

    if not profile:
        st.warning("Please complete your Student Profile first.")
    else:
        subjects = [
            x.strip()
            for x in profile["subjects"].split(",")
            if x.strip()
        ]

        plans = get_study_plan()
        today_str = date.today().isoformat()

        # -----------------------------
        # TRACKING SUMMARY
        # -----------------------------
        total = len(plans)
        completed = sum(1 for p in plans if p[8] == "Completed")
        pending = sum(1 for p in plans if p[8] != "Completed")
        overdue = sum(
            1 for p in plans
            if p[3] < today_str and p[8] != "Completed"
        )

        progress = completed / total if total else 0

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("📋 Total Tasks", total)
        c2.metric("✅ Completed", completed)
        c3.metric("⏳ Pending", pending)
        c4.metric("⚠️ Overdue", overdue)

        st.progress(progress)
        st.caption(f"Overall completion: {int(progress * 100)}%")

        st.divider()

        # -----------------------------
        # ADD TASK
        # -----------------------------
        st.subheader("➕ Add New Task")

        with st.form("add_task_tracking"):
            subject = st.selectbox("Subject", subjects)
            topic = st.text_input(
                "Task / Topic",
                placeholder="Example: Study Classes and Objects"
            )

            task_date = st.date_input(
                "Due / Study Date",
                value=date.today(),
                min_value=date.today(),
                max_value=date(2036, 8, 26)
            )

            c1, c2 = st.columns(2)
            start = c1.time_input("Start Time")
            end = c2.time_input("End Time")

            duration = st.number_input(
                "Duration (hours)",
                min_value=0.25,
                max_value=12.0,
                value=1.0,
                step=0.25
            )

            priority = st.selectbox(
                "Priority",
                ["High", "Medium", "Low"]
            )

            add_task = st.form_submit_button(
                "➕ Add Task",
                use_container_width=True
            )

            if add_task:
                if not topic.strip():
                    st.warning("Please enter a task/topic.")
                elif end <= start:
                    st.warning("End time must be after start time.")
                else:
                    save_study_plan(
                        subject,
                        topic.strip(),
                        task_date.isoformat(),
                        start.strftime("%H:%M"),
                        end.strftime("%H:%M"),
                        duration,
                        priority,
                        "Pending"
                    )
                    st.success("Task added successfully.")
                    st.rerun()

        st.divider()

        # -----------------------------
        # FILTER TASKS
        # -----------------------------
        st.subheader("📋 Manage Tasks")

        filter_option = st.selectbox(
            "Show Tasks",
            ["All", "Pending", "Completed", "Overdue", "Today"]
        )

        filtered_plans = plans

        if filter_option == "Pending":
            filtered_plans = [
                p for p in plans if p[8] != "Completed"
            ]
        elif filter_option == "Completed":
            filtered_plans = [
                p for p in plans if p[8] == "Completed"
            ]
        elif filter_option == "Overdue":
            filtered_plans = [
                p for p in plans
                if p[3] < today_str and p[8] != "Completed"
            ]
        elif filter_option == "Today":
            filtered_plans = [
                p for p in plans if p[3] == today_str
            ]

        if not filtered_plans:
            st.info("No tasks found for this filter.")
        else:
            for p in filtered_plans:
                (
                    pid, subject, topic, task_date,
                    start, end, duration,
                    priority, status, created
                ) = p

                is_overdue = (
                    task_date < today_str and status != "Completed"
                )

                status_text = (
                    "✅ Completed"
                    if status == "Completed"
                    else "⚠️ Overdue"
                    if is_overdue
                    else "⏳ Pending"
                )

                with st.container(border=True):
                    c1, c2, c3 = st.columns([3, 2, 1])

                    c1.write(f"📚 **{subject}**")
                    c1.caption(f"{topic}")

                    c2.write(f"📅 {task_date}")
                    c2.caption(
                        f"⏰ {start} - {end} • "
                        f"{duration} hrs • {priority}"
                    )

                    c3.write(status_text)

                    b1, b2 = st.columns(2)

                    if status != "Completed":
                        if b1.button(
                            "✅ Mark Complete",
                            key=f"track_complete_{pid}"
                        ):
                            update_study_plan_status(pid, "Completed")
                            st.rerun()
                    else:
                        b1.success("Completed")

                    if b2.button(
                        "🗑️ Delete",
                        key=f"track_delete_{pid}"
                    ):
                        delete_study_plan(pid)
                        st.rerun()


# ------------------------------------------------------------
# AI CHAT
# ------------------------------------------------------------

elif page == "💬 AI Chat":

    st.title("💬 AI Study Assistant")
    st.caption("Ask questions directly from your uploaded college notes.")

    if "vector_store" not in st.session_state:

        st.info("📄 Upload a college PDF first.")

    else:

        st.success(
            f"Using: {st.session_state.pdf_name}"
        )

        question = st.text_area(
            "Ask your question",
            placeholder="Explain normalization in simple words."
        )

        if st.button(
            "🤖 Ask AI",
            use_container_width=True
        ):

            if not question.strip():
                st.warning("Enter a question.")

            else:

                with st.spinner("Searching your notes..."):

                    answer = answer_question(
                        st.session_state.vector_store,
                        question
                    )

                st.subheader("🤖 AI Answer")
                st.markdown(answer)

                save_chat(
                    question,
                    answer
                )


# ------------------------------------------------------------
# SUMMARY
# ------------------------------------------------------------

elif page == "📝 Study Summary":

    st.title("📝 AI Study Summary")
    st.caption("Convert lengthy study material into focused revision notes.")

    if "pdf_text" not in st.session_state:

        st.info("📄 Upload a PDF first.")

    else:

        if st.button(
            "📚 Generate Summary",
            use_container_width=True
        ):

            with st.spinner("Creating summary..."):

                result = summarize_text(
                    st.session_state.pdf_text
                )

            st.markdown(result)


# ------------------------------------------------------------
# MCQ
# ------------------------------------------------------------

elif page == "❓ MCQ Generator":

    st.title("❓ AI MCQ Generator")
    st.caption("Practice with AI-generated questions from your study material.")

    if "pdf_text" not in st.session_state:

        st.info("📄 Upload a PDF first.")

    else:

        count = st.slider(
            "Number of MCQs",
            3,
            10,
            5
        )

        if st.button(
            "🎯 Generate MCQs",
            use_container_width=True
        ):

            with st.spinner("Generating MCQs..."):

                result = generate_mcqs(
                    st.session_state.pdf_text,
                    count
                )

            st.markdown(result)


# ------------------------------------------------------------
# IMPORTANT QUESTIONS
# ------------------------------------------------------------

elif page == "🎯 Important Questions":

    st.title("🎯 Important Exam Questions")
    st.caption("Identify high-value questions for exam preparation.")

    if "pdf_text" not in st.session_state:

        st.info("📄 Upload a PDF first.")

    else:

        count = st.slider(
            "Number of Questions",
            5,
            15,
            10
        )

        if st.button(
            "📌 Generate Questions",
            use_container_width=True
        ):

            with st.spinner("Analyzing notes..."):

                result = generate_important_questions(
                    st.session_state.pdf_text,
                    count
                )

            st.markdown(result)


# ------------------------------------------------------------
# CHAT HISTORY
# ------------------------------------------------------------

elif page == "💾 Chat History":

    st.title("💾 Chat History")
    st.caption("Review your previous AI study conversations.")

    history = get_chat_history()

    if history:

        for question, answer, chat_date in history:

            with st.expander(
                f"🕐 {chat_date}"
            ):

                st.write("**Question**")
                st.write(question)

                st.write("**AI Answer**")
                st.write(answer)

        if st.button("🗑️ Clear Chat History"):

            clear_chat_history()

            st.success("Chat history cleared.")

            st.rerun()

    else:

        st.info("💬 No chat history available.")


# ------------------------------------------------------------
# FOOTER
# ------------------------------------------------------------

st.divider()

st.caption(
    "AI College Assistant • "
    
)