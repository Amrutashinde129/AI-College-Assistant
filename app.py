import streamlit as st
from streamlit_option_menu import option_menu
from datetime import date, datetime, timedelta
import json
import re
import requests

from utils.pdf_processor import extract_text_from_pdf
from utils.vector_store import create_vector_store
from utils.rag import answer_question
from utils.summarizer import summarize_text
from utils.mcq_generator import generate_mcqs
from utils.important_questions import generate_important_questions

from db_manager import (
    create_table,
    save_chat,
    get_chat_history,
    clear_chat_history,

    save_student_profile,
    get_student_profile,

    save_study_plan,
    get_study_plan,
    get_study_plan_by_date,
    update_study_plan_status,
    delete_study_plan,
    clear_study_plan
)


# =====================================================
# PAGE CONFIGURATION
# =====================================================

st.set_page_config(
    page_title="AI College Assistant",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

create_table()


# =====================================================
# OLLAMA CONFIGURATION
# =====================================================

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2:1b"


# =====================================================
# CUSTOM CSS
# =====================================================

st.markdown("""
<style>

.main-title {
    font-size: 38px;
    font-weight: bold;
    text-align: center;
    margin-bottom: 5px;
}

.subtitle {
    text-align: center;
    font-size: 17px;
    margin-bottom: 30px;
}

.card {
    padding: 20px;
    border-radius: 15px;
    border: 1px solid #ddd;
    margin-bottom: 15px;
}

.profile-card {
    padding: 20px;
    border-radius: 15px;
    border: 1px solid #ddd;
    margin-bottom: 15px;
}

</style>
""", unsafe_allow_html=True)


# =====================================================
# AI STUDY TASK GENERATOR
# =====================================================

def generate_ai_study_tasks(profile):

    subjects = [
        subject.strip()
        for subject in profile["subjects"].split(",")
        if subject.strip()
    ]

    exam_date = profile["exam_date"]

    daily_hours = profile["daily_study_hours"]

    preferred_time = profile["preferred_study_time"]

    today = date.today()

    try:
        exam = date.fromisoformat(exam_date)
        days_remaining = (exam - today).days
    except:
        days_remaining = 7

    if days_remaining <= 0:
        days_remaining = 1

    # Generate tasks for maximum 7 days
    planning_days = min(days_remaining, 7)

    subject_text = ", ".join(subjects)

    prompt = f"""
You are an AI college study planner.

Create a personalized study plan for a diploma college student.

Student information:

Subjects:
{subject_text}

Daily available study hours:
{daily_hours}

Preferred study time:
{preferred_time}

Exam date:
{exam_date}

Days remaining:
{days_remaining}

Create study tasks for the next {planning_days} days.

Rules:

1. Use only the student's subjects.
2. Generate realistic study tasks.
3. Do not overload the student.
4. Each task should have a topic.
5. Include revision and practice tasks.
6. Priority must be High, Medium, or Low.
7. Duration must be between 0.5 and 2 hours.
8. Each day should fit within the student's available study hours.
9. Use dates starting from {today.isoformat()}.
10. Return ONLY valid JSON.
11. Do not add markdown.
12. Do not add explanations.

Return exactly this format:

[
    {{
        "subject": "Subject Name",
        "topic": "Topic to study",
        "study_date": "YYYY-MM-DD",
        "start_time": "18:00",
        "end_time": "19:00",
        "duration": 1.0,
        "priority": "High"
    }}
]
"""

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.2,
                "num_predict": 1500
            }
        },
        timeout=120
    )

    response.raise_for_status()

    result = response.json()

    ai_text = result.get("response", "").strip()

    # Remove markdown code fences if AI returns them
    ai_text = re.sub(
        r"```json|```",
        "",
        ai_text,
        flags=re.IGNORECASE
    ).strip()

    # Extract JSON array
    match = re.search(
        r"\[.*\]",
        ai_text,
        re.DOTALL
    )

    if not match:
        raise ValueError(
            "AI did not return valid study tasks."
        )

    json_text = match.group(0)

    tasks = json.loads(json_text)

    valid_tasks = []

    for task in tasks:

        required_fields = [
            "subject",
            "topic",
            "study_date",
            "start_time",
            "end_time",
            "duration",
            "priority"
        ]

        if not all(
            field in task
            for field in required_fields
        ):
            continue

        if task["subject"] not in subjects:
            continue

        if task["priority"] not in [
            "High",
            "Medium",
            "Low"
        ]:
            task["priority"] = "Medium"

        try:

            task_date = date.fromisoformat(
                task["study_date"]
            )

            if task_date < today:
                continue

            duration = float(
                task["duration"]
            )

            if duration <= 0:
                duration = 1.0

            if duration > 2:
                duration = 2.0

            task["duration"] = duration

            valid_tasks.append(task)

        except Exception:
            continue

    return valid_tasks


