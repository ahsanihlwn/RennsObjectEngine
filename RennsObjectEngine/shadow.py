# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Author: @ahsanihlwn
# Copyright (c) 2026 @ahsanihlwn

import re
from typing import Optional, List

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import (
    Qt, QRectF, QTimer, QEvent, QObject, Property,
    QPropertyAnimation, QEasingCurve
)
from PySide6.QtGui import QPainter, QColor, QPixmap, QBrush


# ─────────────────────────── CSS parser ────────────────────────────

def parse_box_shadow(value: str) -> List[dict]:
    normalized = re.sub(
        r'\(([^)]*)\)',
        lambda m: '(' + m.group(1).replace(',', '|') + ')',
        value
    )
    return [s for s in (_parse_single(p.strip().replace('|', ','))
                        for p in normalized.split(',')) if s]


def _parse_single(value: str) -> Optional[dict]:
    color = QColor(0, 0, 0, 80)
    m = re.search(r'rgba?\([^)]+\)', value)
    if m:
        color = _parse_rgba(m.group(0))
        value = value.replace(m.group(0), '')
    else:
        m = re.search(r'#[0-9a-fA-F]{3,8}', value)
        if m:
            from .button.button_ext.css_color import parse_css_color as _pc
            color = _pc(m.group(0))
            value = value.replace(m.group(0), '')
    tokens = re.findall(r'-?\d+(?:\.\d+)?', value)
    if len(tokens) < 2:
        return None
    try:
        return {
            "ox":     float(tokens[0]),
            "oy":     float(tokens[1]),
            "blur":   float(tokens[2]) if len(tokens) > 2 else 0.0,
            "spread": float(tokens[3]) if len(tokens) > 3 else 0.0,
            "color":  color,
        }
    except (ValueError, IndexError):
        return None


def _parse_rgba(value: str) -> QColor:
    m = re.search(r'rgba?\(([^)]+)\)', value)
    if not m:
        from .button.button_ext.css_color import parse_css_color as _pc
        return _pc(value)
    parts = [p.strip() for p in m.group(1).split(',')]
    try:
        return QColor(int(parts[0]), int(parts[1]), int(parts[2]),
                      int(float(parts[3]) * 255) if len(parts) > 3 else 255)
    except (ValueError, IndexError):
        return QColor(0, 0, 0, 80)


# ─────────────────────────── Blur + bake ───────────────────────────

def _blur_pixmap(src: QPixmap, radius: int) -> QPixmap:
    """Qt GPU blur — tidak freeze."""
    if radius <= 0:
        return src
    from PySide6.QtWidgets import (
        QGraphicsScene, QGraphicsPixmapItem, QGraphicsBlurEffect
    )
    scene = QGraphicsScene()
    item  = QGraphicsPixmapItem(src)
    fx    = QGraphicsBlurEffect()
    fx.setBlurRadius(radius * 2)
    fx.setBlurHints(QGraphicsBlurEffect.QualityHint)
    item.setGraphicsEffect(fx)
    scene.addItem(item)
    out = QPixmap(src.size())
    out.fill(Qt.transparent)
    p = QPainter(out)
    scene.render(p)
    p.end()
    return out


def _bake(shadows: List[dict], bw: int, bh: int,
          radius: float) -> List[tuple]:
    """Bake list of shadow dicts → [(pixmap, pad, ox, oy)]."""
    result = []
    for sh in shadows:
        blur   = max(0.0, sh["blur"])
        spread = sh["spread"]
        ox, oy = sh["ox"], sh["oy"]
        pad    = int(blur * 1.5) + int(abs(ox)) + int(abs(oy)) + int(spread) + 4
        pw, ph = max(1, bw + pad * 2), max(1, bh + pad * 2)

        pm = QPixmap(pw, ph)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        r = min(radius, bh / 2, bw / 2)
        p.setBrush(QBrush(sh["color"]))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(
            QRectF(pad - spread, pad - spread,
                   bw + spread * 2, bh + spread * 2), r, r
        )
        p.end()

        br = int(blur / 2)
        if br > 0:
            pm = _blur_pixmap(pm, br)

        result.append((pm, pad, ox, oy))
    return result


