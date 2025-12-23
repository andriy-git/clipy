
import abc
import subprocess
import time
import os
import sys
import shutil
from typing import Tuple, Optional
from .utils import get_image_dir, calculate_hash

class ClipboardBackend(abc.ABC):
    @abc.abstractmethod
    def start_watcher(self, clipy_executable_cmd: list[str]):
        """Starts the clipboard watcher process.
        
        Args:
            clipy_executable_cmd: Command list to run clipy, e.g. ['python3', '/path/to/clipy.py']
        """
        pass

    @abc.abstractmethod
    def get_content(self) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Returns (content_value, content_type, content_hash).
        content_type is 'text' or 'image'.
        """
        pass

    @abc.abstractmethod
    def set_content(self, content_value: str, content_type: str):
        """Sets the clipboard content."""
        pass

    @abc.abstractmethod
    def get_active_window_class(self) -> Optional[str]:
        """Returns the class/name of the currently active window."""
        pass


class WaylandBackend(ClipboardBackend):
    def start_watcher(self, clipy_executable_cmd: list[str]):
        # Use wl-paste --watch to execute the command on every clipboard change.
        # Format: ["wl-paste", "--watch", arg1, arg2, ..., "add"]
        cmd = ["wl-paste", "--watch"] + clipy_executable_cmd + ["add"]
        # This call blocks execution until the watcher process is killed.
        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            print(f"Error starting watcher: {e}", file=sys.stderr)
        except KeyboardInterrupt:
            pass

    def get_content(self) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        # Check types
        try:
            types = subprocess.check_output(["wl-paste", "--list-types"], stderr=subprocess.DEVNULL).decode().splitlines()
        except subprocess.CalledProcessError:
            return None, None, None

        if "text/plain" in types or "text/plain;charset=utf-8" in types:
            try:
                content = subprocess.check_output(["wl-paste", "--no-newline"], stderr=subprocess.DEVNULL).decode('utf-8')
                if not content:
                    return None, None, None
                return content, "text", calculate_hash(content.encode('utf-8'))
            except Exception:
                pass # Fallback to check image
        
        # Check for image
        image_types = [t for t in types if t.startswith("image/")]
        if image_types:
            try:
                # Images are read into memory to calculate a stable hash for deduplication.
                content_bytes = subprocess.check_output(["wl-paste", "--no-newline"], stderr=subprocess.DEVNULL)
                content_hash = calculate_hash(content_bytes)
                
                # Save to specific file path based on hash
                image_dir = get_image_dir()
                file_path = os.path.join(image_dir, f"{content_hash}.png")
                
                # Check if file exists, if not write it
                if not os.path.exists(file_path):
                    # Attempt to fetch as PNG specifically to ensure consistent format in storage.
                    # Prefer fetching as PNG to ensure a standard format across different clipboard contents.
                    try:
                        png_bytes = subprocess.check_output(["wl-paste", "--type", "image/png"], stderr=subprocess.DEVNULL)
                        with open(file_path, "wb") as f:
                            f.write(png_bytes)
                    except subprocess.CalledProcessError:
                         # fallback to whatever we got first
                        with open(file_path, "wb") as f:
                            f.write(content_bytes)

                return file_path, "image", content_hash
            except Exception:
                pass

        return None, None, None

    def set_content(self, content_value: str, content_type: str):
        if content_type == "text":
            subprocess.run(["wl-copy", "--type", "text/plain"], input=content_value.encode('utf-8'), check=True)
        elif content_type == "image":
            # wl-copy < file
            with open(content_value, "rb") as f:
                subprocess.run(["wl-copy", "--type", "image/png"], stdin=f, check=True)

    def get_active_window_class(self) -> Optional[str]:
        # Wayland window detection varies by compositor. Using CLI tools for Sway and Hyprland.
        if shutil.which("swaymsg"):
            try:
                import json
                output = subprocess.check_output(["swaymsg", "-t", "get_tree"], stderr=subprocess.DEVNULL)
                tree = json.loads(output)
                
                def find_focused(node):
                    if node.get("focused"):
                        return node.get("window_properties", {}).get("class") or node.get("app_id")
                    for child in node.get("nodes", []) + node.get("floating_nodes", []):
                        res = find_focused(child)
                        if res: return res
                    return None
                
                return find_focused(tree)
            except Exception:
                pass
        
        if shutil.which("hyprctl"):
            try:
                import json
                output = subprocess.check_output(["hyprctl", "activewindow", "-j"], stderr=subprocess.DEVNULL)
                window = json.loads(output)
                return window.get("class")
            except Exception:
                pass
        
        return None


class X11Backend(ClipboardBackend):
    def start_watcher(self, clipy_executable_cmd: list[str]):
        print("Starting X11 Polling Watcher...", file=sys.stderr)
        last_hash = None
        while True:
            try:
                content_value, content_type, content_hash = self.get_content()
                if content_hash and content_hash != last_hash:
                    last_hash = content_hash
                    # Trigger the 'add' command via CLI.
                    # ASSUMPTION: The 'add' command is the standard entry point for recording changes.
                    subprocess.run(clipy_executable_cmd + ["add"], check=False)
                
                time.sleep(1.0) # Poll every second to balance responsiveness and CPU usage.
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error in X11 watcher: {e}", file=sys.stderr)
                time.sleep(1)

    def get_content(self) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        # Requires xclip
        # Check targets
        try:
            # xclip -selection clipboard -t TARGETS -o
            targets = subprocess.check_output(["xclip", "-selection", "clipboard", "-t", "TARGETS", "-o"], stderr=subprocess.DEVNULL).decode().splitlines()
        except subprocess.CalledProcessError:
            return None, None, None

        # Check for sensitive data hints (KeePassXC and others use these)
        sensitive_targets = {"x-kde-passwordManagerHint", "CLIPBOARD_MANAGER_HINT_SECRET"}
        if sensitive_targets.intersection(targets):
            return None, None, None

        if "UTF8_STRING" in targets or "STRING" in targets:
            try:
                content = subprocess.check_output(["xclip", "-selection", "clipboard", "-o"], stderr=subprocess.DEVNULL).decode('utf-8')
                if not content: return None, None, None
                return content, "text", calculate_hash(content.encode('utf-8'))
            except Exception:
                pass

        if "image/png" in targets or "image/jpeg" in targets: # xclip usually shows image/png
            try:
                content_bytes = subprocess.check_output(["xclip", "-selection", "clipboard", "-t", "image/png", "-o"], stderr=subprocess.DEVNULL)
                content_hash = calculate_hash(content_bytes)
                image_dir = get_image_dir()
                file_path = os.path.join(image_dir, f"{content_hash}.png")
                
                if not os.path.exists(file_path):
                     with open(file_path, "wb") as f:
                            f.write(content_bytes)
                return file_path, "image", content_hash
            except Exception:
                pass
        
        return None, None, None

    def set_content(self, content_value: str, content_type: str):
        if content_type == "text":
            p = subprocess.Popen(["xclip", "-selection", "clipboard", "-i"], stdin=subprocess.PIPE)
            p.communicate(input=content_value.encode('utf-8'))
        elif content_type == "image":
            p = subprocess.Popen(["xclip", "-selection", "clipboard", "-t", "image/png", "-i"], stdin=subprocess.PIPE)
            with open(content_value, "rb") as f:
                p.communicate(input=f.read())
    
    def get_active_window_class(self) -> Optional[str]:
        try:
            # Get active window ID
            out = subprocess.check_output(["xprop", "-root", "_NET_ACTIVE_WINDOW"], stderr=subprocess.DEVNULL).decode()
            if "window id #" not in out:
                return None
            window_id = out.split("#")[-1].strip().split()[0]
            
            # Get window class
            out = subprocess.check_output(["xprop", "-id", window_id, "WM_CLASS"], stderr=subprocess.DEVNULL).decode()
            if "WM_CLASS(STRING) =" in out:
                # Format is usually: WM_CLASS(STRING) = "instance", "class"
                parts = out.split("=")[1].strip().split(",")
                if parts:
                    return parts[-1].strip().strip('"')
        except Exception:
            pass
        return None


def get_backend() -> ClipboardBackend:
    # Detect session
    session_type = os.environ.get("XDG_SESSION_TYPE")
    
    # Priority check: if wl-copy is present, prefer Wayland?
    # Preferred detection method using standard environment variables.
    if session_type == "wayland":
        if shutil.which("wl-copy"):
            return WaylandBackend()
    
    # Fallback or explicit X11
    if shutil.which("xclip"):
        return X11Backend()
    
    raise RuntimeError("No suitable clipboard backend found. Install wl-clipboard (Wayland) or xclip (X11).")
