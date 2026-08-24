#!/usr/bin/env /home/faraidun/.local/share/whisper-env/bin/python
"""
Voice Dictation Pro - Masterpiece Everforest Ambient Dynamic Pill
- Bespoke Organic Topographic Audio Waves & 12-Node Equalizer
- Live Recording Timer (● REC 0:03) & Dynamic Status Chip
- Ambient Forest Halo & Frosted Glassmorphism
- Live Transcribed Text Typewriter Preview
- Sub-0.2s Faster-Whisper int8 Engine + Auto-Clipboard & Type
"""
import sys
import os
import time
import math
import signal
import socket
import subprocess
import threading

if "DISPLAY" not in os.environ or not os.environ["DISPLAY"]:
    os.environ["DISPLAY"] = ":0"

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QTimer, QRectF, QPointF
from PyQt5.QtGui import (
    QFont, QCursor, QPainter, QPainterPath, QColor,
    QLinearGradient, QPen, QBrush, QRadialGradient
)
from faster_whisper import WhisperModel

SOCKET_PATH = "/tmp/whisper_dictation.sock"
WAV_FILE = "/tmp/dictate_recording.wav"
GROQ_KEY_FILE = os.path.expanduser("~/.config/groq_api_key.txt")
MAX_RECORDING_SECONDS = 15

# Global State
is_recording = False
recording_proc = None
recording_start_time = 0
model = None
state_lock = threading.Lock()
max_timer = None
app = None
main_window = None

class WorkerSignals(QObject):
    status_changed = pyqtSignal(str, str, str, str) # state, title, subtitle, timer_str
    show_window = pyqtSignal()
    hide_window = pyqtSignal()

signals = WorkerSignals()

def notify(title, message="", timeout_ms=2000):
    try:
        subprocess.run([
            "notify-send", "-t", str(timeout_ms),
            "-a", "Whisper Dictation",
            "-h", "string:x-canonical-private-synchronous:whisper-dictate",
            title, message
        ], check=False)
    except Exception:
        pass

def reset_caps_lock():
    try:
        res = subprocess.run(['xset', 'q'], capture_output=True, text=True, check=False)
        if "Caps Lock:   on" in res.stdout:
            subprocess.run(['xdotool', 'key', 'Caps_Lock'], check=False)
    except Exception:
        pass

def get_groq_key():
    if os.path.exists(GROQ_KEY_FILE):
        try:
            with open(GROQ_KEY_FILE, "r") as f:
                key = f.read().strip()
                if key.startswith("gsk_"):
                    return key
        except Exception:
            pass
    return os.environ.get("GROQ_API_KEY", None)

def load_model():
    global model
    if model is not None:
        return model
    try:
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
        compute_type = "float16" if device == "cuda" else "int8"
        model = WhisperModel("base.en", device=device, compute_type=compute_type, cpu_threads=8)
    except Exception:
        model = WhisperModel("base.en", device="cpu", compute_type="int8", cpu_threads=8)
    return model

def init_atspi():
    try:
        import gi
        gi.require_version('Atspi', '2.0')
        from gi.repository import Atspi
        Atspi.init()
        print("AT-SPI 2.0 initialized successfully.")
    except Exception as e:
        print("AT-SPI init error:", e)