# =====================================================
# SIDEBAR
# =====================================================

with st.sidebar:

    st.title("🎓 AI College Assistant")

    st.caption("Your intelligent study companion")

    st.divider()

    selected = option_menu(
        "Navigation",
        [
            "🏠 Dashboard",
            "👤 Student Profile",
            "📅 Study Planner",
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
            "chat-dots",
            "file-text",
            "question-circle",
            "bullseye",
            "clock-history"
        ],
        menu_icon="cast",
        default_index=0
    )

    st.divider()

    st.subheader("📚 Study Material")

    uploaded_file = st.file_uploader(
        "Upload College PDF",
        type=["pdf"]
    )


# =====================================================
# PDF PROCESSING
# =====================================================

if uploaded_file:

    if (
        "vector_store" not in st.session_state
        or st.session_state.get("pdf_name")
        != uploaded_file.name
    ):

        with st.spinner("📄 Processing PDF..."):

            text = extract_text_from_pdf(
                uploaded_file
            )

            if text.strip():

                st.session_state.pdf_text = text

                st.session_state.vector_store = (
                    create_vector_store(text)
                )

                st.session_state.pdf_name = (
                    uploaded_file.name
                )

                st.success(
                    "✅ PDF processed successfully!"
                )

            else:

                st.error(
                    "❌ Could not extract text from PDF."
                )


# =====================================================
# DASHBOARD
# =====================================================

if selected == "🏠 Dashboard":

    st.markdown(
        '<div class="main-title">'
        '🎓 AI College Assistant'
        '</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="subtitle">'
        'Your AI-powered college study companion'
        '</div>',
        unsafe_allow_html=True
    )

    st.divider()

    st.subheader("🚀 What can you do?")

    col1, col2, col3 = st.columns(3)

    with col1:

        st.markdown("""
        ### 💬 AI Chat

        Ask questions about your uploaded
        college notes using AI and RAG.
        """)

    with col2:

        st.markdown("""
        ### 📝 Study Summary

        Convert lengthy study material into
        concise revision notes.
        """)

    with col3:

        st.markdown("""
        ### ❓ MCQ Generator

        Generate practice multiple-choice
        questions from your study material.
        """)

    col4, col5, col6 = st.columns(3)

    with col4:

        st.markdown("""
        ### 🎯 Important Questions

        Generate important questions for
        examination preparation.
        """)

    with col5:

        st.markdown("""
        ### 👤 Student Profile

        Store your academic information
        for personalized planning.
        """)

    with col6:

        st.markdown("""
        ### 📅 Study Planner

        Create and manage your
        personalized study schedule.
        """)

    st.divider()

    if "pdf_name" in st.session_state:

        st.success(
            f"📄 Current document: "
            f"{st.session_state.pdf_name}"
        )

    else:

        st.info(
            "👈 Upload a college PDF from the sidebar "
            "to get started."
        )


# =====================================================
# STUDENT PROFILE
# =====================================================

