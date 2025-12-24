import argparse
import sys
import os
import signal
import subprocess
import fcntl
import re
from typing import Optional, Tuple

from .database import init_db, save_clip, get_clips, get_clip_by_id, clear_history, delete_clip_by_id, delete_clip_by_value, get_clip_by_value_loose
from .backend import get_backend
from .config import load_config
from .utils import format_timestamp, get_data_dir, get_image_dir, calculate_hash

def cmd_daemon(args):
    """Starts the clipboard watcher daemon."""
    init_db()
    
    # Ensure only one instance is running using a lock file
    lock_path = os.path.join(get_data_dir(), "daemon.lock")
    lock_file = open(lock_path, "w")
    try:
        fcntl.lockf(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # Write current PID to the lock file
        lock_file.write(str(os.getpid()))
        lock_file.flush()
    except IOError:
        print("Error: Clipy daemon is already running.", file=sys.stderr)
        sys.exit(1)

    backend = get_backend()
    
    # Handle SIGINT to exit gracefully
    def signal_handler(sig, frame):
        print("\nStopping Clipy Daemon.", file=sys.stderr)
        sys.exit(0)
    signal.signal(signal.SIGINT, signal_handler)

    print("Starting Clipy Daemon...", file=sys.stderr)
    # Use python3 -m clipy.cli for callbacks to handle the package structure correctly
    executable = [sys.executable, "-m", "clipy.cli"]
    
    backend.start_watcher(executable)

def cmd_add(args):
    """Adds current clipboard content to history. Called by watchers."""
    # This command is usually called by the watcher process.
    # It fetches the current clipboard content using the backend and saves it.
    init_db()
    config = load_config()
    backend = get_backend()
    
    # Check blacklist (case-insensitive)
    active_class = backend.get_active_window_class()
    if active_class:
        blacklist = [b.lower() for b in config.get("blacklist", [])]
        if active_class.lower() in blacklist:
            # Skip saving if blacklisted
            return

    content_value, content_type, content_hash = backend.get_content()
    
    if content_value and content_hash:
        save_clip(content_value, content_type, content_hash, max_entries=config.get("max_entries", 1000))

def cmd_list(args):
    """Lists history to stdout."""
    init_db()
    clips = get_clips(limit=args.limit)
    
    for clip in clips:
        clip_id, _, content_type, content_value, timestamp = clip
        # Format: [ID] [Type] Content
        # Escape newlines for single line display
        if content_type == "text":
            display_value = content_value.replace('\n', '\\n')
            # Only truncate if NOT in simple mode and NOT requested full
            if not args.full and not args.simple:
                display_value = display_value[:100]
        else:
            if os.path.exists(content_value):
                display_value = f"[Image] {content_value}"
            else:
                display_value = f"[Image] [Missing] {content_value}"
            
        if args.simple:
            print(display_value)
        else:
            print(f"{clip_id} [{content_type[0].upper()}] {display_value}")

def cmd_recall(args):
    """Recalls a clip by ID or from stdin selection."""
    init_db()
    clip_id = args.id
    input_line = None
    
    # If no ID provided, try reading from stdin (piped from fzf/rofi)
    if clip_id is None:
        if not sys.stdin.isatty():
             # Use rstrip('\n') to handle rofi output without killing important leading spaces
             input_line = sys.stdin.read().rstrip('\n')
             if not input_line: return
             # Identify the clip ID from pickers (fzf, rofi) that prefix lines with metadata.
             import re
             match_id = re.match(r'^(\d+) \[[A-Z]\] ', input_line)
             if match_id:
                 try:
                     clip_id = int(match_id.group(1))
                 except ValueError:
                     clip_id = None
             else:
                 clip_id = None
    
    backend = get_backend()
    if clip_id is not None:
        clip = get_clip_by_id(clip_id)
        if clip:
            content_value, content_type = clip
            if content_type == "image" and not os.path.exists(content_value):
                print(f"Error: Image clip {clip_id} file is missing (likely cleared from /tmp).", file=sys.stderr)
                return
            backend.set_content(content_value, content_type)
            print(f"Restored clip {clip_id}", file=sys.stderr)
            return

    # If still no clip, try matching by content
    if input_line:
        match = find_clip_from_input(input_line)
        if match:
            c_id, c_val, c_type = match
            if c_type == "image" and not os.path.exists(c_val):
                print(f"Error: Image clip {c_id} file is missing (likely cleared from /tmp).", file=sys.stderr)
                return
            backend.set_content(c_val, c_type)
            print(f"Restored clip {c_id}", file=sys.stderr)
        else:
            print("Clip not found by content.", file=sys.stderr)

def find_clip_from_input(input_line: str):
    """
    Attempts to map a picker's selection back to a database entry.
    This handles common transformations like newline escaping or picker-added prefixes.
    """
    # 1. Generate permutations (exact, unescaped, stripped, etc.)
    base = [input_line, input_line.replace('\\n', '\n')]
    configs = []
    seen = set()
    
    for b in base:
        for p in [b, b.strip(), b + '\n', b.strip() + '\n']:
            if p not in seen:
                configs.append(p)
                seen.add(p)

    for c in configs:
        match = get_clip_by_value_loose(c)
        if match: return match
        
    # 2. Handle specific picker artifacts like Image prefixes
    prefixes = ["[Image] [Missing] ", "[Image] "]
    for p in prefixes:
        if input_line.startswith(p):
            img_path = input_line[len(p):].strip()
            match = get_clip_by_value_loose(img_path)
            if match: return match
            
    # 3. Fallback: Substring matching if the picker or shell modified the content.
    all_clips = get_clips(limit=250)
    for row in all_clips:
        c_id, _, c_type, c_val, _ = row
        # Flatten everything for comparison
        c_val_flat = c_val.replace('\n', '\\n').replace('\r', '').strip()
        input_flat = input_line.replace('\r', '').strip()
        if input_flat and (input_flat in c_val_flat or c_val_flat in input_flat):
            return (c_id, c_val, c_type)

    return None

def cmd_delete(args):
    """Deletes a clip by ID or from stdin selection."""
    init_db()
    clip_id = args.id
    input_line = None
    
    # If no ID provided, try reading from stdin
    if clip_id is None:
        if not sys.stdin.isatty():
             input_line = sys.stdin.read().rstrip('\n')
             if not input_line: return
             # Try parsing ID from the beginning of line with strict regex for ID [Type]
             match_id = re.match(r'^\s*(\d+)\s+\[[A-Z]\]', input_line)
             if match_id:
                 try:
                     clip_id = int(match_id.group(1))
                 except ValueError:
                     clip_id = None
    
    if clip_id is not None:
        # Verify the ID exists or just try to delete it
        delete_clip_by_id(clip_id)
        print(f"Deleted clip {clip_id}", file=sys.stderr)
    elif input_line:
        # Match by content
        match = find_clip_from_input(input_line)
        if match:
            c_id, _, _ = match
            delete_clip_by_id(c_id)
            print(f"Deleted clip {c_id}", file=sys.stderr)
        else:
            # Fallback: if the input_line is just a number, treat it as an ID
            if input_line.isdigit():
                try:
                    c_id = int(input_line)
                    delete_clip_by_id(c_id)
                    print(f"Deleted clip {c_id}", file=sys.stderr)
                    return
                except ValueError: pass
            print("Clip not found by content.", file=sys.stderr)


def cmd_status(args):
    """Checks if the Clipy daemon is running."""
    lock_path = os.path.join(get_data_dir(), "daemon.lock")
    
    if not os.path.exists(lock_path):
        print("Clipy Daemon is NOT running.")
        return

    try:
        # Try to acquire the lock. If it fails, the daemon is running.
        with open(lock_path, "r") as f:
            fcntl.lockf(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            # If we reached here, we got the lock, so the daemon ISN'T running
            # Even if the file exists from a previous crash.
            print("Clipy Daemon is NOT running.")
    except IOError:
        # Lock is held by another process
        pid = "Unknown"
        try:
            with open(lock_path, "r") as f:
                pid = f.read().strip()
        except: pass
        
        print(f"Clipy Daemon is RUNNING (PID: {pid})")
        
        # Check backend specifics
        try:
            backend = get_backend()
            print(f"Active Backend: {backend.__class__.__name__}")
        except: pass
    except Exception as e:
        print(f"Error checking status: {e}", file=sys.stderr)

def cmd_clear(args):
    """Clears history."""
    init_db()
    try:
        clear_history(pattern=args.regex)
        if args.regex:
            print(f"History cleared for pattern: {args.regex}", file=sys.stderr)
        else:
            print("History cleared.", file=sys.stderr)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Clipy - Clipboard Manager")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # Daemon
    p_daemon = subparsers.add_parser("daemon", help="Start background watcher")
    p_daemon.set_defaults(func=cmd_daemon)
    
    # Add (Internal)
    p_add = subparsers.add_parser("add", help="Internal usage: Add current clipboard to DB")
    p_add.set_defaults(func=cmd_add)
    
    # List
    p_list = subparsers.add_parser("list", help="List clipboard history")
    p_list.add_argument("-n", "--limit", type=int, default=50, help="Number of items to show")
    p_list.add_argument("-s", "--simple", action="store_true", help="Only show content (for pickers)")
    p_list.add_argument("-f", "--full", action="store_true", help="Show full content without truncation")
    p_list.set_defaults(func=cmd_list)
    
    # Recall
    p_recall = subparsers.add_parser("recall", help="Restore clip to clipboard")
    p_recall.add_argument("id", type=int, nargs='?', help="ID of clip to restore")
    p_recall.set_defaults(func=cmd_recall)
    
    # Clear
    p_clear = subparsers.add_parser("clear", help="Clear all history or specific entries with regex")
    p_clear.add_argument("regex", nargs='?', help="Optional regex pattern to clear specific entries")
    p_clear.set_defaults(func=cmd_clear)
    
    # Status
    p_status = subparsers.add_parser("status", help="Check daemon status")
    p_status.set_defaults(func=cmd_status)
    
    # Delete
    p_delete = subparsers.add_parser("delete", help="Delete a clip")
    p_delete.add_argument("id", type=int, nargs='?', help="ID of clip to delete")
    p_delete.set_defaults(func=cmd_delete)
    
    
    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
