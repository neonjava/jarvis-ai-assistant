"""
JARVIS Desktop UI — PySide6 with Apple-inspired glassmorphism design
Main window with floating assistant orb, dashboard, and chat panel.
"""
from __future__ import annotations

import asyncio
import sys
import threading
from pathlib import Path
from typing import Optional

from PySide6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    QRect,
    QSize,
    Qt,
    QThread,
    QTimer,
    Signal,
    Slot,
)
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QIcon,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPixmap,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

# ── Color Palette ─────────────────────────────────────────────────────────────

COLORS = {
    "bg_primary": "#0A0E1A",
    "bg_secondary": "#0F1528",
    "bg_card": "#131929",
    "bg_glass": "rgba(19, 25, 41, 0.7)",
    "accent_primary": "#00D4FF",
    "accent_secondary": "#7B61FF",
    "accent_success": "#00E896",
    "accent_warning": "#FFB800",
    "accent_danger": "#FF4757",
    "text_primary": "#E8EEFF",
    "text_secondary": "#8B95C0",
    "text_muted": "#4A5578",
    "border": "rgba(0, 212, 255, 0.15)",
    "glow_blue": "rgba(0, 212, 255, 0.3)",
    "glow_purple": "rgba(123, 97, 255, 0.3)",
}

STYLESHEET = f"""
/* ═══════════════════════════════════════════════════
   JARVIS Design System — Dark Glassmorphism
═══════════════════════════════════════════════════ */

QMainWindow, QWidget {{
    background-color: {COLORS['bg_primary']};
    color: {COLORS['text_primary']};
    font-family: 'Inter', 'SF Pro Display', 'Segoe UI', sans-serif;
    font-size: 14px;
}}

/* Glass Card */
.GlassCard {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 rgba(19, 25, 41, 0.85),
        stop:1 rgba(10, 14, 26, 0.95));
    border: 1px solid {COLORS['border']};
    border-radius: 16px;
}}

/* Sidebar */
#sidebar {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {COLORS['bg_secondary']},
        stop:1 rgba(15, 21, 40, 0.95));
    border-right: 1px solid {COLORS['border']};
    min-width: 220px;
    max-width: 220px;
}}

/* Sidebar buttons */
#sidebar QPushButton {{
    background: transparent;
    border: none;
    border-radius: 12px;
    color: {COLORS['text_secondary']};
    font-size: 14px;
    font-weight: 500;
    padding: 12px 20px;
    text-align: left;
}}

#sidebar QPushButton:hover {{
    background: rgba(0, 212, 255, 0.08);
    color: {COLORS['accent_primary']};
}}

#sidebar QPushButton:checked {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 rgba(0, 212, 255, 0.2),
        stop:1 rgba(123, 97, 255, 0.1));
    color: {COLORS['accent_primary']};
    border-left: 3px solid {COLORS['accent_primary']};
}}

/* Metric Cards */
.MetricCard {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 rgba(19, 25, 41, 0.9),
        stop:1 rgba(10, 14, 26, 0.95));
    border: 1px solid {COLORS['border']};
    border-radius: 16px;
    padding: 20px;
}}

/* Chat Input */
#chat_input {{
    background: rgba(19, 25, 41, 0.9);
    border: 1px solid {COLORS['border']};
    border-radius: 24px;
    color: {COLORS['text_primary']};
    font-size: 15px;
    padding: 14px 60px 14px 24px;
    selection-background-color: {COLORS['accent_secondary']};
}}

#chat_input:focus {{
    border-color: {COLORS['accent_primary']};
    background: rgba(19, 25, 41, 0.95);
}}

/* Send button */
#send_btn {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {COLORS['accent_primary']},
        stop:1 {COLORS['accent_secondary']});
    border: none;
    border-radius: 20px;
    color: white;
    font-size: 16px;
    font-weight: 600;
}}

#send_btn:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #33DDFF,
        stop:1 #9480FF);
}}

#send_btn:pressed {{
    background: {COLORS['accent_secondary']};
}}

/* Chat messages */
.UserMessage {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 rgba(0, 212, 255, 0.15),
        stop:1 rgba(123, 97, 255, 0.1));
    border: 1px solid rgba(0, 212, 255, 0.2);
    border-radius: 16px 4px 16px 16px;
    padding: 14px 18px;
    color: {COLORS['text_primary']};
}}

.AssistantMessage {{
    background: rgba(19, 25, 41, 0.8);
    border: 1px solid {COLORS['border']};
    border-radius: 4px 16px 16px 16px;
    padding: 14px 18px;
    color: {COLORS['text_primary']};
}}

/* Progress bars */
QProgressBar {{
    background: rgba(19, 25, 41, 0.6);
    border: 1px solid {COLORS['border']};
    border-radius: 6px;
    height: 8px;
    text-align: center;
}}

QProgressBar::chunk {{
    border-radius: 6px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {COLORS['accent_primary']},
        stop:1 {COLORS['accent_secondary']});
}}

/* Scrollbar */
QScrollBar:vertical {{
    background: transparent;
    width: 6px;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background: {COLORS['text_muted']};
    border-radius: 3px;
    min-height: 30px;
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}

/* Labels */
.SectionTitle {{
    color: {COLORS['text_secondary']};
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 2px;
}}

.MetricValue {{
    color: {COLORS['text_primary']};
    font-size: 28px;
    font-weight: 700;
}}

.MetricLabel {{
    color: {COLORS['text_secondary']};
    font-size: 12px;
}}
"""


