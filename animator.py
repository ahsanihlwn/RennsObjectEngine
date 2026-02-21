# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/. 
# 
# Author: @ahsanihlwn
# Copyright (c) 2026 @ahsanihlwn

from PySide6.QtCore import QObject, QEvent
from PySide6.QtGui import QIcon
from .button.overlay import RennsOverlay, OVERLAY_CANVAS_FACTOR
from .renns_style import RennsStyle
from .button.button_ext.animation import resolve_easing
from .button.button_ext.transform import parse_transform
from PySide6.QtCore import QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QColor


class RennsAnimator(QObject):

    def __init__(self, widget, class_name):
        super().__init__(widget)

        self.widget = widget
        self.class_name = class_name
        self._hovered = False
        self._pressed = False

        self.overlay = RennsOverlay(widget.window(), None)
        self.overlay.render_mode = "rect"
        self.overlay.show()

        self.widget.installEventFilter(self)

        self.anim = QPropertyAnimation(self.overlay, b"scale")
        self.anim.setEasingCurve(QEasingCurve.OutCubic)

        self.update_visual_state()

    # =========================
    # EVENT FILTER
    # =========================

    def eventFilter(self, obj, event):

        if obj == self.widget:

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

        self._sync_overlay_position()

    def _sync_overlay_position(self):
        """
        Overlay canvas lebih besar dari widget (OVERLAY_CANVAS_FACTOR x).
        Di-center tepat di atas widget supaya animasi scale tidak ter-crop.
        """
        bw = self.widget.width()
        bh = self.widget.height()

        self.overlay._button_width = bw
        self.overlay._button_height = bh

        canvas_w = int(bw * OVERLAY_CANVAS_FACTOR)
        canvas_h = int(bh * OVERLAY_CANVAS_FACTOR)

        offset_x = (canvas_w - bw) // 2
        offset_y = (canvas_h - bh) // 2

        # Posisi center widget di window
        center = self.widget.mapTo(self.widget.window(),
                                   self.widget.rect().center())

        self.overlay.move(
            center.x() - canvas_w // 2,
            center.y() - canvas_h // 2
        )

        self.overlay.resize(canvas_w, canvas_h)