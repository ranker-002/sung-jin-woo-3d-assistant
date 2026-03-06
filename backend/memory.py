"""
memory.py – Gestion de la mémoire à long terme (SQLite).
Stocke le profil utilisateur, les préférences et l'historique des conversations.
"""
import sqlite3
import json
import os
from datetime import datetime
from pathlib import Path

DB_PATH = Path("backend/data/memory.db")
DB_PATH.parent.mkdir(exist_ok=True)

class LongTermMemory:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self._init_db()

    def _init_db(self):
        cursor = self.conn.cursor()
        # Table pour le profil et les préférences
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS profile (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        # Table pour l'historique intelligent (résumés ou faits marquants)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS facts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                category TEXT
            )
        ''')
        # Table pour les logs de chat (complet)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT,
                content TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.conn.commit()

    def get_preference(self, key, default=None):
        cursor = self.conn.cursor()
        cursor.execute("SELECT value FROM profile WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row[0] if row else default

    def set_preference(self, key, value):
        cursor = self.conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO profile (key, value) VALUES (?, ?)", (key, str(value)))
        self.conn.commit()

    def log_chat(self, role, content):
        cursor = self.conn.cursor()
        cursor.execute("INSERT INTO chat_logs (role, content) VALUES (?, ?)", (role, content))
        self.conn.commit()

    def add_fact(self, content, category="general"):
        cursor = self.conn.cursor()
        cursor.execute("INSERT INTO facts (content, category) VALUES (?, ?)", (content, category))
        self.conn.commit()

    def get_recent_history(self, limit=10):
        cursor = self.conn.cursor()
        cursor.execute("SELECT role, content FROM chat_logs ORDER BY timestamp DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        return [{"role": r, "content": c} for r, c in reversed(rows)]

    def get_all_facts(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT content FROM facts ORDER BY timestamp DESC")
        return [row[0] for row in cursor.fetchall()]

    def close(self):
        self.conn.close()

# Singleton
memory = LongTermMemory()
