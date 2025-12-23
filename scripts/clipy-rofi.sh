#!/usr/bin/bash

# Rofi integration for Clipy
# Requires: clipy, rofi

# Use rofi to select a clip
# -kb-remove-char-forward "Delete" ensures the Delete key works normally while freeing up Ctrl+d
res=$(clipy list -s | rofi -dmenu -i -p "Clipboard:" -kb-remove-char-forward "Delete" -kb-custom-1 "Control+d")
# Rofi exit codes: 0 for selection (Enter), 10 for first custom keybinding (Ctrl+d).
exit_code=$?

if [ $exit_code -eq 0 ]; then
    # Result selected (Enter)
    if [ -n "$res" ]; then
        printf "%s" "$res" | clipy recall
    fi
elif [ $exit_code -eq 10 ]; then
    # Custom 1 (Control+d)
    if [ -n "$res" ]; then
        printf "%s" "$res" | clipy delete
    fi
fi
