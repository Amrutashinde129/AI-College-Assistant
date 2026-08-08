import streamlit as st
from streamlit_option_menu import option_menu

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
    clear_chat_history
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

</style>
""", unsafe_allow_html=True)


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
            "💬 AI Chat",
            "📝 Study Summary",
            "❓ MCQ Generator",
            "🎯 Important Questions",
            "💾 Chat History"
        ],
        icons=[
            "house",
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

        st.markdown(
            """
            ### 💬 AI Chat

            Ask questions about your uploaded
            college notes using RAG and Ollama.
            """
        )

    with col2:

        st.markdown(
            """
            ### 📝 Study Summary

            Convert lengthy study material into
            concise revision notes.
            """
        )

    with col3:

        st.markdown(
            """
            ### ❓ MCQ Generator

            Generate practice multiple-choice
            questions from your study material.
            """
        )

    col4, col5, col6 = st.columns(3)

    with col4:

        st.markdown(
            """
            ### 🎯 Exam Questions

            Generate important questions for
            examination preparation.
            """
        )

    with col5:

        st.markdown(
            """
            ### 💾 Chat History

            Keep track of your previous questions
            and AI answers.
            """
        )

    with col6:

        st.markdown(
            """
            ### 🤖 Local AI

            Powered by Ollama and Llama 3.2
            running locally.
            """
        )

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
        "Generate practice questions from your study material."
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
        "Generate important questions from your study material."
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
            date
        ) in history:

            with st.expander(
                f"🕐 {date}"
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