#!/usr/bin/env /home/faraidun/.local/share/whisper-env/bin/python
"""
Instant Client Trigger for Whisper Dictation Daemon (<2ms execution)
"""
import socket
import sys
import os
import subprocess

SOCKET_PATH = "/tmp/whisper_dictation.sock"

def main():
    cmd = sys.argv[1].upper() if len(sys.argv) > 1 else "TOGGLE"
    
    if not os.path.exists(SOCKET_PATH):
        # Auto-restart service if down
        subprocess.run(["systemctl", "--user", "start", "voice-dictation.service"], check=False)
        # Give it a moment to bind socket
        import time
        for _ in range(10):
            if os.path.exists(SOCKET_PATH):
                break
            time.sleep(0.1)

    try:
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.connect(SOCKET_PATH)
        client.sendall(f"{cmd}\n".encode('utf-8'))
        response = client.recv(1024).decode('utf-8').strip()
        client.close()
        print(f"Daemon response: {response}")
    except Exception as e:
        print("Could not connect to whisper daemon:", e)

if __name__ == "__main__":
    main()
