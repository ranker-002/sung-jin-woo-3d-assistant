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
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT,
                content TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # Stats de progression (Mode Donjon)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stats (
                key TEXT PRIMARY KEY,
                value INTEGER DEFAULT 0
            )
        ''')
        cursor.execute("INSERT OR IGNORE INTO stats (key, value) VALUES ('xp', 0)")
        cursor.execute("INSERT OR IGNORE INTO stats (key, value) VALUES ('level', 1)")
        # Table pour les résumés de sessions
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.conn.commit()

    def add_xp(self, amount):
        cursor = self.conn.cursor()
        cursor.execute("SELECT value FROM stats WHERE key = 'xp'")
        old_xp = cursor.fetchone()[0]
        old_lvl = int((old_xp / 100) ** 0.5) + 1
        
        new_xp = old_xp + amount
        cursor.execute("UPDATE stats SET value = ? WHERE key = 'xp'", (new_xp,))
        
        new_lvl = int((new_xp / 100) ** 0.5) + 1
        leveled_up = new_lvl > old_lvl
        
        cursor.execute("UPDATE stats SET value = ? WHERE key = 'level'", (new_lvl,))
        self.conn.commit()
        return new_xp, new_lvl, leveled_up

    def get_stats(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT key, value FROM stats")
        return dict(cursor.fetchall())

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

    def search_relevant_facts(self, query, limit=5):
        """Recherche simple par mots-clés pour simuler une mémoire sémantique."""
        if not query: return []
        words = [w.lower() for w in query.split() if len(w) > 3]
        if not words: return self.get_all_facts()[:limit]

        all_facts = self.get_all_facts()
        scored_facts = []
        for fact in all_facts:
            score = sum(1 for word in words if word in fact.lower())
            if score > 0:
                scored_facts.append((score, fact))
        
        scored_facts.sort(key=lambda x: x[0], reverse=True)
        return [f[1] for f in scored_facts[:limit]]

    def add_summary(self, content):
        cursor = self.conn.cursor()
        cursor.execute("INSERT INTO summaries (content) VALUES (?)", (content,))
        self.conn.commit()

    def get_last_summary(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT content FROM summaries ORDER BY timestamp DESC LIMIT 1")
        row = cursor.fetchone()
        return row[0] if row else ""

    def close(self):
        self.conn.close()

# Singleton
memory = LongTermMemory()
