"""
wraping_test.py — Renns Object Engine Full Feature Demo
Showcase semua kombinasi fitur engine secara eksplisit.
"""

import sys
import os
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPainter, QPixmap, QColor, QLinearGradient, QRadialGradient
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea
)
import RennsObjectEngine as objects

objects.RennsStyle.load("style.rsty")

BG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "background.png")


def section(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet("""
        QLabel {
            color: rgba(155, 162, 215, 0.6);
            font-size: 9px;
            font-family: monospace;
            letter-spacing: 2.5px;
            padding: 0 2px;
        }
    """)
    lbl.setAlignment(Qt.AlignCenter)
    return lbl


def sub(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet("""
        QLabel {
            color: rgba(130, 136, 185, 0.45);
            font-size: 8px;
            font-family: monospace;
            letter-spacing: 1px;
        }
    """)
    lbl.setAlignment(Qt.AlignCenter)
    return lbl


class AuroraCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._bg_pm = None
        self.setAttribute(Qt.WA_StyledBackground, False)

    def set_bg_pixmap(self, pm):
        self._bg_pm = pm
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        w, h = self.width(), self.height()
        if self._bg_pm and not self._bg_pm.isNull():
            p.drawPixmap(self.rect(), self._bg_pm)
        else:
            grad = QLinearGradient(0, 0, w, h)
            grad.setColorAt(0.00, QColor(7,  9, 24))
            grad.setColorAt(0.40, QColor(11, 14, 38))
            grad.setColorAt(0.70, QColor(9,  20, 34))
            grad.setColorAt(1.00, QColor(5,  7, 20))
            p.fillRect(self.rect(), grad)
            for cx, cy, r, col in [
                (int(w*0.12), int(h*0.15), int(w*0.35), QColor(28,  75, 175,  16)),
                (int(w*0.85), int(h*0.30), int(w*0.30), QColor(75,  18, 155,  14)),
                (int(w*0.50), int(h*0.70), int(w*0.40), QColor(0,  130, 110,  12)),
                (int(w*0.22), int(h*0.72), int(w*0.24), QColor(165, 55,  18,   9)),
            ]:
                rg = QRadialGradient(cx, cy, r)
                rg.setColorAt(0.0, col)
                rg.setColorAt(1.0, QColor(0, 0, 0, 0))
                p.fillRect(self.rect(), rg)


class Main(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Renns Object Engine — Full Feature Demo")
        self.resize(760, 980)
        self.setMinimumSize(500, 680)

        self._bg_raw = QPixmap(BG) if os.path.exists(BG) else None

        self._canvas = AuroraCanvas(self)
        self._canvas.setGeometry(self.rect())

        # Scroll supaya semua section muat
        scroll = QScrollArea(self._canvas)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; } QScrollBar { width: 0px; height: 0px; }")
        scroll.setGeometry(self.rect())

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        scroll.setWidget(container)
        self._scroll = scroll

        root = QVBoxLayout(container)
        root.setContentsMargins(44, 52, 44, 52)
        root.setSpacing(0)
        root.setAlignment(Qt.AlignTop | Qt.AlignHCenter)

        # ════════════════════════════════════════════════════════
        # SECTION 1 — BUTTONS
        # ════════════════════════════════════════════════════════
        root.addWidget(section("BUTTONS"))
        root.addSpacing(18)

        # Row A: glass-border variants
        root.addWidget(sub("glass-border · spring+elastic  /  bounce+solid  /  ease-out+elastic"))
        root.addSpacing(10)
        rowA = QHBoxLayout(); rowA.setSpacing(14); rowA.setAlignment(Qt.AlignHCenter)

        rowA.addWidget(objects.Renns.object(
            "btn-glass-spring", parent=self._canvas,
            text="✦ spring drag",
            on_click=lambda: print("glass-spring")))

        rowA.addWidget(objects.Renns.object(
            "btn-solid-bounce", parent=self._canvas,
            text="◈ bounce",
            on_click=lambda: print("solid-bounce")))

        rowA.addWidget(objects.Renns.object(
            "btn-danger-elastic", parent=self._canvas,
            text="⚠ elastic",
            on_click=lambda: print("danger-elastic")))

        root.addLayout(rowA)
        root.addSpacing(14)

        # Row B: ghost + amber + pill
        root.addWidget(sub("linear+ghost  /  ease+amber  /  spring+pill+elastic"))
        root.addSpacing(10)
        rowB = QHBoxLayout(); rowB.setSpacing(14); rowB.setAlignment(Qt.AlignHCenter)

        rowB.addWidget(objects.Renns.object(
            "btn-ghost-linear", parent=self._canvas,
            text="ghost",
            on_click=lambda: print("ghost")))

        rowB.addWidget(objects.Renns.object(
            "btn-amber-ease", parent=self._canvas,
            text="↻ amber",
            on_click=lambda: print("amber")))

        rowB.addWidget(objects.Renns.object(
            "btn-pill-spring", parent=self._canvas,
            text="✧ pill",
            on_click=lambda: print("pill")))

        root.addLayout(rowB)
        root.addSpacing(14)

        # Row C: wide card
        root.addWidget(sub("ease-in-out · wide card · glass · heavy shadow"))
        root.addSpacing(10)
        rowC = QHBoxLayout(); rowC.setAlignment(Qt.AlignHCenter)
        rowC.addWidget(objects.Renns.object(
            "btn-card-ease", parent=self._canvas,
            text="wide card  ·  ease-in-out  ·  glass",
            on_click=lambda: print("card")))
        root.addLayout(rowC)
        root.addSpacing(14)

        # Row D: icon buttons
        root.addWidget(sub("icon circle: spring+glass+rotate  /  icon square: bounce+border biasa"))
        root.addSpacing(10)
        rowD = QHBoxLayout(); rowD.setSpacing(14); rowD.setAlignment(Qt.AlignHCenter)

        for sym in ["♦", "↺", "✦", "⊕"]:
            rowD.addWidget(objects.Renns.object(
                "btn-icon-circle", parent=self._canvas,
                text=sym, on_click=lambda s=sym: print(f"circle {s}")))

        rowD.addSpacing(14)

        for sym in ["⊞", "⊟", "⊠", "⊡"]:
            rowD.addWidget(objects.Renns.object(
                "btn-icon-square", parent=self._canvas,
                text=sym, on_click=lambda s=sym: print(f"square {s}")))

        root.addLayout(rowD)
        root.addSpacing(44)

        # ════════════════════════════════════════════════════════
        # SECTION 2 — TOGGLES
        # ════════════════════════════════════════════════════════
        root.addWidget(section("TOGGLES"))
        root.addSpacing(18)

        root.addWidget(sub("indigo: spring+glass+blur  /  rose: ease-out+border  /  minimal: linear  /  amber: bounce+glass"))
        root.addSpacing(12)

        tog_row = QHBoxLayout(); tog_row.setSpacing(36); tog_row.setAlignment(Qt.AlignHCenter)

        t1 = objects.Renns.toggle("tog-indigo", parent=self._canvas)
        t1.toggled.connect(lambda s: print("indigo:", "ON" if s else "OFF"))
        tog_row.addWidget(t1)

        t2 = objects.Renns.toggle("tog-rose", parent=self._canvas)
        t2.toggled.connect(lambda s: print("rose:", "ON" if s else "OFF"))
        tog_row.addWidget(t2)

        t3 = objects.Renns.toggle("tog-minimal", parent=self._canvas)
        t3.toggled.connect(lambda s: print("minimal:", "ON" if s else "OFF"))
        tog_row.addWidget(t3)

        t4 = objects.Renns.toggle("tog-amber", parent=self._canvas)
        t4.toggled.connect(lambda s: print("amber:", "ON" if s else "OFF"))
        tog_row.addWidget(t4)

        root.addLayout(tog_row)
        root.addSpacing(44)

        # ════════════════════════════════════════════════════════
        # SECTION 3 — ACTION GROUPS
        # ════════════════════════════════════════════════════════
        root.addWidget(section("ACTION GROUPS"))
        root.addSpacing(18)

        # Row AG1: horizontal center + horizontal right
        root.addWidget(sub("horizontal·center+glass  /  horizontal·right+glass+spring"))
        root.addSpacing(12)
        ag_row1 = QHBoxLayout(); ag_row1.setSpacing(28); ag_row1.setAlignment(Qt.AlignHCenter)

        ag1 = objects.Renns.action_group(
            "fab-indigo", parent=self._canvas,
            text="✦",
            direction="horizontal", anchor="center",
            children=[
                objects.Renns.object("item-slate", text="copy",  on_click=lambda: print("copy")),
                objects.Renns.object("item-slate", text="paste", on_click=lambda: print("paste")),
                objects.Renns.object("item-slate", text="share", on_click=lambda: print("share")),
            ]
        )
        ag_row1.addWidget(ag1)

        ag2 = objects.Renns.action_group(
            "fab-amber", parent=self._canvas,
            text="⋯",
            direction="horizontal", anchor="right",
            children=[
                objects.Renns.object("item-amber", text="edit",   on_click=lambda: print("edit")),
                objects.Renns.object("item-amber", text="export", on_click=lambda: print("export")),
            ]
        )
        ag_row1.addWidget(ag2)

        root.addLayout(ag_row1)
        root.addSpacing(18)

        # Row AG2: vertical + horizontal left
        root.addWidget(sub("vertical·top+border  /  horizontal·left+bounce+border"))
        root.addSpacing(12)
        ag_row2 = QHBoxLayout(); ag_row2.setSpacing(28); ag_row2.setAlignment(Qt.AlignHCenter)

        ag3 = objects.Renns.action_group(
            "fab-rose", parent=self._canvas,
            text="↓",
            direction="vertical", anchor="top",
            children=[
                objects.Renns.object("item-rose", text="option A", on_click=lambda: print("A")),
                objects.Renns.object("item-rose", text="option B", on_click=lambda: print("B")),
                objects.Renns.object("item-rose", text="option C", on_click=lambda: print("C")),
            ]
        )
        ag_row2.addWidget(ag3)

        ag4 = objects.Renns.action_group(
            "fab-indigo", parent=self._canvas,
            text="⊕",
            direction="horizontal", anchor="left",
            children=[
                objects.Renns.object("item-slate", text="save",   on_click=lambda: print("save")),
                objects.Renns.object("item-amber", text="send",   on_click=lambda: print("send")),
                objects.Renns.object("item-rose",  text="delete", on_click=lambda: print("delete")),
            ]
        )
        ag_row2.addWidget(ag4)

        root.addLayout(ag_row2)
        root.addSpacing(52)
        root.addStretch()

    def _register_texture(self):
        from RennsObjectEngine.button.button_ext.backdrop import set_window_texture
        if self._bg_raw and not self._bg_raw.isNull():
            scaled = self._bg_raw.scaled(self.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            self._canvas.set_bg_pixmap(scaled)
            set_window_texture(self, scaled)
        else:
            pm = self._canvas.grab()
            if not pm.isNull():
                set_window_texture(self, pm)

    def showEvent(self, event):
        super().showEvent(event)
        self._register_texture()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._canvas.setGeometry(self.rect())
        self._scroll.setGeometry(self.rect())
        from RennsObjectEngine.button.button_ext.backdrop import invalidate_window
        invalidate_window(self)
        QTimer.singleShot(50, self._register_texture)

    def paintEvent(self, event):
        pass


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    w = Main()
    w.show()
    sys.exit(app.exec())