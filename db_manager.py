import sqlite3
import os
from datetime import datetime


# =====================================================
# DATABASE CONFIGURATION
# =====================================================

DATABASE_FOLDER = "database"

os.makedirs(DATABASE_FOLDER, exist_ok=True)

DB_NAME = os.path.join(
    DATABASE_FOLDER,
    "chat_history.db"
)


# =====================================================
# DATABASE CONNECTION
# =====================================================

def get_connection():
    return sqlite3.connect(DB_NAME)


# =====================================================
# CREATE TABLES
# =====================================================

def create_table():

    connection = get_connection()
    cursor = connection.cursor()

    # -------------------------------------------------
    # CHAT HISTORY
    # -------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    # -------------------------------------------------
    # STUDENT PROFILE
    # -------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS student_profile (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            name TEXT,
            course TEXT,
            semester TEXT,
            subjects TEXT,
            exam_date TEXT,
            daily_study_hours REAL,
            preferred_study_time TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    """)

    # -------------------------------------------------
    # STUDY PLAN
    # -------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS study_plan (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT NOT NULL,
            topic TEXT,
            study_date TEXT NOT NULL,
            start_time TEXT,
            end_time TEXT,
            duration REAL,
            priority TEXT,
            status TEXT DEFAULT 'Pending',
            created_at TEXT NOT NULL
        )
    """)

    connection.commit()
    connection.close()


# =====================================================
# CHAT HISTORY
# =====================================================

def save_chat(question, answer):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO chat_history
        (question, answer, created_at)
        VALUES (?, ?, ?)
    """, (
        question,
        answer,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))

    connection.commit()
    connection.close()


def get_chat_history():

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT question, answer, created_at
        FROM chat_history
        ORDER BY id DESC
    """)

    history = cursor.fetchall()

    connection.close()

    return history


def clear_chat_history():

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        "DELETE FROM chat_history"
    )

    connection.commit()
    connection.close()


# =====================================================
# STUDENT PROFILE
# =====================================================

def save_student_profile(
    name,
    course,
    semester,
    subjects,
    exam_date,
    daily_study_hours,
    preferred_study_time
):

    connection = get_connection()
    cursor = connection.cursor()

    current_time = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    cursor.execute("""
        SELECT id
        FROM student_profile
        WHERE id = 1
    """)

    existing_profile = cursor.fetchone()

    if existing_profile:

        cursor.execute("""
            UPDATE student_profile
            SET
                name = ?,
                course = ?,
                semester = ?,
                subjects = ?,
                exam_date = ?,
                daily_study_hours = ?,
                preferred_study_time = ?,
                updated_at = ?
            WHERE id = 1
        """, (
            name,
            course,
            semester,
            subjects,
            exam_date,
            daily_study_hours,
            preferred_study_time,
            current_time
        ))

    else:

        cursor.execute("""
            INSERT INTO student_profile
            (
                id,
                name,
                course,
                semester,
                subjects,
                exam_date,
                daily_study_hours,
                preferred_study_time,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            1,
            name,
            course,
            semester,
            subjects,
            exam_date,
            daily_study_hours,
            preferred_study_time,
            current_time,
            current_time
        ))

    connection.commit()
    connection.close()


def get_student_profile():

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            name,
            course,
            semester,
            subjects,
            exam_date,
            daily_study_hours,
            preferred_study_time,
            created_at,
            updated_at
        FROM student_profile
        WHERE id = 1
    """)

    profile = cursor.fetchone()

    connection.close()

    if profile is None:
        return None

    return {
        "name": profile[0],
        "course": profile[1],
        "semester": profile[2],
        "subjects": profile[3],
        "exam_date": profile[4],
        "daily_study_hours": profile[5],
        "preferred_study_time": profile[6],
        "created_at": profile[7],
        "updated_at": profile[8]
    }


def update_student_profile(
    name=None,
    course=None,
    semester=None,
    subjects=None,
    exam_date=None,
    daily_study_hours=None,
    preferred_study_time=None
):

    profile = get_student_profile()

    if profile is None:
        return False

    name = (
        name if name is not None
        else profile["name"]
    )

    course = (
        course if course is not None
        else profile["course"]
    )

    semester = (
        semester if semester is not None
        else profile["semester"]
    )

    subjects = (
        subjects if subjects is not None
        else profile["subjects"]
    )

    exam_date = (
        exam_date if exam_date is not None
        else profile["exam_date"]
    )

    daily_study_hours = (
        daily_study_hours
        if daily_study_hours is not None
        else profile["daily_study_hours"]
    )

    preferred_study_time = (
        preferred_study_time
        if preferred_study_time is not None
        else profile["preferred_study_time"]
    )

    save_student_profile(
        name,
        course,
        semester,
        subjects,
        exam_date,
        daily_study_hours,
        preferred_study_time
    )

    return True


def delete_student_profile():

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        DELETE FROM student_profile
        WHERE id = 1
    """)

    connection.commit()
    connection.close()


def profile_exists():

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT id
        FROM student_profile
        WHERE id = 1
    """)

    result = cursor.fetchone()

    connection.close()

    return result is not None


# =====================================================
# STUDY PLANNER
# =====================================================

def save_study_plan(
    subject,
    topic,
    study_date,
    start_time,
    end_time,
    duration,
    priority="Medium",
    status="Pending"
):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO study_plan
        (
            subject,
            topic,
            study_date,
            start_time,
            end_time,
            duration,
            priority,
            status,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        subject,
        topic,
        study_date,
        start_time,
        end_time,
        duration,
        priority,
        status,
        datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    ))

    connection.commit()
    connection.close()


def get_study_plan():

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            id,
            subject,
            topic,
            study_date,
            start_time,
            end_time,
            duration,
            priority,
            status,
            created_at
        FROM study_plan
        ORDER BY study_date, start_time
    """)

    plans = cursor.fetchall()

    connection.close()

    return plans


def get_study_plan_by_date(study_date):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            id,
            subject,
            topic,
            study_date,
            start_time,
            end_time,
            duration,
            priority,
            status,
            created_at
        FROM study_plan
        WHERE study_date = ?
        ORDER BY start_time
    """, (study_date,))

    plans = cursor.fetchall()

    connection.close()

    return plans


def update_study_plan_status(
    plan_id,
    status
):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        UPDATE study_plan
        SET status = ?
        WHERE id = ?
    """, (
        status,
        plan_id
    ))

    connection.commit()
    connection.close()


def delete_study_plan(plan_id):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        DELETE FROM study_plan
        WHERE id = ?
    """, (plan_id,))

    connection.commit()
    connection.close()


def clear_study_plan():

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        "DELETE FROM study_plan"
    )

    connection.commit()
    connection.close()