elif selected == "👤 Student Profile":

    st.title("👤 Student Profile")

    st.write(
        "Enter your academic information. "
        "This information will be used by the "
        "Smart Study Planner."
    )

    profile = get_student_profile()

    if profile:

        default_name = profile["name"] or ""

        default_course = profile["course"] or ""

        default_semester = profile["semester"] or ""

        default_subjects = profile["subjects"] or ""

        default_exam_date = profile["exam_date"]

        default_hours = (
            profile["daily_study_hours"]
            if profile["daily_study_hours"] is not None
            else 2.0
        )

        default_time = (
            profile["preferred_study_time"]
            or "Evening"
        )

    else:

        default_name = ""
        default_course = ""
        default_semester = ""
        default_subjects = ""
        default_exam_date = None
        default_hours = 2.0
        default_time = "Evening"

    with st.form("student_profile_form"):

        st.subheader("📋 Academic Information")

        name = st.text_input(
            "Student Name",
            value=default_name,
            placeholder="Enter your name"
        )

        col1, col2 = st.columns(2)

        with col1:

            course = st.text_input(
                "Course / Branch",
                value=default_course,
                placeholder="Example: Computer Engineering"
            )

        with col2:

            semester = st.text_input(
                "Semester",
                value=default_semester,
                placeholder="Example: 4th Semester"
            )

        subjects = st.text_area(
            "Subjects",
            value=default_subjects,
            placeholder=(
                "Enter subjects separated by commas\n"
                "Example: OOP, DBMS, DSU, DTE"
            )
        )

        st.subheader("📅 Study Information")

        exam_date = st.date_input(
            "Exam Date",
            value=(
                date.fromisoformat(
                    default_exam_date
                )
                if default_exam_date
                else date.today()
            ),
            min_value=date.today()
        )

        daily_study_hours = st.number_input(
            "Daily Available Study Hours",
            min_value=0.5,
            max_value=12.0,
            value=float(default_hours),
            step=0.5
        )

        study_times = [
            "Morning",
            "Afternoon",
            "Evening",
            "Night"
        ]

        preferred_study_time = st.selectbox(
            "Preferred Study Time",
            study_times,
            index=(
                study_times.index(default_time)
                if default_time in study_times
                else 2
            )
        )

        submitted = st.form_submit_button(
            "💾 Save Profile",
            use_container_width=True
        )

        if submitted:

            if not name.strip():

                st.warning(
                    "⚠️ Please enter your name."
                )

            elif not course.strip():

                st.warning(
                    "⚠️ Please enter your course/branch."
                )

            elif not semester.strip():

                st.warning(
                    "⚠️ Please enter your semester."
                )

            elif not subjects.strip():

                st.warning(
                    "⚠️ Please enter at least one subject."
                )

            else:

                save_student_profile(
                    name=name.strip(),
                    course=course.strip(),
                    semester=semester.strip(),
                    subjects=subjects.strip(),
                    exam_date=exam_date.isoformat(),
                    daily_study_hours=daily_study_hours,
                    preferred_study_time=preferred_study_time
                )

                st.success(
                    "✅ Student profile saved successfully!"
                )

                st.rerun()

    profile = get_student_profile()

    if profile:

        st.divider()

        st.subheader("📌 Saved Profile")

        col1, col2 = st.columns(2)

        with col1:

            st.info(
                f"👤 **Name:** {profile['name']}"
            )

            st.info(
                f"🎓 **Course:** {profile['course']}"
            )

            st.info(
                f"📚 **Semester:** {profile['semester']}"
            )

            st.info(
                f"📖 **Subjects:** {profile['subjects']}"
            )

        with col2:

            st.info(
                f"📅 **Exam Date:** "
                f"{profile['exam_date']}"
            )

            st.info(
                f"⏱️ **Daily Study Hours:** "
                f"{profile['daily_study_hours']} hours"
            )

            st.info(
                f"🕐 **Preferred Time:** "
                f"{profile['preferred_study_time']}"
            )


# =====================================================
# STUDY PLANNER
# =====================================================

