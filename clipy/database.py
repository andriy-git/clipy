
import sqlite3
import os
import time
from typing import List, Optional, Tuple
from .utils import get_data_dir

DB_PATH = os.path.join(get_data_dir(), "clipy.db")

def init_db():
    """Initialize the database schema."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS clips (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_hash TEXT UNIQUE,
            content_type TEXT, -- 'text' or 'image'
            content_value TEXT, -- Text content or Path to image
            timestamp REAL
        )
    ''')
    conn.commit()
    conn.close()

def _delete_files_for_ids(c, ids: List[int]):
    """Helper to delete image files associated with the given clip IDs."""
    if not ids:
        return
    
    # Get all image paths for these IDs
    placeholders = ','.join(['?'] * len(ids))
    c.execute(f"SELECT content_value FROM clips WHERE id IN ({placeholders}) AND content_type = 'image'", ids)
    for (file_path,) in c.fetchall():
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError:
                pass

def save_clip(content_value: str, content_type: str, content_hash: str, max_entries: int = 1000) -> None:
    """
    Save a clip to the database.
    If it exists, update the timestamp (move to top).
    If total count exceeds max_entries, delete oldest.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    timestamp = time.time()
    
    # Check if duplicate exists
    c.execute("SELECT id FROM clips WHERE content_hash = ?", (content_hash,))
    row = c.fetchone()
    
    if row:
        # Update existing
        c.execute("UPDATE clips SET timestamp = ? WHERE id = ?", (timestamp, row[0]))
    else:
        # Insert new
        c.execute("INSERT INTO clips (content_hash, content_type, content_value, timestamp) VALUES (?, ?, ?, ?)",
                  (content_hash, content_type, content_value, timestamp))
        
        # Enforce max_entries
        c.execute("SELECT COUNT(*) FROM clips")
        count = c.fetchone()[0]
        if count > max_entries:
            # Find IDs to delete
            to_delete_count = count - max_entries
            c.execute("SELECT id FROM clips ORDER BY timestamp ASC LIMIT ?", (to_delete_count,))
            ids_to_delete = [r[0] for r in c.fetchall()]
            
            # Delete files first
            _delete_files_for_ids(c, ids_to_delete)
            
            # Delete from DB
            placeholders = ','.join(['?'] * len(ids_to_delete))
            c.execute(f"DELETE FROM clips WHERE id IN ({placeholders})", ids_to_delete)
        
    conn.commit()
    conn.close()

def get_clips(limit: int = 50) -> List[Tuple[int, str, str, str, float]]:
    """Retrieve clips ordered by timestamp descending."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, content_hash, content_type, content_value, timestamp FROM clips ORDER BY timestamp DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    return rows

def get_clip_by_id(clip_id: int) -> Optional[Tuple[str, str]]:
    """Get clip content and type by ID."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT content_value, content_type FROM clips WHERE id = ?", (clip_id,))
    row = c.fetchone()
    conn.close()
    return row

def get_clip_by_value(content_value: str) -> Optional[Tuple[int, str, str]]:
    """Get clip ID, content, and type by matching content_value."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Try exact match
    c.execute("SELECT id, content_value, content_type FROM clips WHERE content_value = ?", (content_value,))
    row = c.fetchone()
    conn.close()
    return row

def get_clip_by_value_loose(content_value: str) -> Optional[Tuple[int, str, str]]:
    """Get clip by value, being tolerant of whitespace normalization."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # 1. Exact match
    c.execute("SELECT id, content_value, content_type FROM clips WHERE content_value = ?", (content_value,))
    row = c.fetchone()
    if row:
        conn.close()
        return row
    
    # 2. Trimmed match
    stripped = content_value.strip()
    c.execute("SELECT id, content_value, content_type FROM clips WHERE TRIM(content_value) = ?", (stripped,))
    row = c.fetchone()
    conn.close()
    return row

def delete_clip_by_id(clip_id: int):
    """Delete a clip by ID and remove its image file if needed."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    _delete_files_for_ids(c, [clip_id])
    c.execute("DELETE FROM clips WHERE id = ?", (clip_id,))
    conn.commit()
    conn.close()

def delete_clip_by_value(content_value: str):
    """Delete a clip by matching its content value."""
    # Find the ID first
    row = get_clip_by_value(content_value)
    if row:
        delete_clip_by_id(row[0])

def clear_history():
    """Clear all clips and reset autoincrement counter."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Delete all image files first
    c.execute("SELECT content_value FROM clips WHERE content_type = 'image'")
    image_paths = c.fetchall()
    for (file_path,) in image_paths:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError:
                pass

    c.execute("DELETE FROM clips")
    # Reset autoincrement counter
    c.execute("DELETE FROM sqlite_sequence WHERE name='clips'")
    conn.commit()
    conn.close()
