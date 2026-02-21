# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/. 
# 
# Author: @ahsanihlwn
# Copyright (c) 2026 @ahsanihlwn

from PySide6.QtWidgets import QWidget, QPushButton
from PySide6.QtCore import Qt, QEvent, QPropertyAnimation
from PySide6.QtGui import QPainter, QColor
from .renns_style import RennsStyle
from .button.overlay import RennsOverlay, OVERLAY_CANVAS_FACTOR
from .button.button_ext.transform import parse_transform
from .button.button_ext.animation import resolve_easing


class RennsButtonWrapper(QWidget):

    def __init__(self, button: QPushButton, class_name: str, parent=None):
        super().__init__(parent)

        self.button = button
        self.class_name = class_name

        self.button.setParent(self)

        self.button.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
            }
        """)

        self.button.setAttribute(Qt.WA_TranslucentBackground)

        self.overlay = RennsOverlay(self, None)
        self.overlay.render_mode = "rect"
        self.overlay.show()

        self._hovered = False
        self._pressed = False

        self.anim = QPropertyAnimation(self.overlay, b"scale")

        self.button.installEventFilter(self)

        self._apply_base_size()
        self.update_visual_state()

    # =========================

    def _apply_base_size(self):
        base = RennsStyle.get(self.class_name, "base")
        bw = int(base.get("width", 80))
        bh = int(base.get("height", 80))

        self.resize(bw, bh)
        self.button.resize(bw, bh)

        # Overlay canvas lebih besar, di-center dalam wrapper
        canvas_w = int(bw * OVERLAY_CANVAS_FACTOR)
        canvas_h = int(bh * OVERLAY_CANVAS_FACTOR)
        offset_x = (canvas_w - bw) // 2
        offset_y = (canvas_h - bh) // 2

        self.overlay._button_width = bw
        self.overlay._button_height = bh

        # Overlay bisa keluar dari batas wrapper, jadi parenting ke window
        # Jika overlay di-parent ke self, Qt akan clip. Kita pakai window() supaya bebas.
        # (Sudah di-parent ke self di __init__; cukup resize & reposition)
        self.overlay.setGeometry(
            -offset_x,
            -offset_y,
            canvas_w,
            canvas_h
        )

    # =========================

    def eventFilter(self, obj, event):

        if event.type() == QEvent.Enter:
            self._hovered = True
            self.update_visual_state()

        elif event.type() == QEvent.Leave:
            self._hovered = False
            self.update_visual_state()

        elif event.type() == QEvent.MouseButtonPress:
            self._pressed = True
            self.update_visual_state()

        elif event.type() == QEvent.MouseButtonRelease:
            self._pressed = False
            self.update_visual_state()

        return False

    # =========================

    def _resolve_state(self):
        if self._pressed:
            return "active"
        elif self._hovered:
            return "hover"
        return "base"

    def update_visual_state(self):

        state = self._resolve_state()

        props = RennsStyle.get(self.class_name, state)
        base_props = RennsStyle.get(self.class_name, "base")

        merged = base_props.copy()
        merged.update(props)

        transform_value = merged.get("transform")
        scale, rotate = parse_transform(transform_value)

        transition_value = merged.get("transition", "0.25s ease")
        duration, easing = RennsStyle.parse_transition(transition_value)

        curve = resolve_easing(easing)

        self.anim.stop()
        self.anim.setDuration(int(duration * 1000))
        self.anim.setEasingCurve(curve)
        self.anim.setEndValue(scale)
        self.anim.start()

        self.overlay.rotate = rotate

        bg = merged.get("background")
        if bg:
            self.overlay.bgColor = QColor(bg)

        self.overlay.style_data = merged
        self.overlay.update()