# ── Orb Widget ────────────────────────────────────────────────────────────────

class JarvisOrb(QWidget):
    """Animated JARVIS arc reactor orb."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedSize(80, 80)
        self._angle = 0
        self._pulse = 0.0
        self._pulse_dir = 1
        self._active = False

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._animate)
        self._timer.start(16)  # ~60fps

    def _animate(self) -> None:
        self._angle = (self._angle + 2) % 360
        self._pulse += 0.02 * self._pulse_dir
        if self._pulse >= 1.0:
            self._pulse_dir = -1
        elif self._pulse <= 0.0:
            self._pulse_dir = 1
        self.update()

    def set_active(self, active: bool) -> None:
        self._active = active
        self.update()

    def paintEvent(self, event: Any) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        cx, cy = self.width() / 2, self.height() / 2
        r = min(cx, cy) - 4

        # Outer glow
        glow_alpha = int(80 + 60 * self._pulse)
        outer_color = QColor(0, 212, 255, glow_alpha) if not self._active else QColor(123, 97, 255, glow_alpha)

        for i in range(3):
            grad = QRadialGradient(cx, cy, r + i * 6)
            grad.setColorAt(0, outer_color)
            grad.setColorAt(1, QColor(0, 0, 0, 0))
            painter.setBrush(grad)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(int(cx - r - i*6), int(cy - r - i*6), int((r + i*6)*2), int((r + i*6)*2))

        # Core circle
        core_grad = QRadialGradient(cx - r*0.2, cy - r*0.2, r)
        core_grad.setColorAt(0.0, QColor(100, 240, 255))
        core_grad.setColorAt(0.4, QColor(0, 180, 220))
        core_grad.setColorAt(0.7, QColor(0, 80, 150))
        core_grad.setColorAt(1.0, QColor(0, 20, 60))
        painter.setBrush(core_grad)
        painter.drawEllipse(int(cx - r), int(cy - r), int(r*2), int(r*2))

        # Rotating ring
        from PySide6.QtCore import QRectF
        from PySide6.QtGui import QPen
        ring_color = QColor(0, 212, 255, 200)
        pen = QPen(ring_color, 2)
        pen.setStyle(Qt.PenStyle.SolidLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        rect = QRectF(cx - r + 4, cy - r + 4, (r - 4)*2, (r - 4)*2)
        painter.drawArc(rect, self._angle * 16, 270 * 16)

        # Center dot
        painter.setBrush(QColor(255, 255, 255, 220))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(int(cx - 5), int(cy - 5), 10, 10)


# ── Metric Card ───────────────────────────────────────────────────────────────

class MetricCard(QFrame):
    def __init__(
        self,
        title: str,
        value: str = "0",
        unit: str = "%",
        icon: str = "◉",
        color: str = "#00D4FF",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setProperty("class", "MetricCard")
        self.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(19, 25, 41, 0.9),
                    stop:1 rgba(10, 14, 26, 0.95));
                border: 1px solid rgba(0, 212, 255, 0.15);
                border-radius: 16px;
                padding: 20px;
            }}
        """)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(color))
        shadow.setOffset(0, 0)
        self.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(20, 20, 20, 20)

        # Header row
        header = QHBoxLayout()
        icon_label = QLabel(icon)
        icon_label.setStyleSheet(f"color: {color}; font-size: 18px;")
        title_label = QLabel(title.upper())
        title_label.setStyleSheet(
            f"color: {COLORS['text_secondary']}; font-size: 10px; font-weight: 600; letter-spacing: 2px;"
        )
        header.addWidget(icon_label)
        header.addWidget(title_label)
        header.addStretch()
        layout.addLayout(header)

        # Value
        self.value_label = QLabel(f"{value}{unit}")
        self.value_label.setStyleSheet(
            f"color: {COLORS['text_primary']}; font-size: 32px; font-weight: 700;"
        )
        layout.addWidget(self.value_label)

        # Progress bar
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(int(float(value)) if value.replace('.', '').isdigit() else 0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(6)
        self.progress.setStyleSheet(f"""
            QProgressBar {{ background: rgba(19, 25, 41, 0.6); border: none; border-radius: 3px; }}
            QProgressBar::chunk {{ background: {color}; border-radius: 3px; }}
        """)
        layout.addWidget(self.progress)

    def update_value(self, value: float, unit: str = "%") -> None:
        self.value_label.setText(f"{value:.1f}{unit}")
        self.progress.setValue(int(value))


# ── Chat Message ──────────────────────────────────────────────────────────────

class ChatBubble(QFrame):
    def __init__(self, text: str, is_user: bool = False, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        if is_user:
            style = f"""
                QFrame {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 rgba(0, 212, 255, 0.15),
                        stop:1 rgba(123, 97, 255, 0.1));
                    border: 1px solid rgba(0, 212, 255, 0.2);
                    border-radius: 16px 4px 16px 16px;
                    padding: 2px;
                }}
            """
        else:
            style = f"""
                QFrame {{
                    background: rgba(19, 25, 41, 0.8);
                    border: 1px solid rgba(0, 212, 255, 0.15);
                    border-radius: 4px 16px 16px 16px;
                    padding: 2px;
                }}
            """

        self.setStyleSheet(style)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)

        # Sender label
        sender = QLabel("You" if is_user else "⚡ JARVIS")
        sender.setStyleSheet(
            f"color: {'#00D4FF' if is_user else '#7B61FF'}; font-size: 11px; font-weight: 600;"
        )
        layout.addWidget(sender)

        # Message
        msg = QLabel(text)
        msg.setWordWrap(True)
        msg.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 14px; line-height: 1.5;")
        msg.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(msg)


# ── Chat Panel ────────────────────────────────────────────────────────────────

class ChatPanel(QWidget):
    """Full chat interface."""

    message_sent = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header
        header = QFrame()
        header.setStyleSheet(f"""
            QFrame {{
                background: rgba(15, 21, 40, 0.95);
                border-bottom: 1px solid {COLORS['border']};
                padding: 0;
            }}
        """)
        header.setFixedHeight(60)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(24, 0, 24, 0)

        self.orb = JarvisOrb()
        header_layout.addWidget(self.orb)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title_lbl = QLabel("JARVIS")
        title_lbl.setStyleSheet(
            f"color: {COLORS['text_primary']}; font-size: 16px; font-weight: 700; letter-spacing: 3px;"
        )
        subtitle = QLabel("AI Desktop Assistant • Online")
        subtitle.setStyleSheet(
            f"color: {COLORS['accent_success']}; font-size: 11px;"
        )
        title_col.addWidget(title_lbl)
        title_col.addWidget(subtitle)
        header_layout.addLayout(title_col)
        header_layout.addStretch()

        clear_btn = QPushButton("Clear")
        clear_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                color: {COLORS['text_secondary']};
                font-size: 12px;
                padding: 6px 14px;
            }}
            QPushButton:hover {{ color: {COLORS['accent_primary']}; border-color: {COLORS['accent_primary']}; }}
        """)
        clear_btn.clicked.connect(self.clear_chat)
        header_layout.addWidget(clear_btn)

        layout.addWidget(header)

        # Messages area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; }")

        self._msg_container = QWidget()
        self._msg_container.setStyleSheet("background: transparent;")
        self._msg_layout = QVBoxLayout(self._msg_container)
        self._msg_layout.setSpacing(12)
        self._msg_layout.setContentsMargins(20, 20, 20, 20)
        self._msg_layout.addStretch()

        scroll.setWidget(self._msg_container)
        self._scroll = scroll
        layout.addWidget(scroll)

        # Input area
        input_frame = QFrame()
        input_frame.setStyleSheet(f"""
            QFrame {{
                background: rgba(10, 14, 26, 0.95);
                border-top: 1px solid {COLORS['border']};
            }}
        """)
        input_layout = QHBoxLayout(input_frame)
        input_layout.setContentsMargins(20, 16, 20, 16)
        input_layout.setSpacing(12)

        self.input = QLineEdit()
        self.input.setObjectName("chat_input")
        self.input.setPlaceholderText("Ask JARVIS anything, or give a command...")
        self.input.returnPressed.connect(self._send)

        self.send_btn = QPushButton("▶")
        self.send_btn.setObjectName("send_btn")
        self.send_btn.setFixedSize(40, 40)
        self.send_btn.clicked.connect(self._send)

        input_layout.addWidget(self.input)
        input_layout.addWidget(self.send_btn)
        layout.addWidget(input_frame)

        # Welcome message
        self._add_message("Hello! I'm JARVIS, your AI desktop assistant. Ask me anything or give me a command.", False)

    def _send(self) -> None:
        text = self.input.text().strip()
        if not text:
            return
        self.input.clear()
        self._add_message(text, True)
        self.orb.set_active(True)
        self.message_sent.emit(text)

    def _add_message(self, text: str, is_user: bool) -> None:
        bubble = ChatBubble(text, is_user)
        row = QHBoxLayout()
        if is_user:
            row.addStretch()
            row.addWidget(bubble, 0, Qt.AlignmentFlag.AlignRight)
        else:
            row.addWidget(bubble, 0, Qt.AlignmentFlag.AlignLeft)
            row.addStretch()

        # Insert before the stretch
        self._msg_layout.insertLayout(self._msg_layout.count() - 1, row)

        # Scroll to bottom
        QTimer.singleShot(50, lambda: self._scroll.verticalScrollBar().setValue(
            self._scroll.verticalScrollBar().maximum()
        ))

    @Slot(str)
    def add_response(self, text: str) -> None:
        self.orb.set_active(False)
        self._add_message(text, False)

    def clear_chat(self) -> None:
        while self._msg_layout.count() > 1:
            item = self._msg_layout.takeAt(0)
            if item.layout():
                while item.layout().count():
                    w = item.layout().takeAt(0).widget()
                    if w:
                        w.deleteLater()


# ── Dashboard Panel ───────────────────────────────────────────────────────────

class DashboardPanel(QWidget):
    """System metrics dashboard."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._setup_ui()
        self._start_monitor()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # Title
        title = QLabel("SYSTEM DASHBOARD")
        title.setStyleSheet(
            f"color: {COLORS['text_secondary']}; font-size: 11px; font-weight: 600; letter-spacing: 3px;"
        )
        layout.addWidget(title)

        # Metric cards grid
        grid_row1 = QHBoxLayout()
        grid_row1.setSpacing(12)

        self.cpu_card = MetricCard("CPU", "0", "%", "⚡", "#00D4FF")
        self.ram_card = MetricCard("RAM", "0", "%", "💾", "#7B61FF")
        self.disk_card = MetricCard("DISK", "0", "%", "💿", "#00E896")
        self.temp_card = MetricCard("TEMP", "--", "°C", "🌡️", "#FFB800")

        for card in [self.cpu_card, self.ram_card, self.disk_card, self.temp_card]:
            grid_row1.addWidget(card)

        layout.addLayout(grid_row1)

        # Battery row
        grid_row2 = QHBoxLayout()
        grid_row2.setSpacing(12)

        self.battery_card = MetricCard("BATTERY", "--", "%", "🔋", "#00E896")
        self.net_up_card = MetricCard("NET UP", "0", " MB/s", "📤", "#00D4FF")
        self.net_down_card = MetricCard("NET DOWN", "0", " MB/s", "📥", "#7B61FF")

        for card in [self.battery_card, self.net_up_card, self.net_down_card]:
            grid_row2.addWidget(card)
        grid_row2.addStretch()

        layout.addLayout(grid_row2)
        layout.addStretch()

    def _start_monitor(self) -> None:
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_metrics)
        self._timer.start(2000)
        self._prev_net: Optional[Any] = None

    def _update_metrics(self) -> None:
        import psutil

        cpu = psutil.cpu_percent()
        self.cpu_card.update_value(cpu)

        ram = psutil.virtual_memory()
        self.ram_card.update_value(ram.percent)

        disk = psutil.disk_usage("/")
        self.disk_card.update_value(disk.percent)

        try:
            temps = psutil.sensors_temperatures()
            temp_val = None
            for key in ("coretemp", "k10temp", "cpu_thermal"):
                if key in temps:
                    temp_val = max(t.current for t in temps[key])
                    break
            if temp_val:
                self.temp_card.update_value(temp_val, "°C")
        except Exception:
            pass

        battery = psutil.sensors_battery()
        if battery:
            self.battery_card.update_value(battery.percent)

        # Network
        net = psutil.net_io_counters()
        if self._prev_net:
            up = (net.bytes_sent - self._prev_net.bytes_sent) / 1024 / 1024 / 2
            down = (net.bytes_recv - self._prev_net.bytes_recv) / 1024 / 1024 / 2
            self.net_up_card.update_value(round(up, 2), " MB/s")
            self.net_down_card.update_value(round(down, 2), " MB/s")
        self._prev_net = net


