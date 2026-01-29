import sqlite3
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

DB_PATH = "data/policies.db"

@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_database():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS policies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                category TEXT NOT NULL,
                target_audience TEXT NOT NULL,
                description TEXT,
                status TEXT DEFAULT 'draft',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS policy_contents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                policy_id INTEGER NOT NULL,
                content_type TEXT NOT NULL,
                content_data TEXT NOT NULL,
                metadata TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (policy_id) REFERENCES policies(id)
            )
        """)
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS policy_performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                policy_id INTEGER NOT NULL,
                view_count INTEGER DEFAULT 0,
                engagement_score REAL DEFAULT 0.0,
                feedback_data TEXT,
                metrics_data TEXT,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (policy_id) REFERENCES policies(id)
            )
        """)
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS generated_media (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                policy_id INTEGER NOT NULL,
                media_type TEXT NOT NULL,
                media_url TEXT,
                media_data BLOB,
                prompt TEXT,
                generation_params TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (policy_id) REFERENCES policies(id)
            )
        """)
        
        conn.commit()

def create_policy(title: str, category: str, target_audience: str, description: str = "") -> int:
    now = datetime.now().isoformat()
    with get_db() as conn:
        cursor = conn.execute("""
            INSERT INTO policies (title, category, target_audience, description, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'draft', ?, ?)
        """, (title, category, target_audience, description, now, now))
        conn.commit()
        return cursor.lastrowid

def update_policy_status(policy_id: int, status: str):
    now = datetime.now().isoformat()
    with get_db() as conn:
        conn.execute("""
            UPDATE policies SET status = ?, updated_at = ? WHERE id = ?
        """, (status, now, policy_id))
        conn.commit()

def save_policy_content(policy_id: int, content_type: str, content_data: Dict[str, Any], metadata: Optional[Dict] = None):
    now = datetime.now().isoformat()
    with get_db() as conn:
        conn.execute("""
            INSERT INTO policy_contents (policy_id, content_type, content_data, metadata, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (
            policy_id,
            content_type,
            json.dumps(content_data, ensure_ascii=False),
            json.dumps(metadata or {}, ensure_ascii=False),
            now
        ))
        conn.commit()

def save_generated_media(policy_id: int, media_type: str, media_data: bytes, prompt: str, params: Dict[str, Any]):
    now = datetime.now().isoformat()
    with get_db() as conn:
        conn.execute("""
            INSERT INTO generated_media (policy_id, media_type, media_data, prompt, generation_params, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            policy_id,
            media_type,
            media_data,
            prompt,
            json.dumps(params, ensure_ascii=False),
            now
        ))
        conn.commit()

def get_policy(policy_id: int) -> Optional[Dict[str, Any]]:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM policies WHERE id = ?", (policy_id,)).fetchone()
        if row:
            return dict(row)
        return None

def get_all_policies(limit: int = 50) -> List[Dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute("""
            SELECT * FROM policies ORDER BY created_at DESC LIMIT ?
        """, (limit,)).fetchall()
        return [dict(row) for row in rows]

def search_policies(keyword: str, category: Optional[str] = None, limit: int = 30) -> List[Dict[str, Any]]:
    with get_db() as conn:
        if category:
            rows = conn.execute("""
                SELECT * FROM policies 
                WHERE (title LIKE ? OR description LIKE ?) AND category = ?
                ORDER BY created_at DESC LIMIT ?
            """, (f"%{keyword}%", f"%{keyword}%", category, limit)).fetchall()
        else:
            rows = conn.execute("""
                SELECT * FROM policies 
                WHERE title LIKE ? OR description LIKE ?
                ORDER BY created_at DESC LIMIT ?
            """, (f"%{keyword}%", f"%{keyword}%", limit)).fetchall()
        return [dict(row) for row in rows]

def get_policy_contents(policy_id: int) -> List[Dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute("""
            SELECT * FROM policy_contents WHERE policy_id = ? ORDER BY created_at DESC
        """, (policy_id,)).fetchall()
        results = []
        for row in rows:
            data = dict(row)
            data['content_data'] = json.loads(data['content_data'])
            data['metadata'] = json.loads(data['metadata']) if data['metadata'] else {}
            results.append(data)
        return results

def get_generated_media(policy_id: int, media_type: Optional[str] = None) -> List[Dict[str, Any]]:
    with get_db() as conn:
        if media_type:
            rows = conn.execute("""
                SELECT * FROM generated_media WHERE policy_id = ? AND media_type = ? ORDER BY created_at DESC
            """, (policy_id, media_type)).fetchall()
        else:
            rows = conn.execute("""
                SELECT * FROM generated_media WHERE policy_id = ? ORDER BY created_at DESC
            """, (policy_id,)).fetchall()
        
        results = []
        for row in rows:
            data = dict(row)
            data['generation_params'] = json.loads(data['generation_params']) if data['generation_params'] else {}
            results.append(data)
        return results

def update_performance_metrics(policy_id: int, metrics: Dict[str, Any]):
    now = datetime.now().isoformat()
    with get_db() as conn:
        existing = conn.execute("""
            SELECT id FROM policy_performance WHERE policy_id = ?
        """, (policy_id,)).fetchone()
        
        if existing:
            conn.execute("""
                UPDATE policy_performance 
                SET metrics_data = ?, updated_at = ?
                WHERE policy_id = ?
            """, (json.dumps(metrics, ensure_ascii=False), now, policy_id))
        else:
            conn.execute("""
                INSERT INTO policy_performance (policy_id, metrics_data, updated_at)
                VALUES (?, ?, ?)
            """, (policy_id, json.dumps(metrics, ensure_ascii=False), now))
        conn.commit()

def get_policies_by_date(date_str: str) -> List[Dict[str, Any]]:
    """특정 날짜에 생성된 정책 목록 조회 (YYYY-MM-DD)"""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT * FROM policies 
            WHERE date(created_at) = date(?)
            ORDER BY created_at DESC
        """, (date_str,)).fetchall()
        return [dict(row) for row in rows]

def get_policies_by_date_range(start_date: str, end_date: str) -> List[Dict[str, Any]]:
    """날짜 범위로 정책 목록 조회"""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT * FROM policies 
            WHERE date(created_at) BETWEEN date(?) AND date(?)
            ORDER BY created_at DESC
        """, (start_date, end_date)).fetchall()
        return [dict(row) for row in rows]

def get_policies_by_month(year: int, month: int) -> List[Dict[str, Any]]:
    """특정 월의 정책 목록 조회"""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT * FROM policies 
            WHERE strftime('%Y', created_at) = ? 
            AND strftime('%m', created_at) = ?
            ORDER BY created_at DESC
        """, (str(year), f"{month:02d}")).fetchall()
        return [dict(row) for row in rows]