elif selected == "📅 Study Planner":

    st.title("📅 Smart Study Planner")

    st.write(
        "Create and manage your personalized "
        "AI-powered study schedule."
    )

    profile = get_student_profile()

    if profile is None:

        st.warning(
            "⚠️ Please complete your Student Profile first."
        )

        st.info(
            "Go to 👤 Student Profile and enter your "
            "subjects, exam date and daily study hours."
        )

    else:

        st.success(
            f"👋 Welcome {profile['name']}!"
        )

        subjects = [
            subject.strip()
            for subject in profile["subjects"].split(",")
            if subject.strip()
        ]

        # =================================================
        # PROFILE SUMMARY
        # =================================================

        col1, col2, col3 = st.columns(3)

        with col1:

            st.metric(
                "📚 Subjects",
                len(subjects)
            )

        with col2:

            st.metric(
                "⏱️ Daily Study Hours",
                f"{profile['daily_study_hours']} hrs"
            )

        with col3:

            st.metric(
                "📅 Exam Date",
                profile["exam_date"]
            )

        # =================================================
        # PROGRESS BAR
        # =================================================

        st.divider()

        st.subheader("📊 Study Progress")

        all_plans = get_study_plan()

        if all_plans:

            total_tasks = len(all_plans)

            completed_tasks = sum(
                1
                for plan in all_plans
                if plan[8] == "Completed"
            )

            pending_tasks = (
                total_tasks - completed_tasks
            )

            progress = (
                completed_tasks / total_tasks
            )

            col1, col2, col3 = st.columns(3)

            with col1:

                st.metric(
                    "📚 Total Tasks",
                    total_tasks
                )

            with col2:

                st.metric(
                    "✅ Completed",
                    completed_tasks
                )

            with col3:

                st.metric(
                    "⏳ Pending",
                    pending_tasks
                )

            st.progress(
                progress,
                text=f"{int(progress * 100)}% Completed"
            )

        else:

            st.info(
                "📭 No study tasks yet."
            )

        # =================================================
        # DAYS REMAINING
        # =================================================

        if profile["exam_date"]:

            try:

                exam = date.fromisoformat(
                    profile["exam_date"]
                )

                days_remaining = (
                    exam - date.today()
                ).days

                if days_remaining > 0:

                    st.info(
                        f"⏳ **{days_remaining} days "
                        f"remaining for your exam.**"
                    )

                elif days_remaining == 0:

                    st.warning(
                        "📢 Your exam is today!"
                    )

                else:

                    st.warning(
                        "⚠️ Your exam date has passed. "
                        "Update it in Student Profile."
                    )

            except ValueError:

                pass

        st.divider()

        # =================================================
        # AI GENERATED STUDY PLAN
        # =================================================

        st.subheader("🤖 AI Study Plan")

        st.write(
            "Generate personalized study tasks "
            "automatically using your student profile."
        )

        if st.button(
            "🤖 Generate AI Study Plan",
            use_container_width=True
        ):

            with st.spinner(
                "🧠 AI is creating your study plan..."
            ):

                try:

                    generated_tasks = (
                        generate_ai_study_tasks(
                            profile
                        )
                    )

                    if generated_tasks:

                        added_count = 0

                        for task in generated_tasks:

                            save_study_plan(
                                subject=task["subject"],
                                topic=task["topic"],
                                study_date=task["study_date"],
                                start_time=task["start_time"],
                                end_time=task["end_time"],
                                duration=task["duration"],
                                priority=task["priority"],
                                status="Pending"
                            )

                            added_count += 1

                        st.success(
                            f"✅ AI generated "
                            f"{added_count} study tasks!"
                        )

                        st.rerun()

                    else:

                        st.warning(
                            "⚠️ AI could not generate "
                            "valid study tasks."
                        )

                except requests.exceptions.ConnectionError:

                    st.error(
                        "❌ Ollama is not running. "
                        "Please start Ollama and try again."
                    )

                except Exception as e:

                    st.error(
                        f"❌ AI Study Plan Error: {e}"
                    )

        st.divider()

        # =================================================
        # ADD MANUAL STUDY TASK
        # =================================================

        st.subheader("➕ Add Study Task")

        if subjects:

            with st.form("study_plan_form"):

                col1, col2 = st.columns(2)

                with col1:

                    subject = st.selectbox(
                        "📚 Subject",
                        subjects
                    )

                    topic = st.text_input(
                        "📖 Topic / Chapter",
                        placeholder="Example: Inheritance"
                    )

                    study_date = st.date_input(
                        "📅 Study Date",
                        value=date.today()
                    )

                with col2:

                    start_time = st.time_input(
                        "⏰ Start Time"
                    )

                    end_time = st.time_input(
                        "⏰ End Time"
                    )

                    duration = st.number_input(
                        "⏱️ Duration (hours)",
                        min_value=0.25,
                        max_value=12.0,
                        value=1.0,
                        step=0.25
                    )

                priority = st.selectbox(
                    "🔥 Priority",
                    [
                        "High",
                        "Medium",
                        "Low"
                    ]
                )

                submit_plan = st.form_submit_button(
                    "💾 Add to Study Plan",
                    use_container_width=True
                )

                if submit_plan:

                    if not topic.strip():

                        st.warning(
                            "⚠️ Please enter a topic."
                        )

                    elif end_time <= start_time:

                        st.warning(
                            "⚠️ End time must be after "
                            "start time."
                        )

                    else:

                        save_study_plan(
                            subject=subject,
                            topic=topic.strip(),
                            study_date=study_date.isoformat(),
                            start_time=start_time.strftime(
                                "%H:%M"
                            ),
                            end_time=end_time.strftime(
                                "%H:%M"
                            ),
                            duration=duration,
                            priority=priority,
                            status="Pending"
                        )

                        st.success(
                            "✅ Study task added successfully!"
                        )

                        st.rerun()

        else:

            st.warning(
                "⚠️ No subjects found. "
                "Please update your Student Profile."
            )

        st.divider()

        # =================================================
        # TODAY'S PLAN
        # =================================================

        st.subheader("📋 Today's Study Plan")

        today = date.today().isoformat()

        today_plans = get_study_plan_by_date(
            today
        )

        if today_plans:

            for plan in today_plans:

                (
                    plan_id,
                    subject,
                    topic,
                    plan_date,
                    start_time,
                    end_time,
                    duration,
                    priority,
                    status,
                    created_at
                ) = plan

                with st.container(border=True):

                    col1, col2, col3 = st.columns(
                        [3, 2, 1]
                    )

                    with col1:

                        st.markdown(
                            f"### 📚 {subject}"
                        )

                        st.write(
                            f"**Topic:** {topic}"
                        )

                    with col2:

                        st.write(
                            f"⏰ {start_time} - {end_time}"
                        )

                        st.write(
                            f"⏱️ {duration} hours"
                        )

                        st.write(
                            f"🔥 Priority: {priority}"
                        )

                    with col3:

                        if status == "Completed":

                            st.success(
                                "✅ Completed"
                            )

                        else:

                            if st.button(
                                "✅ Complete",
                                key=f"complete_{plan_id}"
                            ):

                                update_study_plan_status(
                                    plan_id,
                                    "Completed"
                                )

                                st.rerun()

                        if st.button(
                            "🗑️ Delete",
                            key=f"delete_{plan_id}"
                        ):

                            delete_study_plan(
                                plan_id
                            )

                            st.rerun()

        else:

            st.info(
                "📭 No study tasks planned for today."
            )

        # =================================================
        # ALL STUDY PLANS
        # =================================================

        st.divider()

        st.subheader("📚 All Study Plans")

        all_plans = get_study_plan()

        if all_plans:

            for plan in all_plans:

                (
                    plan_id,
                    subject,
                    topic,
                    plan_date,
                    start_time,
                    end_time,
                    duration,
                    priority,
                    status,
                    created_at
                ) = plan

                status_icon = (
                    "✅"
                    if status == "Completed"
                    else "⏳"
                )

                st.write(
                    f"{status_icon} **{plan_date}** | "
                    f"**{subject}** | "
                    f"{topic} | "
                    f"{start_time}-{end_time} | "
                    f"🔥 {priority}"
                )

            st.divider()

            if st.button(
                "🗑️ Clear All Study Plans"
            ):

                clear_study_plan()

                st.success(
                    "All study plans cleared."
                )

                st.rerun()

        else:

            st.info(
                "📭 No study plans available."
            )


