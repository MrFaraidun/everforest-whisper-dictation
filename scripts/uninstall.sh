#!/usr/bin/env bash
# ==============================================================================
# 🌲 Everforest Whisper Dictation Pro - Clean Uninstaller
# ==============================================================================
set -e

echo "Stopping and disabling voice-dictation service..."
systemctl --user stop voice-dictation.service 2>/dev/null || true
systemctl --user disable voice-dictation.service 2>/dev/null || true

echo "Removing installed files..."
rm -f "$HOME/.config/systemd/user/voice-dictation.service"
rm -f "$HOME/.local/bin/voice_app_gui.py"
rm -f "$HOME/.local/bin/dictate_toggle.py"
rm -f "$HOME/.local/bin/fix_permissions.sh"
rm -f "$HOME/Desktop/voice-dictation.desktop"
rm -f /tmp/whisper_dictation.sock /tmp/dictate_recording.wav /tmp/dictate_recording.pid

systemctl --user daemon-reload

echo "✅ Uninstallation complete."