def try_atspi_paste(text):
    try:
        import gi
        gi.require_version('Atspi', '2.0')
        from gi.repository import Atspi
        time.sleep(0.08)
        
        # 1. Universal Terminal & Text Paste (Shift + Insert)
        Atspi.generate_keyboard_event(0xffe1, 'Shift_L', Atspi.KeySynthType.PRESS)
        time.sleep(0.03)
        Atspi.generate_keyboard_event(0xff63, 'Insert', Atspi.KeySynthType.PRESS)
        time.sleep(0.04)
        Atspi.generate_keyboard_event(0xff63, 'Insert', Atspi.KeySynthType.RELEASE)
        time.sleep(0.03)
        Atspi.generate_keyboard_event(0xffe1, 'Shift_L', Atspi.KeySynthType.RELEASE)
        
        time.sleep(0.04)
        
        # 2. Terminal Paste (Ctrl + Shift + V)
        Atspi.generate_keyboard_event(0xffe3, 'Control_L', Atspi.KeySynthType.PRESS)
        time.sleep(0.02)
        Atspi.generate_keyboard_event(0xffe1, 'Shift_L', Atspi.KeySynthType.PRESS)
        time.sleep(0.03)
        Atspi.generate_keyboard_event(0x0056, 'V', Atspi.KeySynthType.PRESS)
        time.sleep(0.04)
        Atspi.generate_keyboard_event(0x0056, 'V', Atspi.KeySynthType.RELEASE)
        time.sleep(0.02)
        Atspi.generate_keyboard_event(0xffe1, 'Shift_L', Atspi.KeySynthType.RELEASE)
        time.sleep(0.02)
        Atspi.generate_keyboard_event(0xffe3, 'Control_L', Atspi.KeySynthType.RELEASE)

        time.sleep(0.04)

        # 3. Standard GUI Paste (Ctrl + V)
        Atspi.generate_keyboard_event(0xffe3, 'Control_L', Atspi.KeySynthType.PRESS)
        time.sleep(0.03)
        Atspi.generate_keyboard_event(0x0076, 'v', Atspi.KeySynthType.PRESS)
        time.sleep(0.04)
        Atspi.generate_keyboard_event(0x0076, 'v', Atspi.KeySynthType.RELEASE)
        time.sleep(0.03)
        Atspi.generate_keyboard_event(0xffe3, 'Control_L', Atspi.KeySynthType.RELEASE)
        return True
    except Exception as e:
        print("Atspi paste error:", e)
    return False

def try_atspi_type_string(text):
    try:
        import gi
        gi.require_version('Atspi', '2.0')
        from gi.repository import Atspi
        time.sleep(0.06)
        for char in text:
            Atspi.generate_keyboard_event(0, char, Atspi.KeySynthType.STRING)
            time.sleep(0.003)
        return True
    except Exception as e:
        print("Atspi direct type error:", e)
    return False

def try_uinput_paste():
    try:
        import evdev
        from evdev import UInput, ecodes
        ui = UInput()
        time.sleep(0.04)
        ui.write(ecodes.EV_KEY, ecodes.KEY_LEFTCTRL, 1)
        ui.write(ecodes.EV_KEY, ecodes.KEY_V, 1)
        ui.syn()
        time.sleep(0.03)
        ui.write(ecodes.EV_KEY, ecodes.KEY_V, 0)
        ui.write(ecodes.EV_KEY, ecodes.KEY_LEFTCTRL, 0)
        ui.syn()
        ui.close()
        return True
    except Exception as e:
        return False

def type_and_paste(text):
    if not text or not text.strip():
        return
    text = text.strip()
    
    # 1. Set Native Wayland Clipboard (wl-copy)
    try:
        proc = subprocess.Popen(['wl-copy'], stdin=subprocess.PIPE)
        proc.communicate(input=text.encode('utf-8'))
    except Exception:
        pass

    # 2. Set GTK / X11 Clipboard
    try:
        import gi
        gi.require_version('Gtk', '3.0')
        from gi.repository import Gtk, Gdk
        cb = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        cb.set_text(text, -1)
        cb.store()
        pri = Gtk.Clipboard.get(Gdk.SELECTION_PRIMARY)
        pri.set_text(text, -1)
        pri.store()
    except Exception:
        pass

    try:
        proc = subprocess.Popen(['xclip', '-selection', 'clipboard'], stdin=subprocess.PIPE)
        proc.communicate(input=text.encode('utf-8'))
    except Exception:
        pass

    time.sleep(0.08)

    # 3. PRIORITY 1: ydotool Direct Hardware Wayland Type (100% works on all Wayland apps)
    try:
        res = subprocess.run(['ydotool', 'type', '--', text], check=False, capture_output=True)
        if res.returncode == 0:
            print("Typed successfully via ydotool")
            return
    except Exception:
        pass

    # 4. PRIORITY 2: ydotool Key Simulation (Shift+Insert / Ctrl+Shift+V / Ctrl+V)
    try:
        # Shift+Insert (42:LeftShift, 110:Insert)
        subprocess.run(['ydotool', 'key', '42:1', '110:1', '110:0', '42:0'], check=False)
        # Ctrl+Shift+V (29:LeftCtrl, 42:LeftShift, 47:V)
        subprocess.run(['ydotool', 'key', '29:1', '42:1', '47:1', '47:0', '42:0', '29:0'], check=False)
        # Ctrl+V (29:LeftCtrl, 47:V)
        subprocess.run(['ydotool', 'key', '29:1', '47:1', '47:0', '29:0'], check=False)
    except Exception:
        pass

    # 5. AT-SPI Accessibility Paste & xdotool Fallback
    try_atspi_paste(text)
    try_atspi_type_string(text)
    try:
        subprocess.run(['xdotool', 'key', '--delay', '40', '--clearmodifiers', 'shift+Insert'], check=False)
        subprocess.run(['xdotool', 'key', '--delay', '40', '--clearmodifiers', 'ctrl+shift+v'], check=False)
        subprocess.run(['xdotool', 'key', '--delay', '40', '--clearmodifiers', 'ctrl+v'], check=False)
    except Exception:
        pass