# =====================================================
# AI CHAT
# =====================================================

elif selected == "💬 AI Chat":

    st.title("💬 AI Chat")

    st.write(
        "Ask questions based on your uploaded college notes."
    )

    question = st.text_input(
        "Enter your question:",
        placeholder="Example: What is normalization?"
    )

    if st.button(
        "🤖 Ask AI",
        key="ask_ai"
    ):

        if not question.strip():

            st.warning(
                "⚠️ Please enter a question."
            )

        elif "vector_store" not in st.session_state:

            st.warning(
                "⚠️ Please upload a PDF first."
            )

        else:

            with st.spinner(
                "🔎 Searching your notes..."
            ):

                answer = answer_question(
                    st.session_state.vector_store,
                    question
                )

            st.subheader("🤖 AI Answer")

            st.write(answer)

            save_chat(
                question,
                answer
            )

            st.success(
                "💾 Chat saved successfully!"
            )


# =====================================================
# STUDY SUMMARY
# =====================================================

elif selected == "📝 Study Summary":

    st.title("📝 AI Study Summary")

    st.write(
        "Generate concise study notes from your PDF."
    )

    if "pdf_text" in st.session_state:

        if st.button(
            "📚 Generate Summary",
            key="summary"
        ):

            with st.spinner(
                "🧠 Creating study notes..."
            ):

                summary = summarize_text(
                    st.session_state.pdf_text
                )

            st.markdown(summary)

    else:

        st.info(
            "📄 Upload a PDF first."
        )


