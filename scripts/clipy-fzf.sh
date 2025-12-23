#!/usr/bin/bash

# fzf integration for Clipy
# Requires: clipy, fzf

# Pipe history to fzf for interactive selection.
# Selection is output to stdout, allowing usage like: restored_text=$(clipy fzf)
clipy list -s | fzf \
    --no-sort \
    --header 'Enter: Select | Ctrl-D: Delete | Esc: Cancel' \
    --bind "ctrl-d:execute(bash -c 'printf \"%s\" \"\$1\" | clipy delete' -- {})+reload(clipy list -s)" \
    --preview "printf '%s' {}" \
    --preview-window 'up:3:wrap'