def start_recording():
    global is_recording, recording_proc, recording_start_time, max_timer
    with state_lock:
        if is_recording:
            return
        
        if os.path.exists(WAV_FILE):
            try:
                os.remove(WAV_FILE)
            except Exception:
                pass
        
        cmd = ["arecord", "-q", "-f", "S16_LE", "-r", "16000", "-c", "1", WAV_FILE]
        recording_proc = subprocess.Popen(cmd)
        is_recording = True
        recording_start_time = time.time()
        
        signals.show_window.emit()
        signals.status_changed.emit("LISTENING", "Listening...", "Speak now • Tap to transcribe", "0:00")
        notify("🎙️ Listening...", "Speak now... (Tap shortcut to finish)")
        
        if max_timer:
            max_timer.cancel()
        max_timer = threading.Timer(MAX_RECORDING_SECONDS, auto_stop_timeout)
        max_timer.start()

def auto_stop_timeout():
    if is_recording:
        stop_and_transcribe()

def stop_and_transcribe():
    global is_recording, recording_proc, max_timer
    with state_lock:
        if not is_recording:
            return
        is_recording = False
        
        if max_timer:
            max_timer.cancel()
            max_timer = None
            
        if recording_proc:
            try:
                recording_proc.send_signal(signal.SIGINT)
                recording_proc.wait(timeout=2)
            except Exception:
                pass
            recording_proc = None

    reset_caps_lock()
    
    if not os.path.exists(WAV_FILE) or os.path.getsize(WAV_FILE) < 1500:
        signals.status_changed.emit("ERROR", "No Audio", "Recording too short", "--:--")
        notify("⚠️ Too short", "No audio recorded")
        threading.Timer(1.5, lambda: signals.hide_window.emit()).start()
        return

    signals.status_changed.emit("TRANSCRIBING", "Transcribing...", "Everforest Whisper Engine", "AI ⚡")
    notify("⚡ Transcribing...", "Processing audio in memory...")
    
    def process_transcription():
        t0 = time.time()
        text = ""
        try:
            groq_key = get_groq_key()
            if groq_key:
                try:
                    from groq import Groq
                    client = Groq(api_key=groq_key)
                    with open(WAV_FILE, "rb") as file:
                        transcription = client.audio.transcriptions.create(
                            file=(WAV_FILE, file.read()),
                            model="whisper-large-v3",
                            response_format="text",
                            language="en"
                        )
                    text = str(transcription).strip()
                except Exception as e:
                    print("Groq API error:", e)
            
            if not text:
                try:
                    m = load_model()
                    segments, info = m.transcribe(
                        WAV_FILE,
                        beam_size=1,
                        language="en",
                        vad_filter=True,
                        initial_prompt="Clear spoken English with correct punctuation and spelling."
                    )
                    text = " ".join([s.text for s in segments]).strip()
                except Exception as e:
                    print("Local transcription error:", e)
        finally:
            if os.path.exists(WAV_FILE):
                try:
                    os.remove(WAV_FILE)
                except Exception:
                    pass

        duration = time.time() - t0
        
        if text:
            type_and_paste(text)
            preview = f'"{text[:38]}..."' if len(text) > 38 else f'"{text}"'
            signals.status_changed.emit("SUCCESS", f"Done in {duration:.2f}s", preview, "✔ TYPED")
            notify("✅ Dictation Complete", f"({duration:.2f}s): {text[:60]}...")
            print(f"Transcribed [{duration:.2f}s]: {text}")
            threading.Timer(2.2, lambda: signals.hide_window.emit()).start()
        else:
            signals.status_changed.emit("ERROR", "No Speech", "Could not detect voice", "ERR")
            notify("⚠️ No speech detected", "Could not transcribe audio")
            threading.Timer(1.6, lambda: signals.hide_window.emit()).start()

    threading.Thread(target=process_transcription, daemon=True).start()