# =====================================================
# MCQ GENERATOR
# =====================================================

elif selected == "❓ MCQ Generator":

    st.title("❓ AI MCQ Generator")

    st.write(
        "Generate practice questions from your "
        "study material."
    )

    if "pdf_text" in st.session_state:

        number_of_questions = st.slider(
            "Number of MCQs",
            min_value=3,
            max_value=10,
            value=5,
            key="mcq_count"
        )

        if st.button(
            "🎯 Generate MCQs",
            key="generate_mcqs"
        ):

            with st.spinner(
                "🤖 Generating MCQs..."
            ):

                mcqs = generate_mcqs(
                    st.session_state.pdf_text,
                    number_of_questions
                )

            st.markdown(mcqs)

    else:

        st.info(
            "📄 Upload a PDF first."
        )


# =====================================================
# IMPORTANT QUESTIONS
# =====================================================

elif selected == "🎯 Important Questions":

    st.title("🎯 Important Exam Questions")

    st.write(
        "Generate important questions from your "
        "study material."
    )

    if "pdf_text" in st.session_state:

        question_count = st.slider(
            "Number of questions",
            min_value=5,
            max_value=15,
            value=10,
            key="important_count"
        )

        if st.button(
            "📌 Generate Questions",
            key="important_questions"
        ):

            with st.spinner(
                "🧠 Analyzing study material..."
            ):

                questions = (
                    generate_important_questions(
                        st.session_state.pdf_text,
                        question_count
                    )
                )

            st.markdown(questions)

    else:

        st.info(
            "📄 Upload a PDF first."
        )


# =====================================================
# CHAT HISTORY
# =====================================================

elif selected == "💾 Chat History":

    st.title("💾 Chat History")

    history = get_chat_history()

    if history:

        for (
            question_text,
            answer_text,
            chat_date
        ) in history:

            with st.expander(
                f"🕐 {chat_date}"
            ):

                st.markdown(
                    "**Question:**"
                )

                st.write(
                    question_text
                )

                st.markdown(
                    "**AI Answer:**"
                )

                st.write(
                    answer_text
                )

        st.divider()

        if st.button(
            "🗑️ Clear Chat History"
        ):

            clear_chat_history()

            st.success(
                "Chat history cleared."
            )

            st.rerun()

    else:

        st.info(
            "💬 No chat history available."
        )


# =====================================================
# FOOTER
# =====================================================

st.divider()

st.caption(
    "🎓 AI College Assistant | "
    "Python • Streamlit • RAG • FAISS • Ollama"
)