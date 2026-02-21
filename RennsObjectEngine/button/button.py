# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/. 
# 
# Author: @ahsanihlwn
# Copyright (c) 2026 @ahsanihlwn

from PySide6.QtWidgets import QPushButton
from PySide6.QtCore import QPropertyAnimation, QEasingCurve, Property, Qt, QSize
from PySide6.QtGui import QIcon, QPainter
from PySide6.QtCore import QPointF
from ..renns_style import RennsStyle
from .overlay import RennsOverlay
from .button_ext.animation import resolve_easing
from .button_ext.transform import parse_transform
from PySide6.QtGui import QColor

class RennsButton(QPushButton):
    def __init__(
        self,
        icon_path: str = None,
        render_type: str = "icon",
        hover_mode: str = "expand",
        hover_percent: float = 20.0,
        duration: float = 0.3,
        parent=None
    ):
        super().__init__(parent)

        self.hover_percent = hover_percent / 100.0
        self.hover_mode = hover_mode
        self.duration_ms = int(duration * 1000)
        self.render_type = render_type

        if icon_path:
            self.icon_obj = QIcon(icon_path)
        else:
            self.icon_obj = None

        self.setStyleSheet("border:none; background:transparent;")

        self._scale = 1.0
        self.target_scale = 1.0 + self.hover_percent

        self.anim = QPropertyAnimation(self, b"scale")
        self.overlay = None
        self.anim.setDuration(self.duration_ms)
        self.anim.setEasingCurve(QEasingCurve.OutCubic)

        self._overlay_active = False
        self._hovered = False
        self._pressed = False
        self._drag_origin = None
        self._drag_offset = QPointF(0, 0)
        self._elastic_radius = 0.0

        self._class_name = None
        self._component = None

        self._pending_class = None
        self._pending_component = None
        self._overlay_ready = False
        self._managed_z_order = False

        # Ukuran untuk layout (sizeHint) — stabil, tidak berubah saat hover
        self._layout_w = 0
        self._layout_h = 0

    # ======================
    # OVERLAY LIFECYCLE
    # ======================

    def _ensure_overlay(self):
        if self._overlay_ready:
            return

        root = self.window()
        self.overlay = RennsOverlay(root, self.icon_obj)
        self.overlay.render_mode = self.render_type
        self.overlay.button_ref = self
        self.overlay.show()
        self._overlay_ready = True

        if self._pending_class:
            self._apply_class(self._pending_class, self._pending_component)
            self._pending_class = None
            self._pending_component = None

    def showEvent(self, event):
        super().showEvent(event)
        self._ensure_overlay()
        self._sync_overlay_position()

    # ======================
    # CLASS / STYLE
    # ======================

    def setClass(self, class_name, component=None):
        self._class_name = class_name
        self._component = component

        if not self._overlay_ready:
            self._pending_class = class_name
            self._pending_component = component
            RennsStyle.apply(self, class_name, component)
            return

        self._apply_class(class_name, component)

    def _apply_class(self, class_name, component=None):
        self._class_name = class_name
        self._component = component

        # RennsStyle.apply resize widget kalau CSS punya width/height
        RennsStyle.apply(self, class_name, component)

        # Tentukan ukuran tombol dari CSS base
        base_props = RennsStyle.get(class_name, "base", component)
        css_w    = base_props.get("width")
        css_h    = base_props.get("height")
        obj_size = base_props.get("object-size")

        # Prioritas: width/height > object-size > ukuran widget sekarang
        try:    btn_w = int(float(css_w)) if css_w else None
        except: btn_w = None
        try:    btn_h = int(float(css_h)) if css_h else None
        except: btn_h = None

        if btn_w is None or btn_h is None:
            try:    fallback = int(float(obj_size)) if obj_size else None
            except: fallback = None
            if btn_w is None: btn_w = fallback or max(self.width(),  1) or 64
            if btn_h is None: btn_h = fallback or max(self.height(), 1) or 64

        # Resize widget SEKALI ke ukuran ini dan lock sebagai ukuran layout
        # Dengan override sizeHint, layout tidak akan geser widget lain
        if self._layout_w == 0:
            self._layout_w = btn_w
            self._layout_h = btn_h

        # Hanya resize kalau bukan managed (bukan child dari toggle/composite)
        # _managed_z_order=True artinya parent yang atur ukuran dan posisi
        if not self._managed_z_order:
            self.resize(btn_w, btn_h)
            self.updateGeometry()

        OVERLAY_MULTIPLIER = 5
        overlay_w = int(btn_w * OVERLAY_MULTIPLIER)
        overlay_h = int(btn_h * OVERLAY_MULTIPLIER)

        self.overlay.resize(overlay_w, overlay_h)
        self.overlay._btn_w = btn_w
        self.overlay._btn_h = btn_h

        if not self._managed_z_order:
            self.overlay.show()

        self._sync_overlay_position()
        self.update_visual_state()

    # ======================
    # VISUAL STATE
    # ======================

    def update_visual_state(self):
        self._sync_overlay_position()

        if not self._overlay_ready or not self.overlay or not self._class_name:
            return

        state = self._resolve_state()
        style_data = self._resolve_style_for_render(state)
        scale, rotate, duration, easing_name = self._resolve_style(state)

        bg = style_data.get("background")
        if bg and self.overlay:
            new_color = QColor(bg)
            self.overlay.color_anim.stop()
            self.overlay.color_anim.setStartValue(self.overlay.bgColor)
            self.overlay.color_anim.setEndValue(new_color)
            self.overlay.color_anim.setDuration(int(duration * 1000))
            self.overlay.color_anim.start()

        if self.overlay:
            self.overlay.style_data = style_data
            try:
                target_fs = float(style_data.get("font-size", "13"))
            except:
                target_fs = 13.0
            self.overlay.set_font_size(target_fs)
            self.overlay.update()

        self._apply_animation(scale, duration, easing_name, rotate)

    def _resolve_state(self):
        if self._pressed:
            return "active"
        elif self._hovered:
            return "hover"
        return "base"

    def _resolve_style(self, state):
        c = self._component
        props = RennsStyle.get(self._class_name, state, c)
        base_props = RennsStyle.get(self._class_name, "base", c)

        elastic_value = base_props.get("elastic-drag", None)
        try:
            self._elastic_radius = float(elastic_value) if elastic_value else 0.0
        except:
            self._elastic_radius = 0.0

        transform_value = props.get("transform", base_props.get("transform", None))
        scale, rotate = parse_transform(transform_value)

        transition_value = base_props.get("transition", "0.25s ease")
        if "transition" in props:
            transition_value = props["transition"]

        duration, easing_name = RennsStyle.parse_transition(transition_value)
        return scale, rotate, duration, easing_name

    def _resolve_style_for_render(self, state):
        c = self._component
        props = RennsStyle.get(self._class_name, state, c)
        base_props = RennsStyle.get(self._class_name, "base", c)
        merged = base_props.copy()
        merged.update(props)
        return merged

    # ======================
    # SIZE HINT — layout pakai ini, bukan ukuran widget fisik
    # Supaya widget bisa di-resize untuk hit area tanpa geser layout
    # ======================

    def sizeHint(self):
        if self._layout_w > 0 and self._layout_h > 0:
            return QSize(self._layout_w, self._layout_h)
        return super().sizeHint()

    def minimumSizeHint(self):
        return self.sizeHint()

    # ======================
    # HIT TEST — rect based pakai overlay._btn_w/_btn_h
    # ======================

    def hitButton(self, pos):
        if not self.overlay:
            return self.rect().contains(pos.toPoint())

        s  = self.overlay.scale
        bw = self.overlay._btn_w if self.overlay._btn_w > 0 else self.width()
        bh = self.overlay._btn_h if self.overlay._btn_h > 0 else self.height()

        # Center pos relatif ke widget
        widget_cx = self.width() / 2
        widget_cy = self.height() / 2

        dx = abs(pos.x() - widget_cx)
        dy = abs(pos.y() - widget_cy)

        return dx <= (bw / 2) * s and dy <= (bh / 2) * s

    # ======================
    # ANIMATION
    # ======================

    def _apply_animation(self, scale, duration, easing_name, rotate=0.0):
        if not self.overlay:
            return

        self._overlay_active = True
        self.update()

        curve = resolve_easing(easing_name)

        self.overlay.anim.stop()
        self.overlay.anim.setStartValue(self.overlay.scale)
        self.overlay.anim.setEasingCurve(curve)
        self.overlay.anim.setDuration(int(duration * 1000))
        self.overlay.anim.setEndValue(scale)
        self.overlay.anim.start()

        self.overlay.rotate_anim.stop()
        self.overlay.rotate_anim.setStartValue(self.overlay.rotate)
        self.overlay.rotate_anim.setEasingCurve(curve)
        self.overlay.rotate_anim.setDuration(int(duration * 1000))
        self.overlay.rotate_anim.setEndValue(rotate)
        self.overlay.rotate_anim.start()

    # ======================
    # SCALE PROPERTY
    # ======================

    def getScale(self): return self._scale
    def setScale(self, value): self._scale = value; self.update()
    scale = Property(float, getScale, setScale)

    # ======================
    # OVERLAY SYNC
    # ======================

    def _sync_overlay_position(self):
        if not self.overlay:
            return
        center = self.mapTo(self.window(), self.rect().center())
        self.overlay.move(
            center.x() - self.overlay.width() // 2,
            center.y() - self.overlay.height() // 2
        )

    def _clear_overlay(self):
        if self.overlay:
            if self.overlay.anim:
                self.overlay.anim.stop()
            self.overlay.deleteLater()
            self.overlay = None

    # ======================
    # EVENTS
    # ======================

    def moveEvent(self, event):
        self._sync_overlay_position()
        super().moveEvent(event)

    def resizeEvent(self, event):
        self._sync_overlay_position()
        super().resizeEvent(event)

    def enterEvent(self, event):
        self._hovered = True
        self.update_visual_state()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update_visual_state()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        self._pressed = True
        self._drag_origin = event.position()
        self.update_visual_state()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self._pressed = False
        self.update_visual_state()
        self._drag_origin = None
        self._drag_offset = QPointF(0, 0)
        if self.overlay:
            from .button_ext.elastic import reset_elastic
            reset_elastic(self.overlay)
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        from .button_ext.elastic import apply_elastic
        if self._pressed and self._elastic_radius > 0 and self.overlay:
            apply_elastic(self, event)
        super().mouseMoveEvent(event)

    # ======================
    # PAINT
    # ======================

    def paintEvent(self, event):
        if self._overlay_active:
            return
        if not self.icon_obj:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        self.icon_obj.paint(painter, self.rect(), Qt.AlignCenter)