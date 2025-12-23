#!/usr/bin/bash

# Clipy Setup & Installation Script

REPO_DIR="$(dirname "$(readlink -f "$0")")"
BIN_DIR="$HOME/.local/bin"
CONFIG_DIR="$HOME/.config/clipy"

echo "--- Clipy Setup ---"

# 1. Initialize local directory structures for binaries and configuration.
echo "[1/3] Creating directories..."
mkdir -p "$BIN_DIR"
mkdir -p "$CONFIG_DIR"

# 2. Install the 'clipy' wrapper to handle routing between the core CLI and various integrations.
echo "[2/3] Installing 'clipy' command to $BIN_DIR..."
cat > "$BIN_DIR/clipy" <<EOF
#!/usr/bin/bash
REPO_DIR="$REPO_DIR"

case "\$1" in
    rofi|fzf|dmenu)
        cmd="\$1"
        shift
        # Execute the corresponding script from the scripts directory
        "\$REPO_DIR/scripts/clipy-\$cmd.sh" "\$@"
        ;;
    telescope)
        echo "Telescope integration is a Lua script."
        echo "To use it, add the following to your Neovim config:"
        echo ""
        echo "  local clipy = require('clipy-telescope')"
        echo "  clipy.setup({ clipy_path = \"\$BIN_DIR/clipy\" })"
        echo "  vim.keymap.set('n', '<leader>c', clipy.clipboard_history, { desc = 'Clipy Clipboard History' })"
        echo ""
        echo "Lua file path: \$REPO_DIR/scripts/clipy-telescope.lua"
        ;;
    *)
        export PYTHONPATH="\$REPO_DIR:\$PYTHONPATH"
        python3 -m clipy.cli "\$@"
        ;;
esac
EOF
chmod +x "$BIN_DIR/clipy"

# 3. Initialize default settings if no user configuration is found.
if [ ! -f "$CONFIG_DIR/config.json" ]; then
    echo "[3/3] Creating default configuration..."
    cat > "$CONFIG_DIR/config.json" <<EOF
{
    "max_entries": 100,
    "blacklist": ["KeePassXC"]
}
EOF
else
    echo "[3/3] Configuration already exists."
fi

echo "-------------------"
echo "Installation complete!"
echo ""
echo "Please ensure $BIN_DIR is in your PATH."
echo "Alternatively, you can install as a python package:"
echo "  pip install ."
echo ""
echo "You can now run Clipy integrations directly:"
echo "  clipy rofi"
echo "  clipy fzf"
echo "  clipy status"