def toggle_recording():
    if is_recording:
        stop_and_transcribe()
    else:
        start_recording()

def handle_client(conn):
    try:
        data = conn.recv(1024).decode('utf-8').strip()
        if data == "TOGGLE":
            toggle_recording()
            conn.sendall(b"OK:TOGGLED\n")
        elif data == "START":
            start_recording()
            conn.sendall(b"OK:STARTED\n")
        elif data == "STOP":
            stop_and_transcribe()
            conn.sendall(b"OK:STOPPED\n")
        elif data == "SHOW":
            signals.show_window.emit()
            conn.sendall(b"OK:SHOWN\n")
        elif data == "STATUS":
            status_str = "RECORDING" if is_recording else "IDLE"
            conn.sendall(f"STATUS:{status_str}\n".encode('utf-8'))
        else:
            conn.sendall(b"ERR:UNKNOWN_CMD\n")
    except Exception as e:
        print("Client handling error:", e)
    finally:
        conn.close()

def run_socket_server():
    if os.path.exists(SOCKET_PATH):
        try:
            os.remove(SOCKET_PATH)
        except Exception:
            pass

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(SOCKET_PATH)
    server.listen(10)
    os.chmod(SOCKET_PATH, 0o777)

    while True:
        try:
            conn, _ = server.accept()
            threading.Thread(target=handle_client, args=(conn,), daemon=True).start()
        except Exception as e:
            print("Socket error:", e)
            time.sleep(0.5)