# ── Sidebar ───────────────────────────────────────────────────────────────────

class Sidebar(QWidget):
    page_changed = Signal(int)

    PAGES = [
        ("💬", "Chat"),
        ("📊", "Dashboard"),
        ("🔌", "Plugins"),
        ("⚙️", "Settings"),
    ]

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("sidebar")
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(4)
        layout.setContentsMargins(12, 20, 12, 20)

        # Logo
        logo = QLabel("J·A·R·V·I·S")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setStyleSheet(f"""
            color: {COLORS['accent_primary']};
            font-size: 14px;
            font-weight: 800;
            letter-spacing: 6px;
            padding: 16px 0;
        """)
        layout.addWidget(logo)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {COLORS['border']};")
        layout.addWidget(sep)
        layout.addSpacing(12)

        # Nav buttons
        self._buttons: list[QPushButton] = []
        for icon, label in self.PAGES:
            btn = QPushButton(f"  {icon}  {label}")
            btn.setCheckable(True)
            btn.setFixedHeight(44)
            self._buttons.append(btn)
            layout.addWidget(btn)

        self._buttons[0].setChecked(True)

        for i, btn in enumerate(self._buttons):
            btn.clicked.connect(lambda checked, idx=i: self._on_click(idx))

        layout.addStretch()

        # Version
        ver = QLabel(f"v1.0.0")
        ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ver.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px;")
        layout.addWidget(ver)

    def _on_click(self, idx: int) -> None:
        for i, btn in enumerate(self._buttons):
            btn.setChecked(i == idx)
        self.page_changed.emit(idx)


