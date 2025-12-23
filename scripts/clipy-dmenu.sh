#!/usr/bin/bash

# dmenu integration for Clipy
# Requires: clipy, dmenu

# Use dmenu to select a clip
res=$(clipy list -s | dmenu -i -p "Clipboard:" -l 15)

# If something was selected, recall it to clipboard
if [ -n "$res" ]; then
    echo "$res" | clipy recall
fi
