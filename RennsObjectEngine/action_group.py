# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Author: @ahsanihlwn
# Copyright (c) 2026 @ahsanihlwn

"""
RennsActionGroup — floating pill action menu
============================================

Item bisa berupa:
  - dict  : {"class": "fab-item", "text": "Edit", "on_click": fn}
  - RennsButton : langsung dari Renns.object(...)

Saat RennsButton dipakai sebagai item:
  - Button overlay-nya di-reparent ke window (sudah begitu)
  - Posisi overlay disync ke slot rect yang sudah di-transform oleh pill scale
  - Hover/active/elastic semua dari button itu sendiri — tidak ada override
  - Pill hanya menggambar background pill + slot background untuk item dict

Style (.rss):

    .fab {
        width: 56;
        height: 56;
        background: #2d2f3a;
        border-radius: 28;
        color: #ffffff;
        font-size: 20;
        font-weight: bold;
        transition: 0.35s spring;
        action-direction: horizontal;
        action-anchor: left;
        action-gap: 6;
        action-padding: 6;
        action-item-width: 110;
        action-item-height: 44;
    }
    .fab:hover  { background: #3b3f52; transform: scale(1.06); }
    .fab:active { background: #4a4f65; transform: scale(0.9) rotate(45deg); }

    .fab-item {
        background: #3b3f52;
        border-radius: 10;
        color: #ffffff;
        font-size: 13;
        transition: 0.18s ease-out;
    }
    .fab-item:hover  { background: #4a4f65; }
    .fab-item:active { background: #5a6080; transform: scale(0.96); }

Python (dict):
    group = Renns.action_group(
        "fab", parent=self, text="+",
        children=[
            {"class": "fab-item", "text": "Edit",   "on_click": fn},
        ]
    )

Python (RennsButton):
    group = Renns.action_group(
        "fab", parent=self, text="+",
        children=[
            Renns.object("primary", text="pencet", on_click=lambda: print("click")),
            Renns.object("primary", text="ok",     on_click=lambda: print("ok")),
        ]
    )
"""

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import (
    QPropertyAnimation, QEasingCurve, Property,
    Qt, QRect, QRectF, QPoint, QPointF, QTimer, Signal, QEvent, QObject
)
from PySide6.QtGui import (
    QPainter, QColor, QBrush, QFont, QCursor, QTransform
)
import warnings as _warnings

def _safe_disconnect(signal):
    """Disconnect semua slot dari signal tanpa warning."""
    with _warnings.catch_warnings():
        _warnings.simplefilter("ignore")
        try:
            signal.disconnect()
        except (RuntimeError, TypeError):
            pass

from .button.button import RennsButton
from .button.button_ext.animation import resolve_easing
from .button.button_ext.transform import parse_transform
from .renns_style import RennsStyle
from .button.button_ext.css_color import parse_css_color
from .button.button_ext.backdrop import draw_backdrop_blur


# ─────────────────────────────────────────────────────────────
#  Slot color animator
# ─────────────────────────────────────────────────────────────

class _SlotColor(QObject):
    """QObject host untuk animasi warna satu slot (dict item)."""
    def __init__(self, base_color: QColor, repaint_fn):
        super().__init__()
        self._c       = QColor(base_color)
        self._repaint = repaint_fn
        self._anim    = QPropertyAnimation(self, b"col")
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

    def getCol(self):    return self._c
    def setCol(self, c): self._c = QColor(c); self._repaint()
    col = Property(QColor, getCol, setCol)

    def go(self, target: QColor, dur_ms: int, easing: QEasingCurve):
        self._anim.stop()
        self._anim.setStartValue(QColor(self._c))
        self._anim.setEndValue(target)
        self._anim.setDuration(max(60, dur_ms))
        self._anim.setEasingCurve(easing)
        self._anim.start()

    @property
    def color(self): return self._c


_SlotBorder = _SlotColor


class _SlotScale(QObject):
    def __init__(self, base_scale: float, repaint_fn):
        super().__init__()
        self._s       = float(base_scale)
        self._repaint = repaint_fn
        self._anim    = QPropertyAnimation(self, b"sc")

    def getSc(self):    return self._s
    def setSc(self, v): self._s = float(v); self._repaint()
    sc = Property(float, getSc, setSc)

    def go(self, target: float, dur_ms: int, easing: QEasingCurve):
        self._anim.stop()
        self._anim.setStartValue(float(self._s))
        self._anim.setEndValue(float(target))
        self._anim.setDuration(max(60, dur_ms))
        self._anim.setEasingCurve(easing)
        self._anim.start()

    @property
    def scale(self): return self._s


# ─────────────────────────────────────────────────────────────
#  Floating pill overlay
# ─────────────────────────────────────────────────────────────

