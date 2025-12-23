# Clipy - Python Clipboard Manager

Clipy is a simple clipboard manager written in Python that is designed to be piped into `rofi`, `dmenu`, or `fzf`.

### Dependencies
- Python 3
- **Wayland**: `wl-clipboard`
- **X11**: `xclip`

## Features
- **Wayland Support**: Uses `wl-paste --watch` for efficient monitoring.
- **X11 Support**: Uses polling with `xclip`.
- **Image Support**: Automatically detects and caches images.
- **Database**: Stores history in `~/.local/share/clipy/clipy.db`.

### Installation
```bash
git clone https://github.com/andriy-git/clipy
cd clipy
./setup.sh
```
This will install the `clipy` command to `~/.local/bin`. **Ensure `~/.local/bin` is in your `$PATH`.**

Alternatively, install as a Python package:
```bash
pip install .
```
This will provide the `clipy` command directly.

## Usage

### 1. Start the Daemon
Run the daemon in the background to watch for clipboard changes.
```bash
clipy daemon &
```
Add this to your startup script (e.g., `~/.config/sway/config` or `~/.xinitrc`).

### Systemd Service
You can also run Clipy as a user systemd service. Create `~/.config/systemd/user/clipy-daemon.service`:

```ini
[Unit]
Description=Clipboard history daemon

[Service]
ExecStart=%h/.local/bin/clipy daemon
Restart=on-failure

[Install]
WantedBy=default.target
```

Then enable and start it:
```bash
systemctl --user daemon-reload
systemctl --user enable --now clipy-daemon.service
```

### 2. Status & Management
```bash
clipy status
clipy clear
```

### 3. Integrated Pickers
Clipy comes with built-in support for popular search tools. You can run them directly:

- **fzf**: `clipy fzf` (Supports live search, delete with `Ctrl-D`, and outputs selection to stdout)
- **Rofi**: `clipy rofi` (Supports select and delete with `Ctrl+d`, restores to clipboard)
- **dmenu**: `clipy dmenu` (Restores to clipboard)

> [!TIP]
> You can use `clipy fzf` in command substitutions, e.g., `$(clipy fzf)` to execute or capture the selection.

### 4. Neovim Integration (Telescope)
The Telescope integration is available as a Lua script in the `scripts/` directory.

To use it, run `clipy telescope` for setup instructions or add this to your Neovim config:
```lua
local clipy = require('clipy-telescope') -- Or path in subfolder
clipy.setup({ clipy_path = "clipy" }) -- Path to the clipy command
vim.keymap.set('n', '<leader>c', clipy.clipboard_history, { desc = "Clipy Clipboard History" })
```
> [!NOTE]
> You must add the `scripts/` directory to your Neovim `runtimepath` or copy clipy-telescope.lua to your lua folder.