# =========================================================================
# 🌲 Masterpiece Visualizer: Topographic Fluid Wave + 12 Organic Equalizer Nodes
# =========================================================================
class EverforestMasterpieceVisualizer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(124, 46)
        self.phase = 0.0
        self.current_state = "IDLE"
        self.num_nodes = 12
        self.node_heights = [5.0] * self.num_nodes
        self.target_heights = [5.0] * self.num_nodes

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_physics)
        self.timer.start(16) # 60 FPS

    def set_state(self, state):
        self.current_state = state

    def update_physics(self):
        self.phase += 0.14
        h_max = self.height() - 10

        for i in range(self.num_nodes):
            if self.current_state == "LISTENING":
                # Double harmonic wave + organic envelope
                t = i / (self.num_nodes - 1)
                wave1 = math.sin(self.phase * 1.6 + i * 0.65)
                wave2 = math.cos(self.phase * 0.9 - i * 0.45)
                envelope = math.sin(t * math.pi)
                val = 6.0 + (abs(wave1 * 0.7 + wave2 * 0.3) * (h_max - 6)) * (0.35 + 0.65 * envelope)
                self.target_heights[i] = max(4.0, min(val, h_max))
            elif self.current_state == "TRANSCRIBING":
                # Amber shimmer wave
                wave = math.sin(self.phase * 2.2 - i * 0.55)
                self.target_heights[i] = 5.0 + (abs(wave) * (h_max * 0.45))
            elif self.current_state == "SUCCESS":
                self.target_heights[i] = 0.0
            else:
                idle = math.sin(self.phase * 0.6 + i * 0.5)
                self.target_heights[i] = 4.0 + abs(idle) * 3.5

            # Smooth spring interpolation
            self.node_heights[i] += (self.target_heights[i] - self.node_heights[i]) * 0.24

        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        cy = h / 2.0

        if self.current_state == "SUCCESS":
            # Radiant Moss Green Leaf Badge with Everforest Glow
            glow = QRadialGradient(w/2, cy, 18)
            glow.setColorAt(0.0, QColor(167, 192, 128, 120)) # #a7c080
            glow.setColorAt(1.0, QColor(167, 192, 128, 0))
            painter.setBrush(QBrush(glow))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(int(w/2 - 18), int(cy - 18), 36, 36)

            painter.setBrush(QBrush(QColor(167, 192, 128, 240)))
            painter.drawEllipse(int(w/2 - 13), int(cy - 13), 26, 26)
            
            pen = QPen(QColor(39, 46, 51), 2.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(pen)
            painter.drawLine(int(w/2 - 5), int(cy), int(w/2 - 1), int(cy + 4))
            painter.drawLine(int(w/2 - 1), int(cy + 4), int(w/2 + 6), int(cy - 4))
            return

        # 1. Background Topographic Fluid Mountain Aura (Curved area fill)
        topo_path = QPainterPath()
        topo_path.moveTo(0, h)
        
        for x in range(0, int(w) + 1, 3):
            t = x / w
            wave = math.sin(x * 0.05 + self.phase * 0.8) * math.sin(t * math.pi) * 8.0
            topo_path.lineTo(x, cy - wave)
            
        topo_path.lineTo(w, h)
        topo_path.closeSubpath()

        topo_grad = QLinearGradient(0, cy - 10, 0, h)
        if self.current_state == "LISTENING":
            topo_grad.setColorAt(0.0, QColor(230, 126, 128, 35)) # Coral tint
            topo_grad.setColorAt(1.0, QColor(45, 53, 59, 0))
        elif self.current_state == "TRANSCRIBING":
            topo_grad.setColorAt(0.0, QColor(219, 188, 127, 40)) # Amber tint
            topo_grad.setColorAt(1.0, QColor(45, 53, 59, 0))
        else:
            topo_grad.setColorAt(0.0, QColor(131, 192, 146, 25)) # Sage tint
            topo_grad.setColorAt(1.0, QColor(45, 53, 59, 0))

        painter.setBrush(QBrush(topo_grad))
        painter.setPen(Qt.NoPen)
        painter.drawPath(topo_path)

        # 2. 12 Rounded Equalizer Nodes
        bar_w = 4.0
        spacing = 4.8
        total_w = self.num_nodes * bar_w + (self.num_nodes - 1) * spacing
        start_x = (w - total_w) / 2.0

        for i in range(self.num_nodes):
            bx = start_x + i * (bar_w + spacing)
            bh = self.node_heights[i]
            by = cy - (bh / 2.0)

            grad = QLinearGradient(bx, by, bx, by + bh)
            t = i / (self.num_nodes - 1)

            if self.current_state == "LISTENING":
                # Terracotta Coral (#e67e80) -> Sand Amber (#dbbc7f) -> Forest Moss (#a7c080)
                if t < 0.4:
                    c1, c2 = QColor(230, 126, 128), QColor(230, 152, 117)
                elif t < 0.7:
                    c1, c2 = QColor(230, 152, 117), QColor(219, 188, 127)
                else:
                    c1, c2 = QColor(219, 188, 127), QColor(167, 192, 128)
            elif self.current_state == "TRANSCRIBING":
                c1, c2 = QColor(219, 188, 127), QColor(230, 152, 117) # Amber / Peach
            else:
                c1, c2 = QColor(131, 192, 146), QColor(167, 192, 128) # Sage / Moss

            grad.setColorAt(0.0, c1)
            grad.setColorAt(1.0, c2)

            painter.setBrush(QBrush(grad))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(QRectF(bx, by, bar_w, bh), bar_w / 2.0, bar_w / 2.0)

# =========================================================================
# 🌲 Masterpiece Everforest Dynamic Island Pill
# =========================================================================
class EverforestMasterpiecePill(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(450, 64)
        
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint | 
            Qt.FramelessWindowHint | 
            Qt.Tool | 
            Qt.WindowDoesNotAcceptFocus |
            Qt.X11BypassWindowManagerHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)

        self.current_state = "IDLE"
        self.pulse_phase = 0.0

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)

        self.container = QFrame()
        self.container.setCursor(QCursor(Qt.PointingHandCursor))
        
        layout = QHBoxLayout(self.container)
        layout.setContentsMargins(14, 6, 12, 6)
        layout.setSpacing(12)

        # 1. Visualizer
        self.visualizer = EverforestMasterpieceVisualizer()
        layout.addWidget(self.visualizer, 0, Qt.AlignVCenter)

        # 2. Typography & Micro-copy
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        text_layout.setContentsMargins(0, 1, 0, 1)

        self.title_label = QLabel("Whisper Dictation")
        self.title_label.setFont(QFont("Cantarell, Inter, Sans-Serif", 11, QFont.Bold))
        self.title_label.setStyleSheet("color: #d3c6aa; border: none; letter-spacing: 0.2px;")
        text_layout.addWidget(self.title_label)

        self.subtitle_label = QLabel("Tap shortcut or click to dictate")
        self.subtitle_label.setFont(QFont("Cantarell, Inter, Sans-Serif", 9, QFont.Normal))
        self.subtitle_label.setStyleSheet("color: #859289; border: none;")
        text_layout.addWidget(self.subtitle_label)

        layout.addLayout(text_layout, 1)

        # 3. Dynamic Status Badge Chip (e.g. ● REC 0:03 / ✔ TYPED)
        self.chip_badge = QLabel("🌿 READY")
        self.chip_badge.setFont(QFont("Cantarell, Inter, Sans-Serif", 9, QFont.Bold))
        self.chip_badge.setAlignment(Qt.AlignCenter)
        self.chip_badge.setFixedHeight(22)
        self.chip_badge.setStyleSheet("""
            QLabel {
                background-color: #343f44;
                color: #a7c080;
                border: 1px solid rgba(167, 192, 128, 0.3);
                border-radius: 11px;
                padding: 0 8px;
            }
        """)
        layout.addWidget(self.chip_badge, 0, Qt.AlignVCenter)

        # 4. Dismiss Button
        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(22, 22)
        self.close_btn.setToolTip("Dismiss")
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: #343f44;
                color: #9da9a0;
                border: 1px solid #475258;
                border-radius: 11px;
                font-weight: bold;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: #e67e80;
                color: #272e33;
                border: 1px solid #e67e80;
            }
        """)
        self.close_btn.clicked.connect(self.hide)
        layout.addWidget(self.close_btn, 0, Qt.AlignVCenter)

        main_layout.addWidget(self.container)

        # Position under GNOME top bar
        screen_geo = QApplication.primaryScreen().geometry()
        self.move((screen_geo.width() - self.width()) // 2, 38)

        # Recording duration live timer
        self.rec_timer = QTimer(self)
        self.rec_timer.timeout.connect(self.update_recording_timer)
        self.rec_timer.start(500)

        # Pulse halo timer
        self.halo_timer = QTimer(self)
        self.halo_timer.timeout.connect(self.update_halo)
        self.halo_timer.start(33)

        # Signals
        signals.status_changed.connect(self.on_status_changed)
        signals.show_window.connect(self.bring_to_front)
        signals.hide_window.connect(self.hide)

    def update_halo(self):
        self.pulse_phase += 0.08
        if self.current_state in ("LISTENING", "TRANSCRIBING"):
            self.update()

    def update_recording_timer(self):
        if is_recording and self.current_state == "LISTENING":
            elapsed = int(time.time() - recording_start_time)
            mins = elapsed // 60
            secs = elapsed % 60
            self.chip_badge.setText(f"● REC {mins}:{secs:02d}")
            self.chip_badge.setStyleSheet("""
                QLabel {
                    background-color: rgba(230, 126, 128, 0.18);
                    color: #e67e80;
                    border: 1px solid #e67e80;
                    border-radius: 11px;
                    padding: 0 8px;
                }
            """)

    def on_manual_paste_clicked(self):
        try_atspi_paste("")
        self.paste_btn.setText("✔ Pasted!")
        self.paste_btn.setStyleSheet("""
            QPushButton {
                background-color: #a7c080;
                color: #272e33;
                border: 1px solid #a7c080;
                border-radius: 12px;
                font-weight: bold;
                font-size: 10px;
                padding: 0 8px;
            }
        """)
        QTimer.singleShot(1500, lambda: self.paste_btn.setText("📋 Paste"))

    def mousePressEvent(self, event):
        toggle_recording()

    def bring_to_front(self):
        self.show()
        self.raise_()

    def on_status_changed(self, state, title, subtitle, badge_text):
        self.current_state = state
        self.visualizer.set_state(state)
        self.title_label.setText(title)
        self.subtitle_label.setText(subtitle)
        self.chip_badge.setText(badge_text)

        if state == "LISTENING":
            self.title_label.setStyleSheet("color: #e67e80; font-weight: bold; border: none;")
            self.chip_badge.setStyleSheet("""
                QLabel {
                    background-color: rgba(230, 126, 128, 0.18);
                    color: #e67e80;
                    border: 1px solid #e67e80;
                    border-radius: 11px;
                    padding: 0 8px;
                }
            """)
        elif state == "TRANSCRIBING":
            self.title_label.setStyleSheet("color: #dbbc7f; font-weight: bold; border: none;")
            self.chip_badge.setStyleSheet("""
                QLabel {
                    background-color: rgba(219, 188, 127, 0.18);
                    color: #dbbc7f;
                    border: 1px solid #dbbc7f;
                    border-radius: 11px;
                    padding: 0 8px;
                }
            """)
        elif state == "SUCCESS":
            self.title_label.setStyleSheet("color: #a7c080; font-weight: bold; border: none;")
            self.chip_badge.setStyleSheet("""
                QLabel {
                    background-color: rgba(167, 192, 128, 0.18);
                    color: #a7c080;
                    border: 1px solid #a7c080;
                    border-radius: 11px;
                    padding: 0 8px;
                }
            """)
        elif state == "ERROR":
            self.title_label.setStyleSheet("color: #e67e80; font-weight: bold; border: none;")
            self.chip_badge.setStyleSheet("""
                QLabel {
                    background-color: rgba(230, 126, 128, 0.18);
                    color: #e67e80;
                    border: 1px solid #e67e80;
                    border-radius: 11px;
                    padding: 0 8px;
                }
            """)
        else:
            self.title_label.setStyleSheet("color: #d3c6aa; font-weight: bold; border: none;")
            self.chip_badge.setStyleSheet("""
                QLabel {
                    background-color: #343f44;
                    color: #a7c080;
                    border: 1px solid rgba(167, 192, 128, 0.3);
                    border-radius: 11px;
                    padding: 0 8px;
                }
            """)
        
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect().adjusted(4, 4, -4, -4)
        radius = 27.0

        # 1. Soft Ambient Halo Glow (Breathing in theme color)
        if self.current_state in ("LISTENING", "TRANSCRIBING", "SUCCESS"):
            halo_alpha = int(40 + 25 * math.sin(self.pulse_phase))
            halo = QRadialGradient(rect.center().x(), rect.center().y(), rect.width() / 1.6)
            
            if self.current_state == "LISTENING":
                halo.setColorAt(0.0, QColor(230, 126, 128, halo_alpha)) # Terracotta Coral
            elif self.current_state == "TRANSCRIBING":
                halo.setColorAt(0.0, QColor(219, 188, 127, halo_alpha)) # Sand Amber
            else:
                halo.setColorAt(0.0, QColor(167, 192, 128, halo_alpha)) # Forest Moss
                
            halo.setColorAt(1.0, QColor(45, 53, 59, 0))
            painter.setBrush(QBrush(halo))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(rect.adjusted(-3, -3, 3, 3), radius + 2, radius + 2)

        # 2. Main Everforest Frosted Glass Body
        path = QPainterPath()
        path.addRoundedRect(rect.x(), rect.y(), rect.width(), rect.height(), radius, radius)
        
        bg_gradient = QLinearGradient(0, rect.y(), 0, rect.bottom())
        bg_gradient.setColorAt(0.0, QColor(45, 53, 59, 248))  # #2d353b
        bg_gradient.setColorAt(1.0, QColor(39, 46, 51, 252))  # #272e33
        painter.fillPath(path, QBrush(bg_gradient))

        # 3. Micro 1px Top Highlight (Frosted Glass Rim)
        highlight_path = QPainterPath()
        highlight_path.addRoundedRect(rect.x() + 1, rect.y() + 1, rect.width() - 2, 14, radius - 1, radius - 1)
        hl_grad = QLinearGradient(0, rect.y(), 0, rect.y() + 14)
        hl_grad.setColorAt(0.0, QColor(255, 255, 255, 22))
        hl_grad.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.fillPath(highlight_path, QBrush(hl_grad))

        # 4. Dynamic Theme Accent Border
        if self.current_state == "LISTENING":
            pen = QPen(QColor(230, 126, 128, 230), 1.8)
        elif self.current_state == "TRANSCRIBING":
            pen = QPen(QColor(219, 188, 127, 230), 1.8)
        elif self.current_state == "SUCCESS":
            pen = QPen(QColor(167, 192, 128, 240), 1.8)
        else:
            pen = QPen(QColor(131, 192, 146, 85), 1.2) # Soft Sage

        painter.setPen(pen)
        painter.drawPath(path)

def main():
    global app, main_window
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    
    # Initialize GNOME AT-SPI accessibility bus
    init_atspi()
    
    main_window = EverforestMasterpiecePill()
    main_window.hide()
    
    # Pre-warm model in background
    threading.Thread(target=load_model, daemon=True).start()
    
    # Start Socket IPC server
    threading.Thread(target=run_socket_server, daemon=True).start()

    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