class _PillOverlay(QWidget):
    """
    Canvas floating di-parent ke window().
    Menggambar pill background + slot dict.
    Untuk item RennsButton: sync posisi overlay button ke slot yang di-transform.
    """

    close_requested = Signal()
    item_clicked    = Signal(int)   # hanya untuk item dict

    def __init__(self, parent_window, trigger_ref: 'RennsActionGroup',
                 items: list, class_name: str, direction: str, anchor: str):
        super().__init__(parent_window)

        self._trigger_ref = trigger_ref
        self.items        = items          # list of dict | RennsButton
        self.class_name   = class_name
        self.direction    = direction
        self.anchor       = anchor

        self._hovered_idx = -1   # hanya untuk dict slots
        self._pressed_idx = -1
        self._pill_scale  = 0.0
        self._opacity     = 0.0

        # ── Baca CSS ─────────────────────────────────────────
        base = RennsStyle.get(class_name, "base")
        def _i(k, d):
            try:    return int(float(base.get(k, d)))
            except: return d

        self._gap      = _i("action-gap",          6)
        self._pad      = _i("action-padding",       6)
        self._trig_w   = _i("width",               56)
        self._trig_h   = _i("height",              56)
        self._item_w   = _i("action-item-width",  110)
        self._item_h   = _i("action-item-height",  44)

        dur_s, eas_name = RennsStyle.parse_transition(
            base.get("transition", "0.32s ease-out")
        )
        self._dur_ms = max(100, int(dur_s * 1000))
        self._easing = resolve_easing(eas_name)

        # ── Pill size ─────────────────────────────────────────
        # Untuk item RennsButton, ambil ukuran dari button itu sendiri
        n = len(items)
        item_w, item_h = self._measure_items()

        if direction == "horizontal":
            self._pill_w = self._pad * 2 + self._trig_w + self._gap + n * item_w + (n - 1) * self._gap
            self._pill_h = max(self._trig_h, item_h) + self._pad * 2
        else:
            self._pill_w = max(self._trig_w, item_w) + self._pad * 2
            self._pill_h = self._pad * 2 + self._trig_h + self._gap + n * item_h + (n - 1) * self._gap

        self._item_w = item_w
        self._item_h = item_h

        MARGIN = 80
        self._margin    = MARGIN
        self._canvas_w  = self._pill_w + MARGIN * 2
        self._canvas_h  = self._pill_h + MARGIN * 2
        self.resize(self._canvas_w, self._canvas_h)

        # ── Shadow pill
        self._pill_shadow = None
        self._init_pill_shadow(base)

        # ── Animasi ───────────────────────────────────────────
        self._scale_anim = QPropertyAnimation(self, b"pill_scale")
        self._scale_anim.setEasingCurve(self._easing)
        self._scale_anim.setDuration(self._dur_ms)

        self._opacity_anim = QPropertyAnimation(self, b"pill_opacity")
        self._opacity_anim.setEasingCurve(QEasingCurve.OutCubic)

        # ── Slot colors (hanya untuk dict item) ───────────────
        self._slot_colors: list[_SlotColor] = []
        self._slot_borders: list = []
        self._slot_scales: list = []
        self._rebuild_slot_colors()

        # ── Button items: sembunyikan + connect clicked ───────
        for i, item in enumerate(self.items):
            if isinstance(item, RennsButton):
                item.setParent(self)  # child of pill → selalu di atas pill, klik langsung diterima
                item.hide()
                if item.overlay:
                    item.overlay.hide()
                # Saat button diklik → close pill
                # Capture i untuk closure yang bener
                def _make_handler(idx):
                    def _handler():
                        self.item_clicked.emit(idx)
                    return _handler
                item.clicked.connect(_make_handler(i))

        self.setMouseTracking(True)
        self.setAttribute(Qt.WA_TranslucentBackground)

        # Text pixmap cache — sama seperti RennsOverlay supaya rendering identik
        self._text_pm_cache: dict = {}   # key → QPixmap

        self.hide()

    # ── Ukuran item ───────────────────────────────────────────

    def _measure_items(self):
        """Ambil ukuran dari CSS item — item.width() selalu 0 sebelum show."""
        for item in self.items:
            if isinstance(item, RennsButton):
                cn = getattr(item, '_class_name', None)
                if cn:
                    ib = RennsStyle.get(cn, "base", getattr(item, '_component', None))
                    try:    w = int(float(ib.get("width",  self._item_w)))
                    except: w = self._item_w
                    try:    h = int(float(ib.get("height", self._item_h)))
                    except: h = self._item_h
                    return w, h
                lw = getattr(item, '_layout_w', 0)
                lh = getattr(item, '_layout_h', 0)
                return (lw if lw > 0 else self._item_w), (lh if lh > 0 else self._item_h)
            else:
                return self._item_w, self._item_h
        return self._item_w, self._item_h

    # ── Shadow ────────────────────────────────────────────────

    def _init_pill_shadow(self, base: dict):
        shadow_css = base.get("box-shadow", "")
        if not shadow_css:
            return
        from .shadow import parse_box_shadow, _ShadowLayer as _SL
        shadows = parse_box_shadow(shadow_css)
        if not shadows:
            return
        try:    radius = float(base.get("border-radius", min(self._pill_h, self._pill_w) / 2))
        except: radius = self._pill_h / 2
        self._pill_shadow = _SL(
            parent_window=self.parent(),
            btn_w=self._pill_w,
            btn_h=self._pill_h,
            shadows=shadows,
            border_radius=radius,
        )
        self._pill_shadow.hide()

    def _sync_pill_shadow(self):
        if not self._pill_shadow:
            return
        pvx, pvy = self._pivot_in_canvas()
        win_pivot_x = self.x() + pvx
        win_pivot_y = self.y() + pvy
        ox, oy = self._pill_origin()
        s = self._pill_scale
        win_cx = int(win_pivot_x + (ox + self._pill_w / 2 - pvx) * s)
        win_cy = int(win_pivot_y + (oy + self._pill_h / 2 - pvy) * s)
        self._pill_shadow.set_scale(s)
        lw = self._pill_shadow.width()
        lh = self._pill_shadow.height()
        self._pill_shadow.move(win_cx - lw // 2, win_cy - lh // 2)
        self._pill_shadow.setWindowOpacity(self._opacity)

    # ── Qt Properties ─────────────────────────────────────────

    def getPillScale(self):    return self._pill_scale
    def setPillScale(self, v):
        self._pill_scale = max(0.0, v)
        self._sync_button_overlays()
        self._update_mask()
        self._sync_pill_shadow()
        self.update()
    pill_scale = Property(float, getPillScale, setPillScale)

    def _update_mask(self):
        from PySide6.QtGui import QRegion
        if self._pill_scale <= 0.01:
            self.setMask(QRegion())
            return
        tr = self._make_transform()
        ox, oy = self._pill_origin()
        corners = [
            tr.map(QPointF(ox,                 oy)),
            tr.map(QPointF(ox + self._pill_w,  oy)),
            tr.map(QPointF(ox + self._pill_w,  oy + self._pill_h)),
            tr.map(QPointF(ox,                 oy + self._pill_h)),
        ]
        xs = [p.x() for p in corners]
        ys = [p.y() for p in corners]
        mask_rect = QRect(
            int(min(xs)) - 4, int(min(ys)) - 4,
            int(max(xs) - min(xs)) + 8, int(max(ys) - min(ys)) + 8
        )
        self.setMask(QRegion(mask_rect))

    def getPillOpacity(self):    return self._opacity
    def setPillOpacity(self, v):
        self._opacity = max(0.0, min(1.0, v))
        # Set opacity untuk button overlays juga
        for item in self.items:
            if isinstance(item, RennsButton) and item.overlay:
                item.overlay.setWindowOpacity(self._opacity)
        self._sync_pill_shadow()
        self.update()
    pill_opacity = Property(float, getPillOpacity, setPillOpacity)

    # ── Slot colors ───────────────────────────────────────────

    def _rebuild_slot_colors(self):
        self._slot_colors.clear()
        self._slot_borders.clear()
        self._slot_scales.clear()
        b = RennsStyle.get(self.class_name, "base")
        self._slot_colors.append(_SlotColor(parse_css_color(b.get("background", "#2d2f3a")), self.update))
        self._slot_borders.append(_SlotBorder(parse_css_color(b.get("border-color", "#00000000")), self.update))
        self._slot_scales.append(_SlotScale(1.0, self.update))
        for item in self.items:
            if isinstance(item, dict):
                ib = RennsStyle.get(item.get("class", self.class_name), "base")
                self._slot_colors.append(_SlotColor(parse_css_color(ib.get("background", "#3b3f52")), self.update))
                self._slot_borders.append(_SlotBorder(parse_css_color(ib.get("border-color", "#00000000")), self.update))
                self._slot_scales.append(_SlotScale(1.0, self.update))
            else:
                self._slot_colors.append(None)
                self._slot_borders.append(None)
                self._slot_scales.append(None)

    def _color_slot(self, idx: int, state: str):
        if idx >= len(self._slot_colors): return
        sc = self._slot_colors[idx]
        if sc is None: return
        cname  = self.class_name if idx == 0 else self.items[idx-1].get("class", self.class_name)
        base   = RennsStyle.get(cname, "base")
        props  = RennsStyle.get(cname, state)
        merged = {**base, **props}
        dur_s, eas = RennsStyle.parse_transition(base.get("transition", "0.18s ease-out"))
        dur_ms = int(dur_s * 1000)
        curve  = resolve_easing(eas)
        sc.go(parse_css_color(merged.get("background", "#3b3f52")), dur_ms, curve)
        sb = self._slot_borders[idx] if idx < len(self._slot_borders) else None
        if sb:
            sb.go(parse_css_color(merged.get("border-color", "#00000000")), dur_ms, curve)
        ss = self._slot_scales[idx] if idx < len(self._slot_scales) else None
        if ss:
            target_sc, _ = parse_transform(merged.get("transform", ""))
            ss.go(target_sc, dur_ms, curve)

    # ── Geometry ──────────────────────────────────────────────

    def _pill_origin(self):
        return self._margin, self._margin

    def _pivot_in_canvas(self):
        ox, oy = self._pill_origin()
        pw, ph = self._pill_w, self._pill_h
        if self.direction == "horizontal":
            if self.anchor == "right":
                return ox + pw - self._pad - self._trig_w / 2, oy + ph / 2
            elif self.anchor == "center":
                # Center pill di-align ke center trigger
                # Trigger kiri, items kanan — pill center = trigger center
                return ox + pw / 2, oy + ph / 2
            else:  # left
                return ox + self._pad + self._trig_w / 2, oy + ph / 2
        else:
            if self.anchor == "bottom":
                return ox + pw / 2, oy + ph - self._pad - self._trig_h / 2
            elif self.anchor == "center":
                return ox + pw / 2, oy + ph / 2
            else:  # top
                return ox + pw / 2, oy + self._pad + self._trig_h / 2

    def sync_position(self):
        pvx, pvy = self._pivot_in_canvas()
        tc = self._trigger_ref.mapTo(
            self.window(), self._trigger_ref.rect().center()
        )
        self.move(int(tc.x() - pvx), int(tc.y() - pvy))
        self._sync_button_overlays()
        self._sync_pill_shadow()

    def _make_transform(self) -> QTransform:
        pvx, pvy = self._pivot_in_canvas()
        s = self._pill_scale
        t = QTransform()
        t.translate(pvx, pvy)
        t.scale(s, s)
        t.translate(-pvx, -pvy)
        return t

    # ── Slot rects (dalam canvas coords, pre-transform) ───────

    def _slot_rects(self) -> list:
        ox, oy = self._pill_origin()
        pad = self._pad
        n   = len(self.items)
        rects = [None] * (n + 1)

        if self.direction == "horizontal":
            sh = self._trig_h
            if self.anchor == "right":
                tx = ox + self._pill_w - pad - self._trig_w
                rects[0] = QRectF(tx, oy + pad, self._trig_w, sh)
                for i in range(n):
                    x = tx - (n - i) * (self._item_w + self._gap)
                    rects[i+1] = QRectF(x, oy + pad, self._item_w, sh)
            else:  # left / center — trigger kiri, items ke kanan
                tx = ox + pad
                rects[0] = QRectF(tx, oy + pad, self._trig_w, sh)
                for i in range(n):
                    x = tx + self._trig_w + self._gap + i * (self._item_w + self._gap)
                    rects[i+1] = QRectF(x, oy + pad, self._item_w, sh)
        else:
            cw = self._pill_w - pad * 2
            if self.anchor == "bottom":
                ty = oy + self._pill_h - pad - self._trig_h
                rects[0] = QRectF(ox + pad, ty, cw, self._trig_h)
                for i in range(n):
                    y = ty - (n - i) * (self._item_h + self._gap)
                    rects[i+1] = QRectF(ox + pad, y, cw, self._item_h)
            else:
                ty = oy + pad
                rects[0] = QRectF(ox + pad, ty, cw, self._trig_h)
                for i in range(n):
                    y = ty + self._trig_h + self._gap + i * (self._item_h + self._gap)
                    rects[i+1] = QRectF(ox + pad, y, cw, self._item_h)
        return rects

    # ── Sync button overlays ke posisi slot ──────────────────

    def _sync_button_overlays_final(self):
        """Sync posisi item ke posisi FINAL pill (scale=1.0). Tidak ikut-ikutan scale pill."""
        if not self.isVisible():
            return
        slots = self._slot_rects()
        for i, item in enumerate(self.items):
            if not isinstance(item, RennsButton) or not item.overlay:
                continue
            slot_idx = i + 1
            if slot_idx >= len(slots) or slots[slot_idx] is None:
                continue
            r = slots[slot_idx]
            # Tidak pakai _make_transform() — langsung pakai center slot (scale=1.0)
            win_cx = int(self.x() + r.center().x())
            win_cy = int(self.y() + r.center().y())
            ov = item.overlay
            ov.move(win_cx - ov.width() // 2, win_cy - ov.height() // 2)
            bw = item._layout_w if item._layout_w > 0 else (ov._btn_w if ov._btn_w > 0 else item.width())
            bh = item._layout_h if item._layout_h > 0 else (ov._btn_h if ov._btn_h > 0 else item.height())
            item.move(win_cx - self.x() - bw // 2, win_cy - self.y() - bh // 2)

    def _sync_button_overlays(self):
        """
        Posisikan overlay RennsButton ke koordinat window sesuai slot rect
        setelah pill transform. _btn_w/_btn_h TIDAK diubah (tetap ukuran CSS penuh)
        supaya animasi hover/active button tetap smooth.
        Yang berubah hanya: posisi overlay (move) dan opacity (via pill opacity).
        Skip saat _entry_animating agar item tidak goyang ngikutin pill scale.
        """
        if not self.isVisible():
            return
        if getattr(self, '_entry_animating', False):
            return

        slots = self._slot_rects()
        tr    = self._make_transform()

        for i, item in enumerate(self.items):
            if not isinstance(item, RennsButton) or not item.overlay:
                continue

            slot_idx = i + 1
            if slot_idx >= len(slots) or slots[slot_idx] is None:
                continue

            r = slots[slot_idx]

            # Center slot di canvas pre-transform → map ke window coords
            mapped_c = tr.map(r.center())
            win_cx   = int(self.x() + mapped_c.x())
            win_cy   = int(self.y() + mapped_c.y())

            ov = item.overlay

            # JANGAN ubah _btn_w/_btn_h dan resize — itu yang bikin hover kasar
            # Overlay sudah punya ukuran penuh dari CSS saat setClass() dipanggil
            # Cukup pindahkan center overlay ke posisi slot yang sudah di-transform
            ov.move(
                win_cx - ov.width()  // 2,
                win_cy - ov.height() // 2,
            )

            # Item child of pill → koordinat relatif pill, bukan window
            bw = item._layout_w if item._layout_w > 0 else (ov._btn_w if ov._btn_w > 0 else item.width())
            bh = item._layout_h if item._layout_h > 0 else (ov._btn_h if ov._btn_h > 0 else item.height())
            item.move(win_cx - self.x() - bw // 2, win_cy - self.y() - bh // 2)

    # ── Hit test ──────────────────────────────────────────────

    def _hit_slot(self, widget_pos: QPointF) -> int:
        tr = self._make_transform()
        inv, ok = tr.inverted()
        if not ok: return -1
        p = inv.map(widget_pos)
        for i, r in enumerate(self._slot_rects()):
            if r is not None and r.contains(p):
                # Kalau RennsButton — tidak handle di sini (mouse events ke button-nya)
                if i > 0 and isinstance(self.items[i-1], RennsButton):
                    continue
                return i
        return -1

    # ── Paint ─────────────────────────────────────────────────

    def paintEvent(self, event):
        if self._opacity <= 0.0:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)
        painter.setOpacity(self._opacity)

        ox, oy = self._pill_origin()
        pw, ph = self._pill_w, self._pill_h
        slots  = self._slot_rects()

        # ── Pill background ───────────────────────────────────
        base     = RennsStyle.get(self.class_name, "base")
        pill_bg  = parse_css_color(base.get("background", "#2d2f3a"))
        raw_r    = float(base.get("border-radius", min(ph, pw) / 2))
        pill_rad = min(raw_r, ph / 2, pw / 2)
        pill_rect = QRectF(ox, oy, pw, ph)

        border_color = base.get("border-color", None)
        try:    border_width = float(base.get("border-width", 0))
        except: border_width = 0

        # ── Backdrop blur — pakai pill transform supaya ikut scale animasi ──
        _backdrop_css = base.get("backdrop-filter", "")
        if _backdrop_css:
            draw_backdrop_blur(painter, self, pill_rect.toRect(), pill_rad,
                               _backdrop_css, transform=self._make_transform())

        # Transform untuk animasi scale/expand pill
        painter.setTransform(self._make_transform())

        painter.setBrush(QBrush(pill_bg))
        if border_color and border_width > 0:
            from PySide6.QtGui import QPen
            pen = QPen(parse_css_color(border_color))
            pen.setWidthF(border_width)
            painter.setPen(pen)
        else:
            painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(pill_rect, pill_rad, pill_rad)
        painter.setClipRect(pill_rect.toAlignedRect())

        # ── Tiap slot ─────────────────────────────────────────
        for idx, rect in enumerate(slots):
            if rect is None: continue

            is_trig = (idx == 0)
            item    = None if is_trig else self.items[idx-1]

            # RennsButton: gambarin slot background transparan aja
            # (button overlay yang gambar kontennya)
            if not is_trig and isinstance(item, RennsButton):
                # Tidak gambar apa-apa — button overlay sudah handle sendiri
                continue

            cname   = self.class_name if is_trig else item.get("class", self.class_name)
            text    = self._trig_label() if is_trig else item.get("text", "")
            sc      = self._slot_colors[idx]
            sb      = self._slot_borders[idx] if idx < len(self._slot_borders) else None
            ss      = self._slot_scales[idx] if idx < len(self._slot_scales) else None
            bg_c    = sc.color if sc else QColor("#3b3f52")
            bdr_c   = sb.color if sb else None
            anim_sc = ss.scale if ss else 1.0
            hov     = (self._hovered_idx == idx)
            prs     = (self._pressed_idx == idx)
            self._draw_slot(painter, rect, cname, text, bg_c, bdr_c, anim_sc, hov, prs)

        painter.setClipping(False)

    def _draw_slot(self, painter, rect: QRectF, class_name: str,
                   text: str, bg_color: QColor, animated_border,
                   anim_scale: float, hovered: bool, pressed: bool):
        state  = "active" if pressed else "hover" if hovered else "base"
        base   = RennsStyle.get(class_name, "base")
        props  = RennsStyle.get(class_name, state)
        merged = {**base, **props}

        fg     = merged.get("color", "#ffffff")
        radius = float(merged.get("border-radius", 10))
        fs     = int(float(merged.get("font-size", 13)))
        fw     = merged.get("font-weight", "normal").strip().lower()
        painter.save()
        if abs(anim_scale - 1.0) > 0.001:
            cx, cy = rect.center().x(), rect.center().y()
            st = QTransform()
            st.translate(cx, cy); st.scale(anim_scale, anim_scale); st.translate(-cx, -cy)
            painter.setTransform(st, True)

        try:    border_width = float(merged.get("border-width", 0))
        except: border_width = 0

        painter.setBrush(QBrush(bg_color))
        if animated_border and border_width > 0 and animated_border.alpha() > 0:
            from PySide6.QtGui import QPen
            pen = QPen(animated_border)
            pen.setWidthF(border_width)
            painter.setPen(pen)
        else:
            painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(rect, radius, radius)

        if text:
            r_int  = rect.toAlignedRect()
            pm_w   = max(1, r_int.width())
            pm_h   = max(1, r_int.height())
            pm = self._get_slot_text_pm(text, fg, fs, fw, pm_w, pm_h)
            painter.setRenderHint(QPainter.SmoothPixmapTransform)
            painter.drawPixmap(r_int, pm, QRect(0, 0, pm_w, pm_h))
        painter.restore()

    def _trig_label(self) -> str:
        t = self._trigger_ref.trigger_text()
        return t if t else "×"

    def _get_slot_text_pm(self, text: str, color_str: str, font_size: int,
                          font_weight: str, pm_w: int, pm_h: int):
        """Cache text pixmap persis seperti RennsOverlay._get_text_pixmap."""
        key = (text, font_size, color_str, font_weight, pm_w, pm_h)
        if key in self._text_pm_cache:
            return self._text_pm_cache[key]

        font = QFont()
        font.setPixelSize(max(1, font_size))
        font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
        fw = font_weight.strip().lower()
        if   fw == "bold":      font.setBold(True)
        elif fw == "medium":    font.setWeight(QFont.Weight.Medium)
        elif fw == "semibold":  font.setWeight(QFont.Weight.DemiBold)
        elif fw == "thin":      font.setWeight(QFont.Weight.Thin)
        elif fw == "light":     font.setWeight(QFont.Weight.Light)

        from PySide6.QtGui import QPixmap
        dpr = self.devicePixelRatioF()
        pm  = QPixmap(int(pm_w * dpr), int(pm_h * dpr))
        pm.setDevicePixelRatio(dpr)
        pm.fill(Qt.transparent)

        p = QPainter(pm)
        p.setRenderHint(QPainter.TextAntialiasing)
        p.setFont(font)
        p.setPen(QColor(color_str))
        p.drawText(QRect(0, 0, pm_w, pm_h), Qt.AlignCenter, text)
        p.end()

        # Batasi cache supaya tidak bocor memori
        if len(self._text_pm_cache) > 64:
            self._text_pm_cache.pop(next(iter(self._text_pm_cache)))
        self._text_pm_cache[key] = pm
        return pm

    # ── Mouse (hanya untuk dict slots + trigger) ──────────────

    def _is_over_button_item(self, widget_pos: QPointF) -> bool:
        """Cek apakah posisi mouse berada di atas salah satu RennsButton item."""
        tr = self._make_transform()
        inv, ok = tr.inverted()
        if not ok: return False
        p = inv.map(widget_pos)
        slots = self._slot_rects()
        for i, item in enumerate(self.items):
            if not isinstance(item, RennsButton): continue
            slot_idx = i + 1
            if slot_idx < len(slots) and slots[slot_idx] and slots[slot_idx].contains(p):
                return True
        return False

    def mouseMoveEvent(self, event):
        idx = self._hit_slot(event.position())
        if idx != self._hovered_idx:
            old = self._hovered_idx
            self._hovered_idx = idx
            if old >= 0: self._color_slot(old, "active" if self._pressed_idx == old else "base")
            if idx >= 0: self._color_slot(idx, "hover")
            self.update()
        self.setCursor(QCursor(Qt.PointingHandCursor if idx >= 0 else Qt.ArrowCursor))

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton: return
        idx = self._hit_slot(event.position())
        if idx >= 0:
            old = self._pressed_idx
            self._pressed_idx = idx
            if old >= 0: self._color_slot(old, "hover" if self._hovered_idx == old else "base")
            self._color_slot(idx, "active")
            self.update()
            event.accept()
        else:
            event.ignore()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.LeftButton: return
        idx   = self._hit_slot(event.position())
        fired = (idx >= 0 and idx == self._pressed_idx)
        if self._pressed_idx >= 0:
            self._color_slot(self._pressed_idx,
                             "hover" if self._hovered_idx == self._pressed_idx else "base")
        self._pressed_idx = -1
        if fired:
            if idx == 0: self.close_requested.emit()
            else:        self.item_clicked.emit(idx - 1)
        self.update()
        if idx >= 0:
            event.accept()
        else:
            event.ignore()

    def leaveEvent(self, event):
        if self._hovered_idx >= 0: self._color_slot(self._hovered_idx, "base")
        if self._pressed_idx  >= 0: self._color_slot(self._pressed_idx,  "base")
        self._hovered_idx = -1
        self._pressed_idx = -1
        self.update()

    # ── Show / hide button items ───────────────────────────────

    def _show_button_items(self):
        """
        Show button items: tiap item animate dari posisi TRIGGER → posisi FINAL,
        sambil scale overlay 0→1. Stagger antar item.
        """
        self._entry_animating = True
        if not hasattr(self, '_entry_anims'):
            self._entry_anims = []

        n_btn      = sum(1 for it in self.items if isinstance(it, RennsButton))
        stagger_ms = min(50, self._dur_ms // max(n_btn * 2, 1))
        entry_dur  = int(self._dur_ms * 0.85)

        # Prepare semua item: invisible, scale 0, parent ke pill
        for item in self.items:
            if not isinstance(item, RennsButton):
                continue
            if item.parent() is not self:
                item.setParent(self)
            bw = item._layout_w if item._layout_w > 0 else (
                 item.overlay._btn_w if (item.overlay and item.overlay._btn_w > 0) else 100)
            bh = item._layout_h if item._layout_h > 0 else (
                 item.overlay._btn_h if (item.overlay and item.overlay._btn_h > 0) else 50)
            item.resize(bw, bh)
            item.show()
            if item.overlay:
                ov = item.overlay
                if item._class_name:
                    base = RennsStyle.get(item._class_name, "base", item._component)
                    bg = base.get("background")
                    if bg:
                        ov.color_anim.stop()
                        ov._bg_color = parse_css_color(bg)
                ov.anim.stop()
                ov._scale = 0.0
                ov.setWindowOpacity(0.0)
                ov.show()
                ov.raise_()

        def _deferred_start():
            # Titik START = center trigger di window coords
            trig_center = self._trigger_ref.mapTo(
                self.window(), self._trigger_ref.rect().center()
            )
            trig_win_x = trig_center.x()
            trig_win_y = trig_center.y()

            # Kumpulkan posisi FINAL tiap item (dari slot rect, pill scale=1)
            slots = self._slot_rects()

            self._entry_anims.clear()

            btn_idx = 0
            last_end_ms = 0
            for i, item in enumerate(self.items):
                if not isinstance(item, RennsButton) or not item.overlay:
                    continue

                slot_idx = i + 1
                if slot_idx >= len(slots) or slots[slot_idx] is None:
                    btn_idx += 1
                    continue

                r = slots[slot_idx]
                # Posisi final overlay (window coords)
                final_win_cx = int(self.x() + r.center().x())
                final_win_cy = int(self.y() + r.center().y())

                ov = item.overlay
                ow = ov.width()
                oh = ov.height()

                # Posisi final overlay (top-left)
                final_ox = final_win_cx - ow // 2
                final_oy = final_win_cy - oh // 2

                # Posisi start overlay (center = trigger center)
                start_ox = trig_win_x - ow // 2
                start_oy = trig_win_y - oh // 2

                # Posisi final item widget (relatif pill)
                bw = item._layout_w if item._layout_w > 0 else (ov._btn_w if ov._btn_w > 0 else item.width())
                bh = item._layout_h if item._layout_h > 0 else (ov._btn_h if ov._btn_h > 0 else item.height())
                final_item_x = final_win_cx - self.x() - bw // 2
                final_item_y = final_win_cy - self.y() - bh // 2

                # Taruh di posisi start dulu
                ov.move(start_ox, start_oy)
                item.move(trig_win_x - self.x() - bw // 2, trig_win_y - self.y() - bh // 2)

                delay = btn_idx * stagger_ms
                last_end_ms = delay + entry_dur + 60

                def _launch(
                    overlay=ov, itm=item,
                    sox=start_ox, soy=start_oy,
                    fox=final_ox, foy=final_oy,
                    fix=final_item_x, fiy=final_item_y,
                    bw_=bw, bh_=bh,
                    d=delay, dur=entry_dur
                ):
                    def _go():
                        # ── Animate posisi overlay: start → final ──
                        pos_anim = QPropertyAnimation(overlay, b"pos")
                        pos_anim.setStartValue(QPoint(sox, soy))
                        pos_anim.setEndValue(QPoint(fox, foy))
                        pos_anim.setDuration(dur)
                        pos_anim.setEasingCurve(self._easing)
                        pos_anim.start()
                        overlay._entry_pos_anim = pos_anim  # anti-GC

                        # Gerakkan juga item widget bareng overlay
                        itm_pos_anim = QPropertyAnimation(itm, b"pos")
                        start_item = itm.pos()
                        itm_pos_anim.setStartValue(start_item)
                        itm_pos_anim.setEndValue(QPoint(fix, fiy))
                        itm_pos_anim.setDuration(dur)
                        itm_pos_anim.setEasingCurve(self._easing)
                        itm_pos_anim.start()
                        overlay._entry_item_pos_anim = itm_pos_anim  # anti-GC

                        # ── Scale overlay 0 → 1 ──
                        overlay.anim.stop()
                        overlay.anim.setStartValue(0.0)
                        overlay.anim.setEndValue(1.0)
                        overlay.anim.setDuration(dur)
                        overlay.anim.setEasingCurve(self._easing)
                        overlay.anim.start()

                        # ── Opacity fade in ──
                        op = QPropertyAnimation(overlay, b"windowOpacity")
                        op.setStartValue(0.0)
                        op.setEndValue(1.0)
                        op.setDuration(min(120, dur // 3))
                        op.setEasingCurve(QEasingCurve.OutCubic)
                        op.start()
                        overlay._entry_op_anim = op  # anti-GC

                        self._entry_anims.extend([pos_anim, itm_pos_anim, op])

                    if d > 0:
                        QTimer.singleShot(d, _go)
                    else:
                        _go()

                _launch()
                btn_idx += 1

            def _clear():
                self._entry_animating = False
                self._sync_button_overlays_final()
            QTimer.singleShot(last_end_ms, _clear)

        QTimer.singleShot(0, _deferred_start)

    def _hide_button_items(self):
        # Item adalah child of pill — saat pill.hide() dipanggil nanti, item ikut
        # Overlay di window level harus di-hide manual
        for item in self.items:
            if isinstance(item, RennsButton):
                if item.overlay:
                    item.overlay.hide()

    # ── Expand / Collapse ─────────────────────────────────────

    def expand(self):
        _safe_disconnect(self._opacity_anim.finished)
        _safe_disconnect(self._scale_anim.finished)
        self._rebuild_slot_colors()
        self.sync_position()
        self.show()
        self.raise_()
        self._show_button_items()
        if self._pill_shadow:
            self._pill_shadow.show()
            self._pill_shadow.lower()
            self._sync_pill_shadow()

        _safe_disconnect(self._scale_anim.finished)

        self._scale_anim.stop()
        self._scale_anim.setStartValue(self._pill_scale)
        self._scale_anim.setEndValue(1.0)
        self._scale_anim.start()

        fade_dur = min(120, self._dur_ms // 2)
        self._opacity_anim.stop()
        self._opacity_anim.setStartValue(self._opacity)
        self._opacity_anim.setEndValue(1.0)
        self._opacity_anim.setDuration(fade_dur)
        self._opacity_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._opacity_anim.start()

    def collapse(self):
        _safe_disconnect(self._scale_anim.finished)
        _safe_disconnect(self._opacity_anim.finished)
        self._entry_animating = False  # batalkan entry mode kalau collapse duluan

        # Reset windowOpacity item overlays supaya tidak stuck di 0
        for item in self.items:
            if isinstance(item, RennsButton) and item.overlay:
                item.overlay.setWindowOpacity(1.0)

        self._scale_anim.stop()
        self._scale_anim.setStartValue(self._pill_scale)
        self._scale_anim.setEndValue(0.0)
        self._scale_anim.start()

        fade_dur = min(100, self._dur_ms // 3)
        self._opacity_anim.stop()
        self._opacity_anim.setEasingCurve(QEasingCurve.InCubic)
        self._opacity_anim.setStartValue(self._opacity)
        self._opacity_anim.setEndValue(0.0)
        self._opacity_anim.setDuration(fade_dur)
        self._opacity_anim.start()

        # Scale overlay RennsButton items ke 0 bareng animasi pill
        for item in self.items:
            if isinstance(item, RennsButton) and item.overlay:
                ov = item.overlay
                ov.anim.stop()
                ov.anim.setStartValue(ov.scale)
                ov.anim.setEndValue(0.0)
                ov.anim.setDuration(self._dur_ms)
                ov.anim.setEasingCurve(self._easing)
                ov.anim.start()

        def _on_fade_done():
            _safe_disconnect(self._opacity_anim.finished)
            self._hide_button_items()
            for item in self.items:
                if isinstance(item, RennsButton) and item.overlay:
                    item.overlay._scale = 1.0
            if self._pill_shadow:
                self._pill_shadow.hide()

        self._opacity_anim.finished.connect(_on_fade_done)


# ─────────────────────────────────────────────────────────────
#  RennsActionGroup — placeholder di layout
# ─────────────────────────────────────────────────────────────

class RennsActionGroup(QWidget):

    expanded = Signal(bool)

    def __init__(self, class_name: str, trigger: RennsButton,
                 items: list, parent=None):
        super().__init__(parent)

        self._class_name  = class_name
        self._trigger_btn = trigger
        self._items       = items
        self._is_open     = False
        self._pill        = None

        base = RennsStyle.get(class_name, "base")
        def _i(k, d):
            try:    return int(float(base.get(k, d)))
            except: return d

        trig_w          = _i("width",  56)
        trig_h          = _i("height", 56)
        self._direction  = base.get("action-direction", "horizontal").strip().lower()
        self._anchor     = base.get("action-anchor",    "left").strip().lower()

        self._trigger_btn.setParent(self)
        self._trigger_btn.resize(trig_w, trig_h)
        self._trigger_btn.move(0, 0)
        self._trigger_btn.clicked.connect(self._on_trigger_click)
        self.setFixedSize(trig_w, trig_h)

    def trigger_text(self) -> str:
        return self._trigger_btn.text() or ""

    # ── Lifecycle ─────────────────────────────────────────────

    def showEvent(self, event):
        super().showEvent(event)
        if self._pill is None:
            self._pill = _PillOverlay(
                parent_window=self.window(),
                trigger_ref=self,
                items=self._items,
                class_name=self._class_name,
                direction=self._direction,
                anchor=self._anchor,
            )
            self._pill.close_requested.connect(self._close)
            self._pill.item_clicked.connect(self._on_item_click)
            self.window().installEventFilter(self)

        if self._trigger_btn.overlay:
            self._trigger_btn.overlay.show()
        QTimer.singleShot(0, self._trigger_btn._sync_overlay_position)

    def eventFilter(self, obj, event):
        if obj is self.window():
            if event.type() in (QEvent.Resize, QEvent.Move):
                if self._pill: self._pill.sync_position()
                if self._trigger_btn.overlay:
                    self._trigger_btn._sync_overlay_position()
        return False

    def moveEvent(self, event):
        super().moveEvent(event)
        if self._trigger_btn.overlay:
            self._trigger_btn._sync_overlay_position()
        if self._pill: self._pill.sync_position()

    # ── Toggle ────────────────────────────────────────────────

    def _on_trigger_click(self):
        if self._is_open: self._close()
        else:             self._open()

    def _open(self):
        if self._is_open or not self._pill: return
        self._is_open = True
        self._pill.expand()

        ov = self._trigger_btn.overlay
        if ov:
            _safe_disconnect(ov.anim.finished)
            ov.anim.stop()
            ov.anim.setStartValue(ov.scale)
            ov.anim.setEndValue(0.0)
            ov.anim.setDuration(self._pill._dur_ms)
            ov.anim.setEasingCurve(self._pill._easing)
            def _hide_trig():
                _safe_disconnect(ov.anim.finished)
                ov.hide()
            ov.anim.finished.connect(_hide_trig)
            ov.anim.start()

        self.expanded.emit(True)

    def _close(self):
        if not self._is_open or not self._pill: return
        self._is_open = False
        self._pill.collapse()

        ov = self._trigger_btn.overlay
        if ov:
            _safe_disconnect(ov.anim.finished)
            ov._scale = 0.0
            ov.show()
            self._trigger_btn._sync_overlay_position()
            ov.anim.stop()
            ov.anim.setStartValue(0.0)
            ov.anim.setEndValue(1.0)
            ov.anim.setDuration(self._pill._dur_ms)
            ov.anim.setEasingCurve(self._pill._easing)
            ov.anim.start()

        # Hide via scale_anim.finished — scale berlangsung selama _dur_ms penuh
        # Lebih reliable dari opacity (opacity cuma ~100ms, bisa miss connect window)
        def _hide_pill():
            _safe_disconnect(self._pill._scale_anim.finished)
            self._pill.hide()
        _safe_disconnect(self._pill._scale_anim.finished)
        self._pill._scale_anim.finished.connect(_hide_pill)

        self.expanded.emit(False)

    def _on_item_click(self, index: int):
        item = self._items[index]
        if isinstance(item, dict):
            cb = item.get("on_click")
            if cb: cb()
        # Untuk RennsButton, on_click sudah connect saat Renns.object() dibuat
        self._close()