# ── Main Window ───────────────────────────────────────────────────────────────

class JarvisWindow(QMainWindow):
    """JARVIS main application window."""

    response_ready = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("JARVIS — AI Desktop Assistant")
        self.setMinimumSize(1200, 800)
        self.resize(1400, 900)

        # Apply stylesheet
        self.setStyleSheet(STYLESHEET)

        self._setup_ui()
        self._setup_api_client()
        self.response_ready.connect(self.chat_panel.add_response)

    def _setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QHBoxLayout(central)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Sidebar
        self.sidebar = Sidebar()
        self.sidebar.page_changed.connect(self._change_page)
        main_layout.addWidget(self.sidebar)

        # Content area
        self.stack = QStackedWidget()

        # Pages
        self.chat_panel = ChatPanel()
        self.chat_panel.message_sent.connect(self._handle_message)

        self.dashboard_panel = DashboardPanel()

        placeholder_plugins = self._placeholder_page("🔌", "Plugins", "Plugin marketplace coming soon")
        placeholder_settings = self._placeholder_page("⚙️", "Settings", "Configuration panel coming soon")

        self.stack.addWidget(self.chat_panel)
        self.stack.addWidget(self.dashboard_panel)
        self.stack.addWidget(placeholder_plugins)
        self.stack.addWidget(placeholder_settings)

        main_layout.addWidget(self.stack)

    def _placeholder_page(self, icon: str, title: str, subtitle: str) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl_icon = QLabel(icon)
        lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_icon.setStyleSheet("font-size: 64px;")

        lbl_title = QLabel(title)
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_title.setStyleSheet(
            f"color: {COLORS['text_primary']}; font-size: 24px; font-weight: 700;"
        )

        lbl_sub = QLabel(subtitle)
        lbl_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_sub.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 14px;")

        layout.addWidget(lbl_icon)
        layout.addSpacing(16)
        layout.addWidget(lbl_title)
        layout.addWidget(lbl_sub)

        return w

    def _change_page(self, idx: int) -> None:
        self.stack.setCurrentIndex(idx)

    def _setup_api_client(self) -> None:
        """Setup background thread for API communication."""
        from api.app import app as fastapi_app
        # Start FastAPI server in background thread
        self._api_thread = threading.Thread(
            target=self._run_api,
            daemon=True,
        )
        self._api_thread.start()

        # WebSocket client for responses
        self._ws_loop = asyncio.new_event_loop()
        self._ws_thread = threading.Thread(
            target=self._ws_loop.run_forever,
            daemon=True,
        )
        self._ws_thread.start()

    def _run_api(self) -> None:
        import uvicorn
        from config.settings import settings
        uvicorn.run(
            "api.app:app",
            host=settings.API_HOST,
            port=settings.API_PORT,
            log_level="warning",
            reload=False,
        )

    @Slot(str)
    def _handle_message(self, text: str) -> None:
        """Send message to AI and get response."""
        asyncio.run_coroutine_threadsafe(
            self._async_chat(text),
            self._ws_loop,
        )

    async def _async_chat(self, text: str) -> None:
        try:
            import httpx
            from config.settings import settings

            await asyncio.sleep(0.5)  # Wait for server to be ready

            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"http://localhost:{settings.API_PORT}/api/v1/chat/command",
                    json={"command": text, "confirm": False},
                    timeout=60,
                )
                data = resp.json()
                response = data.get("response", "Command executed.")
                self.response_ready.emit(response)
        except Exception as e:
            self.response_ready.emit(f"Error: {e}")


# ── Application Entry ─────────────────────────────────────────────────────────

def run_desktop_app() -> None:
    """Launch the JARVIS desktop application."""
    app = QApplication(sys.argv)
    app.setApplicationName("JARVIS")
    app.setApplicationVersion("1.0.0")

    # High DPI
    app.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)

    window = JarvisWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    run_desktop_app()
