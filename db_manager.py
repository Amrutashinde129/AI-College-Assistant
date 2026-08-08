import sqlite3
import os
from datetime import datetime


DATABASE_FOLDER = "database"

os.makedirs(
    DATABASE_FOLDER,
    exist_ok=True
)

DB_NAME = os.path.join(
    DATABASE_FOLDER,
    "chat_history.db"
)


def create_table():

    connection = sqlite3.connect(DB_NAME)

    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    connection.commit()
    connection.close()


def save_chat(question, answer):

    connection = sqlite3.connect(DB_NAME)

    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO chat_history
        (question, answer, created_at)
        VALUES (?, ?, ?)
    """, (
        question,
        answer,
        datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    ))

    connection.commit()
    connection.close()


def get_chat_history():

    connection = sqlite3.connect(DB_NAME)

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

    connection = sqlite3.connect(DB_NAME)

    cursor = connection.cursor()

    cursor.execute(
        "DELETE FROM chat_history"
    )

    connection.commit()
    connection.close()