# ─────────────────────────── _ShadowLayer ──────────────────────────

class _ShadowLayer(QWidget):
    """Floating widget shadow, support crossfade antar state."""

    def __init__(self, parent_window, btn_w: int, btn_h: int,
                 shadows: List[dict], border_radius: float = 12.0):
        super().__init__(parent_window)
        self._bw      = btn_w
        self._bh      = btn_h
        self._radius  = border_radius
        self._scale   = 1.0

        self._sh_from  = shadows
        self._sh_to    = shadows
        self._c_from   = []
        self._c_to     = []
        self._key_from = None
        self._key_to   = None
        self._cf       = 1.0   # 0=from, 1=to

        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self._anim = QPropertyAnimation(self, b"cf")
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

        self._rebake_all()
        self._resize_canvas()

    # Qt property
    def getCf(self):    return self._cf
    def setCf(self, v): self._cf = float(v); self.update()
    cf = Property(float, getCf, setCf)

    def _key(self, sh_list):
        return (self._bw, self._bh, self._radius, self._scale, id(sh_list))

    def _rebake_all(self):
        bw = max(1, int(self._bw * self._scale))
        bh = max(1, int(self._bh * self._scale))
        k = self._key(self._sh_from)
        if self._key_from != k:
            self._c_from   = _bake(self._sh_from, bw, bh, self._radius)
            self._key_from = k
        k2 = self._key(self._sh_to)
        if self._key_to != k2:
            self._c_to   = _bake(self._sh_to, bw, bh, self._radius)
            self._key_to = k2

    def _resize_canvas(self):
        bw = max(1, int(self._bw * self._scale))
        bh = max(1, int(self._bh * self._scale))
        ext = 8
        for cache in (self._c_from, self._c_to):
            for _, pad, ox, oy in cache:
                ext = max(ext, pad + abs(ox) + abs(oy))
        self.resize(bw + ext * 2, bh + ext * 2)

    def set_scale(self, s: float):
        if abs(s - self._scale) < 0.001:
            return
        self._scale    = s
        self._key_from = None
        self._key_to   = None
        self._rebake_all()
        self._resize_canvas()
        self.update()

    def transition_shadows(self, new_shadows: List[dict],
                           dur_ms: int, easing: QEasingCurve):
        # Snap from = to saat ini
        self._sh_from  = self._sh_to
        self._c_from   = self._c_to
        self._key_from = self._key_to

        self._sh_to  = new_shadows
        self._key_to = None
        bw = max(1, int(self._bw * self._scale))
        bh = max(1, int(self._bh * self._scale))
        self._c_to   = _bake(new_shadows, bw, bh, self._radius)
        self._key_to = self._key(new_shadows)

        self._resize_canvas()

        self._anim.stop()
        self._anim.setDuration(max(60, dur_ms))
        self._anim.setEasingCurve(easing)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.start()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        cw, ch = self.width(), self.height()
        cf = max(0.0, min(1.0, self._cf))

        if self._c_from and cf < 1.0:
            painter.setOpacity(1.0 - cf)
            for pm, _, ox, oy in self._c_from:
                painter.drawPixmap(
                    (cw - pm.width()) // 2 + int(ox),
                    (ch - pm.height()) // 2 + int(oy), pm)

        if self._c_to and cf > 0.0:
            painter.setOpacity(cf)
            for pm, _, ox, oy in self._c_to:
                painter.drawPixmap(
                    (cw - pm.width()) // 2 + int(ox),
                    (ch - pm.height()) // 2 + int(oy), pm)


# ─────────────────────────── RennsShadow ───────────────────────────

class RennsShadow(QObject):
    """Attach + manage shadow layer untuk RennsButton."""

    def __init__(self, button, class_name: str = None, component=None):
        super().__init__(button)
        self._button     = button
        self._class_name = class_name or getattr(button, '_class_name', None)
        self._component  = component
        self._layer: Optional[_ShadowLayer] = None

        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._sync_scale)

        button.installEventFilter(self)

        if button.window() and button.isVisible():
            self._init_layer()
        else:
            QTimer.singleShot(0, self._init_layer)

    def _init_layer(self):
        if self._layer:
            return
        btn = self._button
        if not btn.window() or not self._class_name:
            return

        from .renns_style import RennsStyle

        # Cek apakah ada box-shadow di state manapun
        has_shadow = any(
            RennsStyle.get(self._class_name, s, self._component).get("box-shadow")
            for s in ("base", "hover", "active")
        )
        if not has_shadow:
            return

        base    = RennsStyle.get(self._class_name, "base", self._component)
        css     = base.get("box-shadow", "")
        shadows = parse_box_shadow(css) if css else []

        try:    radius = float(base.get("border-radius", 12))
        except: radius = 12.0

        bw = getattr(btn, '_layout_w', 0) or btn.width() or 64
        bh = getattr(btn, '_layout_h', 0) or btn.height() or 64

        self._layer = _ShadowLayer(
            parent_window=btn.window(),
            btn_w=bw, btn_h=bh,
            shadows=shadows, border_radius=radius,
        )
        self._layer.show()
        self._layer.lower()
        self._sync_pos()
        self._timer.start()

    def _sync_pos(self):
        if not self._layer:
            return
        btn = self._button
        if not btn.window():
            return
        c  = btn.mapTo(btn.window(), btn.rect().center())
        lw = self._layer.width()
        lh = self._layer.height()
        self._layer.move(c.x() - lw // 2, c.y() - lh // 2)

    def _sync_scale(self):
        if not self._layer:
            return
        ov = getattr(self._button, 'overlay', None)
        if ov:
            self._layer.set_scale(getattr(ov, '_scale', 1.0))
            self._sync_pos()

    def set_state(self, state: str, dur_ms: int, easing: QEasingCurve):
        """Crossfade shadow ke state CSS. Dipanggil dari button.update_visual_state."""
        if not self._layer or not self._class_name:
            return
        from .renns_style import RennsStyle
        base_p  = RennsStyle.get(self._class_name, "base",  self._component)
        state_p = RennsStyle.get(self._class_name, state,   self._component)
        css     = {**base_p, **state_p}.get("box-shadow", "")
        shadows = parse_box_shadow(css) if css else []
        self._layer.transition_shadows(shadows, dur_ms, easing)

    def eventFilter(self, obj, event):
        if obj is self._button:
            t = event.type()
            if t in (QEvent.Move, QEvent.Resize, QEvent.Show):
                self._sync_pos()
            elif t == QEvent.Hide and self._layer:
                self._layer.hide()
            elif t == QEvent.Show and self._layer:
                self._layer.show()
        return False

    def deleteLater(self):
        self._timer.stop()
        if self._layer:
            self._layer.deleteLater()
            self._layer = None
        super().deleteLater()


# ─────────────────────────── Helper ────────────────────────────────

def attach_shadow(widget, class_name: str = None,
                  component=None) -> Optional[RennsShadow]:
    """
    Buat RennsShadow kalau CSS punya box-shadow di state manapun.
    Return None kalau tidak ada — tidak crash.
    """
    cn = class_name or getattr(widget, '_class_name', None)
    if not cn:
        return None

    from .renns_style import RennsStyle
    has_shadow = any(
        RennsStyle.get(cn, s, component).get("box-shadow")
        for s in ("base", "hover", "active")
    )
    if not has_shadow:
        return None

    return RennsShadow(widget, cn, component)