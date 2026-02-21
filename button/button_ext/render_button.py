# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/. 
# 
# Author: @ahsanihlwn
# Copyright (c) 2026 @ahsanihlwn

from PySide6.QtGui import QPainter, QColor, QBrush, QPen
from PySide6.QtCore import Qt, QRect


def render_rect(painter, overlay, style: dict, rect: QRect = None):
    """
    Render rectangular button background + border.
    rect: area yang di-render (default = overlay.rect())
    """
    if rect is None:
        rect = overlay.rect()

    radius = float(style.get("border-radius", 0))
    bg = style.get("background", "#ffffff")
    border_color = style.get("border-color", None)
    border_width = float(style.get("border-width", 0))
    opacity = float(style.get("opacity", 1.0))

    painter.save()
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setOpacity(opacity)

    painter.setBrush(QBrush(QColor(bg)))

    if border_color and border_width > 0:
        pen = QPen(QColor(border_color))
        pen.setWidthF(border_width)
        painter.setPen(pen)
    else:
        painter.setPen(Qt.NoPen)

    painter.drawRoundedRect(rect, radius, radius)
    painter.restore()

def render_rect_border_only(painter, style: dict, rect):
    """
    Hanya render border (kalau ada) — background sudah di-handle oleh overlay._bg_color.
    Dipanggil dari overlay paintEvent untuk mode rect.
    """
    border_color = style.get("border-color", None)
    border_width = float(style.get("border-width", 0))
    opacity      = float(style.get("opacity", 1.0))
    radius       = float(style.get("border-radius", 0))

    if not border_color or border_width <= 0:
        return  # Tidak ada border, tidak perlu gambar apapun

    painter.save()
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setOpacity(opacity)
    painter.setBrush(Qt.NoBrush)
    pen = QPen(QColor(border_color))
    pen.setWidthF(border_width)
    painter.setPen(pen)
    painter.drawRoundedRect(rect, radius, radius)
    painter.restore()