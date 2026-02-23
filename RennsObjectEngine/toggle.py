# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/. 
# 
# Author: @ahsanihlwn
# Copyright (c) 2026 @ahsanihlwn

import math
from PySide6.QtCore import QPropertyAnimation, QEasingCurve, QPoint, QPointF, Qt
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QColor
from .button.button_ext.css_color import parse_css_color
from .button.button import RennsButton
from .button.button_ext.animation import resolve_easing
from .renns_style import RennsStyle
from PySide6.QtCore import Signal

def _is_springy(easing_name: str) -> bool:
    return easing_name in ("spring", "bounce")


class RennsToggle(QWidget):
    toggled = Signal(bool)

    def __init__(self, class_name: str, parent=None):
        super().__init__(parent)

        self._checked               = False
        self._class_name            = class_name
        self._pos_anim              = None
        self._knob_dragging         = False
        self._knob_drag_start_pos   = None
        self._knob_drag_mouse_start = None
        self._drag_moved            = False
        self._knob_drag_prev_x      = None   # untuk velocity tracking
        self._knob_drag_vel_x       = 0.0    # velocity frame sebelumnya

        # Baca CSS dulu sebelum buat button -- track.width() selalu 0 di __init__
        _tc = RennsStyle.get(class_name, "base", "toggle")
        _kc = RennsStyle.get(class_name, "base", "toggle-knob")
        try:    self._track_w = int(float(_tc.get("width",  64)))
        except: self._track_w = 64
        try:    self._track_h = int(float(_tc.get("height", 34)))
        except: self._track_h = 34
        try:    self._knob_w  = int(float(_kc.get("width",  26)))
        except: self._knob_w  = 26
        try:    self._knob_h  = int(float(_kc.get("height", 26)))
        except: self._knob_h  = 26

        # Toggle widget harus cukup besar untuk knob
        self._widget_w = max(self._track_w, self._knob_w)
        self._widget_h = max(self._track_h, self._knob_h)

        # ===== TRACK — disable semua events =====
        self.track = RennsButton(render_type="rect", parent=self)
        self.track._managed_z_order = True
        self.track.setClass(class_name, component="toggle")
        self.track.enterEvent        = lambda e: e.ignore()
        self.track.leaveEvent        = lambda e: e.ignore()
        self.track.mousePressEvent   = lambda e: e.ignore()
        self.track.mouseReleaseEvent = lambda e: e.ignore()
        self.track.mouseMoveEvent    = lambda e: e.ignore()

        # ===== KNOB — disable hover =====
        self.knob = RennsButton(render_type="rect", parent=self)
        self.knob._managed_z_order = True
        self.knob.setClass(class_name, component="toggle-knob")
        self.knob.enterEvent = lambda e: e.ignore()
        self.knob.leaveEvent = lambda e: e.ignore()

        # Paksa resize sesuai CSS -- managed_z_order skip resize di _apply_class
        self.track.resize(self._track_w, self._track_h)
        self.knob.resize(self._knob_w,  self._knob_h)

        self.track.installEventFilter(self)

        self.setFixedSize(self._widget_w, self._widget_h)
        # Track di-center vertikal dalam toggle widget
        self.track.move(0, (self._widget_h - self._track_h) // 2)
        self._layout_knob_instant()

        # JANGAN pakai track.clicked — itu trigger update_visual_state yg override warna
        # Klik ditangani di mousePressEvent toggle sendiri

        # Override knob events
        self.knob.mousePressEvent   = self._knob_mouse_press
        self.knob.mouseMoveEvent    = self._knob_mouse_move
        self.knob.mouseReleaseEvent = self._knob_mouse_release

    # =========================================================
    # SHOW — z-order sekali
    # =========================================================

    def showEvent(self, event):
        super().showEvent(event)
        if self.track.overlay:
            self.track.overlay.show()
        if self.knob.overlay:
            self.knob.overlay.show()
            self.knob.overlay.raise_()
        self._layout_knob_instant()
        # Sync overlay setelah layout selesai posisikan toggle
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, self._sync_all_overlays)

    # =========================================================
    # HELPERS
    # =========================================================

    def _knob_left_x(self):  return 4
    def _knob_right_x(self): return self._track_w - self._knob_w - 4
    def _knob_y(self):       return (self._widget_h - self._knob_h) // 2
    def _track_half(self):   return self._track_w / 2.0

    def _get_transition(self, component):
        base = RennsStyle.get(self._class_name, "base", component)
        return RennsStyle.parse_transition(base.get("transition", "0.25s ease"))

    def _layout_knob_instant(self):
        x = self._knob_right_x() if self._checked else self._knob_left_x()
        self.knob.move(x, self._knob_y())

    def _get_elastic_drag(self):
        """
        Baca elastic-drag dari semua state toggle (base, hover, active).
        Property ini bisa ada di state manapun.
        """
        for state in ("hover", "active", "base"):
            props = RennsStyle.get(self._class_name, state, "toggle")
            val = props.get("elastic-drag")
            if val:
                try:
                    return float(val)
                except:
                    pass
        return 0.0

    def _get_track_bg(self, state: str) -> str:
        """Ambil background track untuk state tertentu, fallback ke base."""
        props = RennsStyle.get(self._class_name, state, "toggle")
        base  = RennsStyle.get(self._class_name, "base", "toggle")
        return props.get("background", base.get("background", "#444444"))

    # =========================================================
    # KLIK AREA TRACK — handle di toggle, bukan track.clicked
    # =========================================================

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # Klik di mana saja di area toggle = toggle
            # (knob drag punya handler sendiri di _knob_mouse_press)
            self._toggle()
        super().mousePressEvent(event)

    # =========================================================
    # TOGGLE (klik)
    # =========================================================

    def _toggle(self):
        self._checked = not self._checked
        self._sync_track_color()
        self._snap_knob_animated()
        self.toggled.emit(self._checked)
    # =========================================================
    # TRACK COLOR — handle base/hover/active semua
    # =========================================================

    def _sync_track_color(self, state: str = None):
        """
        Update warna track sesuai state.
        state=None → resolve dari _checked + _track_hovered.
        """
        ov = self.track.overlay
        if not ov:
            return

        if state is None:
            if self._checked:
                state = "active"
            elif getattr(self, "_track_hovered", False):
                state = "hover"
            else:
                state = "base"

        target_bg    = self._get_track_bg(state)
        target_color = parse_css_color(target_bg)

        # Skip kalau udah menuju warna yang sama
        current_end = ov.color_anim.endValue()
        if isinstance(current_end, QColor) and target_color == current_end \
                and ov.color_anim.state() == QPropertyAnimation.Running:
            return

        dur_s, easing_name = self._get_transition("toggle")
        curve = resolve_easing(easing_name)

        ov.color_anim.stop()
        ov.color_anim.setStartValue(ov._bg_color)
        ov.color_anim.setEndValue(target_color)
        ov.color_anim.setDuration(int(dur_s * 1000))
        ov.color_anim.setEasingCurve(curve)
        ov.color_anim.start()

    # =========================================================
    # TRACK HOVER — forward dari knob/toggle area
    # =========================================================

    def eventFilter(self, obj, event):
        from PySide6.QtCore import QEvent
        if obj == self.track:
            if event.type() == QEvent.MouseButtonPress:
                self.mousePressEvent(event)
                return True
            elif event.type() == QEvent.MouseButtonRelease:
                self.mouseReleaseEvent(event)
                return True
        return False

    def enterEvent(self, event):
        self._track_hovered = True
        if not self._checked:
            self._sync_track_color("hover")
        self._sync_knob_color("hover")
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._track_hovered = False
        if not self._checked:
            self._sync_track_color("base")
        self._sync_knob_color("base")
        super().leaveEvent(event)

    def _sync_knob_color(self, state: str):
        ov = self.knob.overlay
        if not ov:
            return
        props     = RennsStyle.get(self._class_name, state, "toggle-knob")
        base      = RennsStyle.get(self._class_name, "base", "toggle-knob")
        target_bg = props.get("background", base.get("background", "#ffffff"))
        target    = parse_css_color(target_bg)
        dur_s, easing_name = self._get_transition("toggle-knob")
        ov.color_anim.stop()
        ov.color_anim.setStartValue(ov._bg_color)
        ov.color_anim.setEndValue(target)
        ov.color_anim.setDuration(int(dur_s * 1000))
        ov.color_anim.setEasingCurve(resolve_easing(easing_name))
        ov.color_anim.start()

    # =========================================================
    # SNAP KNOB
    # =========================================================

    def _snap_knob_animated(self, easing_override=None):
        target_x = self._knob_right_x() if self._checked else self._knob_left_x()
        target_y = self._knob_y()

        dur_s, easing_name = self._get_transition("toggle-knob")
        dur_ms  = int(dur_s * 1000)
        curve   = easing_override if easing_override else resolve_easing(easing_name)
        springy = _is_springy(easing_name)

        anim = QPropertyAnimation(self.knob, b"pos")
        anim.setDuration(dur_ms)
        anim.setEasingCurve(curve)
        anim.setStartValue(self.knob.pos())
        anim.setEndValue(QPoint(target_x, target_y))

        def on_moved(_pos):
            self.knob._sync_overlay_position()
            if not springy:
                return
            # Tali — overshoot knob narik track
            overshoot = self.knob.x() - target_x
            stretch   = math.tanh(overshoot / max(1, self._track_half()) * 3.0) * 0.30
            self._set_track_stretch_instant(stretch, 1 if overshoot >= 0 else -1)
            self._set_knob_jelly_instant(min(abs(stretch) * 1.3, 0.5),
                                         1 if overshoot >= 0 else -1)

        anim.valueChanged.connect(on_moved)
        anim.finished.connect(self._on_snap_finished)
        anim.start()
        self._pos_anim = anim

        if springy:
            self._set_knob_jelly_instant(0.4, 1 if self._checked else -1)

    def _on_snap_finished(self):
        self._reset_track_stretch_animated()
        self._reset_knob_jelly_animated()

    # =========================================================
    # DRAG KNOB
    # =========================================================

    def _knob_mouse_press(self, event):
        if event.button() != Qt.LeftButton:
            return
        self._knob_dragging         = True
        self._drag_moved            = False
        self._knob_drag_start_pos   = self.knob.pos()
        self._knob_drag_mouse_start = event.globalPosition().toPoint()
        self._knob_drag_prev_x      = event.globalPosition().x()
        self._knob_drag_vel_x       = 0.0
        self.knob._pressed = True
        self.knob.update_visual_state()
        if self._pos_anim:
            self._pos_anim.stop()
        event.accept()

    def _knob_mouse_move(self, event):
        if not self._knob_dragging:
            return

        mouse_now = event.globalPosition().toPoint()
        dx = mouse_now.x() - self._knob_drag_mouse_start.x()

        if abs(dx) > 3:
            self._drag_moved = True

        left_x  = self._knob_left_x()
        right_x = self._knob_right_x()
        raw_x   = self._knob_drag_start_pos.x() + dx

        # ── Velocity frame ini ──────────────────────────────
        cur_x   = event.globalPosition().x()
        frame_v = cur_x - (self._knob_drag_prev_x or cur_x)
        # Smooth: 70% prev + 30% baru
        self._knob_drag_vel_x = self._knob_drag_vel_x * 0.70 + frame_v * 0.30
        self._knob_drag_prev_x = cur_x
        speed = abs(self._knob_drag_vel_x)

        # Overflow = tarikan di luar batas
        overflow = 0.0
        if   raw_x < left_x:  overflow = raw_x - left_x
        elif raw_x > right_x: overflow = raw_x - right_x

        clamped_x = max(left_x, min(right_x, raw_x))
        self.knob.move(clamped_x, self._knob_y())
        self.knob._sync_overlay_position()

        # ── ELASTIC DRAG TRACK ─────────────────────────────
        elastic_radius = self._get_elastic_drag()
        if elastic_radius > 0 and abs(overflow) > 0:
            raw_mapped = abs(overflow) / (self.track.width() * elastic_radius / 10.0)
            mapped     = math.tanh(raw_mapped * 1.2)
            stretch    = mapped * 0.85 * (1 if overflow > 0 else -1)
            self._set_track_elastic_drag(stretch, overflow)
        else:
            self._set_track_stretch_instant(0.0, 1)

        # ── KNOB JELLY ──────────────────────────────────────
        # Bergerak → gepeng Y (tegak lurus arah gerak horizontal)
        # Mendadak berhenti (speed kecil tapi flatten masih besar) → gepeng X sesaat
        _, easing_name = self._get_transition("toggle-knob")
        if _is_springy(easing_name):
            drag_frac   = abs(dx) / max(1, right_x - left_x)
            target_flat = math.tanh(drag_frac * 2.5) * 0.45

            ov = self.knob.overlay
            if ov:
                prev_flat = ov._elastic_flatten

                # Deteksi "mendadak berhenti": velocity turun drastis
                # sementara flatten masih besar
                if speed < 1.5 and prev_flat > 0.12:
                    # Berhenti mendadak → flip ke X sesaat
                    # Ini akan di-reset via _reset_knob_jelly_damped saat release
                    # Saat drag masih aktif: gepeng X tapi fade cepat
                    ov._elastic_vec_x = 1.0 if dx > 0 else -1.0
                    ov._elastic_vec_y = 0.0
                    # Flatten tetap pakai nilai sekarang, biar keliatan
                    ov._elastic_flatten = min(prev_flat, 0.55)
                else:
                    # Normal gerak: gepeng Y (vx=0, vy=1 = tegak lurus)
                    ov._elastic_vec_x = 0.0
                    ov._elastic_vec_y = 1.0
                    ov._elastic_flatten = target_flat
                ov.update()

        # Blend warna track
        progress = (clamped_x - left_x) / max(1, right_x - left_x)
        self._blend_track_color(progress)

        event.accept()

    def _knob_mouse_release(self, event):
        if not self._knob_dragging:
            return
        self._knob_dragging = False
        self.knob._pressed  = False
        self.knob.update_visual_state()

        if not self._drag_moved:
            self._toggle()
            return

        left_x      = self._knob_left_x()
        right_x     = self._knob_right_x()
        new_checked = self.knob.x() >= (left_x + right_x) / 2

        if new_checked != self._checked:
            self._checked = new_checked
            self.toggled.emit(self._checked)

        self._sync_track_color()
        self._reset_track_stretch_animated()

        # Tentukan arah drag terakhir untuk arah gepeng saat release
        dx_total = self.knob.x() - self._knob_drag_start_pos.x() if self._knob_drag_start_pos else 0
        dx_dir   = 1 if dx_total >= 0 else -1

        _, easing_name = self._get_transition("toggle-knob")
        self._snap_knob_animated(easing_override=resolve_easing(easing_name))
        self._reset_knob_jelly_animated(dx_dir=dx_dir)
        event.accept()

    # =========================================================
    # KNOB JELLY
    # =========================================================

    def _set_knob_jelly_instant(self, flatten: float, direction: int):
        ov = self.knob.overlay
        if not ov: return
        ov._elastic_flatten = max(0.0, float(flatten))
        ov._elastic_vec_x   = float(direction)
        ov._elastic_vec_y   = 0.0
        ov.update()

    def _reset_knob_jelly_animated(self, dx_dir: int = 1):
        """
        Damped oscillation saat release:
          gepeng X (arah gerak) → normal → gepeng Y kecil → normal → settle

        Sama persis dengan elastic.py reset_elastic:
          easing(t)=0   → output=peak (gepeng X)
          easing(t)=1   → output=0    (normal)
          easing(t)=1.2 → output=-0.2*peak (gepeng berlawanan, arah Y)
          easing(t)=0.96→ output=+0.04*peak
          settle
        """
        from PySide6.QtCore import QPointF
        ov = self.knob.overlay
        if not ov: return

        # Saat release: paksa vec ke arah X (arah drag terakhir)
        ov._elastic_vec_x = float(dx_dir)
        ov._elastic_vec_y = 0.0
        peak = max(ov._elastic_flatten, 0.25)  # minimal peak supaya efek keliatan
        ov._elastic_flatten = peak

        flatten_curve = QEasingCurve(QEasingCurve.BezierSpline)
        flatten_curve.addCubicBezierSegment(
            QPointF(0.15, 0.00), QPointF(0.28, 1.00), QPointF(0.35, 1.00)
        )
        flatten_curve.addCubicBezierSegment(
            QPointF(0.40, 1.00), QPointF(0.46, 1.20), QPointF(0.50, 1.20)
        )
        flatten_curve.addCubicBezierSegment(
            QPointF(0.54, 1.20), QPointF(0.59, 1.00), QPointF(0.62, 1.00)
        )
        flatten_curve.addCubicBezierSegment(
            QPointF(0.65, 1.00), QPointF(0.69, 0.96), QPointF(0.72, 0.96)
        )
        flatten_curve.addCubicBezierSegment(
            QPointF(0.75, 0.96), QPointF(0.78, 1.00), QPointF(0.80, 1.00)
        )
        flatten_curve.addCubicBezierSegment(
            QPointF(0.88, 1.00), QPointF(0.95, 1.00), QPointF(1.00, 1.00)
        )

        anim = QPropertyAnimation(ov, b"elastic_flatten_prop")
        anim.setDuration(420)
        anim.setStartValue(peak)
        anim.setEndValue(0.0)
        anim.setEasingCurve(flatten_curve)
        anim.start()
        ov._jelly_reset = anim

    # =========================================================
    # TRACK STRETCH / ELASTIC DRAG
    # =========================================================

    def _set_track_elastic_drag(self, stretch_signed: float, overflow: float):
        """
        Track melar ke arah knob ditarik.
        Hanya pakai _elastic_flatten (horizontal) — TANPA _elastic_offset_x
        karena offset menggeser overlay dan menyebabkan geter.
        """
        ov = self.track.overlay
        if not ov: return
        direction   = 1 if overflow >= 0 else -1
        abs_stretch = abs(stretch_signed)

        # Flatten lebih besar biar efek melar keliatan
        ov._elastic_flatten  = abs_stretch * 1.2
        ov._elastic_vec_x    = float(direction)
        ov._elastic_vec_y    = 0.0
        # Nol-kan offset — ini sumber geter sebelumnya
        ov._elastic_offset_x = 0.0
        ov._elastic_offset_y = 0.0
        ov.update()

    def _set_track_stretch_instant(self, stretch_norm: float, direction: int):
        ov = self.track.overlay
        if not ov: return
        ov._elastic_flatten  = abs(stretch_norm)
        ov._elastic_vec_x    = float(direction)
        ov._elastic_vec_y    = 0.0
        ov._elastic_offset_x = 0.0
        ov._elastic_offset_y = 0.0
        ov.update()

    def _reset_track_stretch_animated(self):
        ov = self.track.overlay
        if not ov: return

        dur_s, easing_name = self._get_transition("toggle")
        dur_ms = int(dur_s * 1000)

        if _is_springy(easing_name):
            curve = QEasingCurve(QEasingCurve.OutElastic)
            curve.setAmplitude(0.55)
            curve.setPeriod(0.35)
        else:
            curve = QEasingCurve(QEasingCurve.OutCubic)

        af = QPropertyAnimation(ov, b"elastic_flatten_prop")
        af.setDuration(dur_ms); af.setStartValue(ov._elastic_flatten)
        af.setEndValue(0.0);    af.setEasingCurve(curve); af.start()
        ov._stretch_f = af

        ax = QPropertyAnimation(ov, b"elastic_offset_x")
        ax.setDuration(dur_ms); ax.setStartValue(ov._elastic_offset_x)
        ax.setEndValue(0.0);    ax.setEasingCurve(curve); ax.start()
        ov._stretch_x = ax

    # =========================================================
    # TRACK COLOR BLEND (drag realtime)
    # =========================================================

    def _blend_track_color(self, progress: float):
        ov = self.track.overlay
        if not ov: return
        c1 = parse_css_color(self._get_track_bg("base"))
        c2 = parse_css_color(self._get_track_bg("active"))
        r  = int(c1.red()   + (c2.red()   - c1.red())   * progress)
        g  = int(c1.green() + (c2.green() - c1.green()) * progress)
        b  = int(c1.blue()  + (c2.blue()  - c1.blue())  * progress)
        a  = int(c1.alpha() + (c2.alpha() - c1.alpha()) * progress)
        ov.color_anim.stop()
        ov._bg_color = QColor(r, g, b, a)
        ov.update()

    # =========================================================

    def _sync_all_overlays(self):
        self.track._sync_overlay_position()
        self.knob._sync_overlay_position()

    def moveEvent(self, event):
        super().moveEvent(event)
        self._sync_all_overlays()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._sync_all_overlays()

    def isChecked(self): return self._checked
    def setChecked(self, v):
        if v != self._checked:
            self._checked = v
            self._sync_track_color()
            self._layout_knob_instant()