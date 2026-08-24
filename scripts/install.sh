#!/usr/bin/env bash
# ==============================================================================
# 🌲 Everforest Whisper Dictation Pro - Automated Installer
# ==============================================================================
set -e

# Color definitions
GREEN='\033[0;32m'
AQUA='\033[0;36m'
YELLOW='\033[1;33m'
CORAL='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}======================================================${NC}"
echo -e "${AQUA}  🌲 Installing Everforest Whisper Dictation Pro...    ${NC}"
echo -e "${GREEN}======================================================${NC}"

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALL_BIN="$HOME/.local/bin"
SYSTEMD_DIR="$HOME/.config/systemd/user"
DESKTOP_DIR="$HOME/Desktop"
VENV_DIR="$HOME/.local/share/whisper-env"

mkdir -p "$INSTALL_BIN" "$SYSTEMD_DIR" "$DESKTOP_DIR"

echo -e "\n${AQUA}[1/6] Checking system packages (ydotool, wl-clipboard, ffmpeg, alsa-utils)...${NC}"
MISSING_PKGS=()
for pkg in ydotool wl-clipboard ffmpeg alsa-utils python3-pip python3-venv xclip; do
    if ! dpkg -s "$pkg" >/dev/null 2>&1; then
        MISSING_PKGS+=("$pkg")
    fi
done

if [ ${#MISSING_PKGS[@]} -ne 0 ]; then
    echo -e "${YELLOW}Installing missing dependencies: ${MISSING_PKGS[*]}${NC}"
    sudo apt update && sudo apt install -y "${MISSING_PKGS[@]}"
else
    echo -e "${GREEN}✓ All system packages are installed.${NC}"
fi

echo -e "\n${AQUA}[2/6] Configuring uinput virtual keyboard permissions...${NC}"
sudo usermod -aG input "$USER"
echo 'KERNEL=="uinput", MODE="0666"' | sudo tee /etc/udev/rules.d/80-uinput.rules >/dev/null
sudo chmod 0666 /dev/uinput 2>/dev/null || true
sudo udevadm control --reload-rules 2>/dev/null || true
sudo udevadm trigger 2>/dev/null || true
echo -e "${GREEN}✓ Kernel virtual keyboard permissions active.${NC}"

echo -e "\n${AQUA}[3/6] Setting up Python virtual environment at $VENV_DIR...${NC}"
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
fi
"$VENV_DIR/bin/pip" install --upgrade pip >/dev/null 2>&1
"$VENV_DIR/bin/pip" install -r "$PROJECT_DIR/requirements.txt" >/dev/null 2>&1

# Link PyGObject if system-wide
if [ -d "/usr/lib/python3/dist-packages/gi" ] && [ ! -d "$VENV_DIR/lib/python3.12/site-packages/gi" ]; then
    ln -sf /usr/lib/python3/dist-packages/gi* "$VENV_DIR/lib/python3.12/site-packages/" 2>/dev/null || true
fi
echo -e "${GREEN}✓ Python environment configured with faster-whisper and PyQt5.${NC}"

echo -e "\n${AQUA}[4/6] Copying executable scripts to $INSTALL_BIN...${NC}"
cp "$PROJECT_DIR/bin/voice_app_gui.py" "$INSTALL_BIN/voice_app_gui.py"
cp "$PROJECT_DIR/bin/dictate_toggle.py" "$INSTALL_BIN/dictate_toggle.py"
cp "$PROJECT_DIR/bin/fix_permissions.sh" "$INSTALL_BIN/fix_permissions.sh"
chmod +x "$INSTALL_BIN/voice_app_gui.py" "$INSTALL_BIN/dictate_toggle.py" "$INSTALL_BIN/fix_permissions.sh"

echo -e "\n${AQUA}[5/6] Registering and starting background systemd daemon...${NC}"
cp "$PROJECT_DIR/systemd/voice-dictation.service" "$SYSTEMD_DIR/voice-dictation.service"
systemctl --user daemon-reload
systemctl --user enable --now voice-dictation.service
systemctl --user restart voice-dictation.service

echo -e "\n${AQUA}[6/6] Setting up Desktop launcher and GNOME hotkey...${NC}"
cp "$PROJECT_DIR/desktop/voice-dictation.desktop" "$DESKTOP_DIR/voice-dictation.desktop"
chmod +x "$DESKTOP_DIR/voice-dictation.desktop"

# Register GNOME custom keybinding if GNOME is running
if command -v gsettings >/dev/null 2>&1; then
    KEY_PATH="/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom1/"
    gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:$KEY_PATH name "Whisper Dictation" 2>/dev/null || true
    gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:$KEY_PATH command "$INSTALL_BIN/dictate_toggle.py" 2>/dev/null || true
    gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:$KEY_PATH binding "Caps_Lock" 2>/dev/null || true
    echo -e "${GREEN}✓ GNOME shortcut assigned to CapsLock.${NC}"
fi

echo -e "\n${GREEN}======================================================${NC}"
echo -e "${GREEN}  ✨ Installation Complete! Dictation is active!      ${NC}"
echo -e "${GREEN}  • Tap CapsLock to speak, tap again to type anywhere.${NC}"
echo -e "${GREEN}======================================================${NC}"
