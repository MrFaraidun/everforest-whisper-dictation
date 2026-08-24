#!/usr/bin/env bash
set -e

echo "1. Adding user $SUDO_USER to input group..."
usermod -aG input "${SUDO_USER:-$USER}"

echo "2. Setting uinput udev rules..."
echo 'KERNEL=="uinput", MODE="0666"' > /etc/udev/rules.d/80-uinput.rules

echo "3. Granting immediate write permissions to /dev/uinput..."
chmod 0666 /dev/uinput

udevadm control --reload-rules && udevadm trigger

echo "✅ Success! Virtual hardware keyboard is now 100% active and enabled."
