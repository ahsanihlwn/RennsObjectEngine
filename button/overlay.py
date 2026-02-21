# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/. 
# 
# Author: @ahsanihlwn
# Copyright (c) 2026 @ahsanihlwn

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import QPropertyAnimation, QEasingCurve, Property, Qt, QRect
from PySide6.QtGui import QPainter, QColor, QPixmap, QFont, QTransform
from .button_ext.render_button import render_rect

OVERLAY_MULTIPLIER = 5
OVERLAY_CANVAS_FACTOR = OVERLAY_MULTIPLIER


class RennsOverlay(QWidget):
    def __init__(self, parent, icon):
        super().__init__(parent)

        self.icon = icon
        self.render_mode = "icon"
        self.style_data = {}
        self.button_ref = None

        self._btn_w = 0
        self._btn_h = 0

        self._scale = 1.0
        self._transform_rotate = 0.0

        # Elastic offset+flatten (dipakai elastic.py versi tanh)
        self._elastic_offset_x = 0.0
        self._elastic_offset_y = 0.0
        self._elastic_flatten  = 0.0
        self._elastic_vec_x    = 0.0
        self._elastic_vec_y    = 0.0

        self._bg_color = QColor(0, 0, 0, 0)

        # Font size
        self._font_size = 13.0
        self._text_pm = None
        self._text_pm_key = None

        self.color_anim = QPropertyAnimation(self, b"bgColor")
        self.color_anim.setEasingCurve(QEasingCurve.OutCubic)

        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.anim = QPropertyAnimation(self, b"scale")
        self.anim.setEasingCurve(QEasingCurve.OutCubic)
        self.rotate_anim = QPropertyAnimation(self, b"rotate")
        self.rotate_anim.setEasingCurve(QEasingCurve.OutCubic)

    # ------------------------------------------------------------------
    # Qt Properties
    # ------------------------------------------------------------------

    def getBgColor(self): return self._bg_color
    def setBgColor(self, c): self._bg_color = c; self.update()
    bgColor = Property(QColor, getBgColor, setBgColor)

    def getScale(self): return self._scale
    def setScale(self, v): self._scale = v; self.update()
    scale = Property(float, getScale, setScale)

    def getRotate(self): return self._transform_rotate
    def setRotate(self, v): self._transform_rotate = v; self.update()
    rotate = Property(float, getRotate, setRotate)

    # Tiga Qt Properties untuk QPropertyAnimation di reset_elastic
    def getElasticOffsetX(self): return self._elastic_offset_x
    def setElasticOffsetX(self, v): self._elastic_offset_x = v; self.update()
    elastic_offset_x = Property(float, getElasticOffsetX, setElasticOffsetX)

    def getElasticOffsetY(self): return self._elastic_offset_y
    def setElasticOffsetY(self, v): self._elastic_offset_y = v; self.update()
    elastic_offset_y = Property(float, getElasticOffsetY, setElasticOffsetY)

    def getElasticFlatten(self): return self._elastic_flatten
    def setElasticFlatten(self, v): self._elastic_flatten = v; self.update()
    elastic_flatten_prop = Property(float, getElasticFlatten, setElasticFlatten)

    # ------------------------------------------------------------------
    # Font size
    # ------------------------------------------------------------------

    def set_font_size(self, size: float):
        size = max(1.0, float(size))
        if size != self._font_size:
            self._font_size = size
            self._text_pm = None
            self.update()

    # ------------------------------------------------------------------
    # Text pixmap cache
    # ------------------------------------------------------------------

    def _get_text_pixmap(self, text, color_str, pm_w, pm_h):
        font_size_int = max(1, int(self._font_size))
        weight_str = self.style_data.get("font-weight", "normal").strip().lower()
        family = self.style_data.get("font-family", "")
        key = (text, font_size_int, color_str, weight_str, family, pm_w, pm_h)

        if self._text_pm is not None and self._text_pm_key == key:
            return self._text_pm

        font = QFont()
        if family:
            font.setFamily(family.strip())
        font.setPixelSize(font_size_int)
        font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)

        if   weight_str == "bold":      font.setBold(True)
        elif weight_str == "thin":      font.setWeight(QFont.Weight.Thin)
        elif weight_str == "light":     font.setWeight(QFont.Weight.Light)
        elif weight_str == "medium":    font.setWeight(QFont.Weight.Medium)
        elif weight_str == "semibold":  font.setWeight(QFont.Weight.DemiBold)
        elif weight_str == "extrabold": font.setWeight(QFont.Weight.ExtraBold)
        elif weight_str == "black":     font.setWeight(QFont.Weight.Black)
        elif weight_str.isdigit():      font.setWeight(int(weight_str))

        dpr = self.devicePixelRatioF()
        pm = QPixmap(int(pm_w * dpr), int(pm_h * dpr))
        pm.setDevicePixelRatio(dpr)
        pm.fill(Qt.transparent)

        p = QPainter(pm)
        p.setRenderHint(QPainter.TextAntialiasing)
        p.setFont(font)
        p.setPen(QColor(color_str))
        p.drawText(QRect(0, 0, pm_w, pm_h), Qt.AlignCenter, text)
        p.end()

        self._text_pm = pm
        self._text_pm_key = key
        return pm

    # ------------------------------------------------------------------
    # Paint
    # ------------------------------------------------------------------

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.setRenderHint(QPainter.TextAntialiasing)

        ow = self.width()
        oh = self.height()

        bw = self._btn_w if self._btn_w > 0 else ow // OVERLAY_MULTIPLIER
        bh = self._btn_h if self._btn_h > 0 else oh // OVERLAY_MULTIPLIER

        cx = ow / 2
        cy = oh / 2

        # Elastic offset: normalized → pixel
        el_px = self._elastic_offset_x * (bw / 2)
        el_py = self._elastic_offset_y * (bh / 2)

        # Flatten matrix: gepeng searah drag (R * diag * R^T)
        flatten = self._elastic_flatten
        vx = self._elastic_vec_x
        vy = self._elastic_vec_y
        perp_scale = 1.0 - flatten * 0.18
        para_scale  = 1.0 + flatten * 0.07

        if flatten > 0.001 and (vx != 0.0 or vy != 0.0):
            m11 = para_scale * vx*vx + perp_scale * vy*vy
            m12 = (para_scale - perp_scale) * vx * vy
            m21 = m12
            m22 = para_scale * vy*vy + perp_scale * vx*vx
            tdx = cx * (1.0 - m11) - cy * m21
            tdy = cy * (1.0 - m22) - cx * m12
            flatten_t = QTransform(m11, m12, m21, m22, tdx, tdy)
        else:
            flatten_t = QTransform()

        # CSS scale + rotate transform, pivot di center overlay
        base_t = QTransform()
        base_t.translate(cx, cy)
        base_t.scale(self._scale, self._scale)
        base_t.rotate(self._transform_rotate)
        base_t.translate(-cx, -cy)

        painter.save()
        painter.setTransform(base_t * flatten_t)

        # Posisi btn_rect dalam overlay berdasarkan align dari style
        # Sintaks sama seperti CSS: "center" | "left" | "right" | "top" | "bottom"
        # Bisa kombinasi: "left top", "right bottom", dll. Default: "center"
        align = self.style_data.get("align", "center").strip().lower()

        if "left" in align:    bx = 0
        elif "right" in align: bx = ow - bw
        else:                  bx = int(cx - bw / 2)

        if "top" in align:      by = 0
        elif "bottom" in align: by = oh - bh
        else:                   by = int(cy - bh / 2)

        btn_rect = QRect(bx, by, bw, bh)
        radius = float(self.style_data.get("border-radius", 12))

        # Background via _bg_color (dikontrol color_anim untuk transisi smooth)
        if self._bg_color.alpha() > 0:
            painter.setBrush(self._bg_color)
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(btn_rect, radius, radius)

        if self.render_mode == "rect":
            # render_rect hanya untuk border — background sudah di-handle _bg_color
            # Jangan timpa _bg_color dengan warna CSS statis dari style_data
            from .button_ext.render_button import render_rect_border_only
            render_rect_border_only(painter, self.style_data, btn_rect)

        # Konten (icon/text) ikut elastic offset
        padding = int(float(self.style_data.get("padding", 0)))
        content_rect = QRect(
            int(bx + padding + el_px),
            int(by + padding + el_py),
            bw - padding * 2,
            bh - padding * 2
        )

        # Icon
        if self.icon:
            obj_size_raw = self.style_data.get("object-size")
            try:
                obj_size = int(float(obj_size_raw)) if obj_size_raw else int(min(bw, bh) * 0.6)
            except:
                obj_size = int(min(bw, bh) * 0.6)
            ix = content_rect.x() + (content_rect.width()  - obj_size) // 2
            iy = content_rect.y() + (content_rect.height() - obj_size) // 2
            self.icon.paint(painter, ix, iy, obj_size, obj_size, Qt.AlignCenter)

        # Text
        text = ""
        if self.button_ref is not None and hasattr(self.button_ref, "text"):
            text = self.button_ref.text() or ""
        if text:
            text_color = self.style_data.get("color", "#ffffff")
            pm_w = max(1, content_rect.width())
            pm_h = max(1, content_rect.height())
            pm = self._get_text_pixmap(text, text_color, pm_w, pm_h)
            painter.drawPixmap(content_rect, pm, QRect(0, 0, pm_w, pm_h))

        painter.restore()