# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Author: @ahsanihlwn
# Copyright (c) 2026 @ahsanihlwn

"""
glass_border.py — Liquid glass border, Apple style.

Syntax:
    glass-border: 135deg 1.5px;

Implementasi:
  - Border shape = outer path - inner path (ring tipis)
  - Fill ring dengan QConicalGradient putih
  - Tidak pakai QPen gradient (tidak reliable di Qt)
  - Pola opacity: hi → lo → hi → lo, persis cincin kaca Apple
"""

import re

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import (
    QPainter, QPainterPath, QPen,
    QColor, QConicalGradient, QBrush, QRadialGradient
)


def parse_glass_border(value: str):
    deg   = 135.0
    width = 1.0
    m = re.search(r'([+-]?\d+(?:\.\d+)?)\s*deg', value, re.IGNORECASE)
    if m:
        try: deg = float(m.group(1))
        except: pass
    m = re.search(r'([+-]?\d+(?:\.\d+)?)\s*px', value, re.IGNORECASE)
    if m:
        try: width = float(m.group(1))
        except: pass
    return deg, max(0.1, width)


def draw_glass_border(painter: QPainter, rect, radius: float,
                      light_deg: float, border_width: float):
    """
    Gambar glass border sebagai filled ring dengan conical gradient.
    Ring = outer rounded rect - inner rounded rect (shrunk by border_width).
    Fill ring dengan putih, opacity 50→10→50 mengikuti arah cahaya.
    """
    r  = QRectF(rect)
    cx = r.center().x()
    cy = r.center().y()

    max_rc = min(r.width(), r.height()) / 2.0
    rc_out = min(float(radius), max_rc)

    # Inner rect — shrink sesuai border_width
    bw     = border_width
    r_in   = r.adjusted(bw, bw, -bw, -bw)
    rc_in  = max(0.0, rc_out - bw)

    # Outer path
    path_out = QPainterPath()
    path_out.addRoundedRect(r, rc_out, rc_out)

    # Inner path
    path_in = QPainterPath()
    if r_in.width() > 0 and r_in.height() > 0:
        path_in.addRoundedRect(r_in, rc_in, rc_in)

    # Ring = outer - inner
    ring = path_out.subtracted(path_in)

    # Conical gradient — putih semua, opacity 50→10→50
    # CSS 0deg=atas, QConicalGradient 0=kanan CCW → qt_angle = 90 - css_deg
    qt_angle = 90.0 - light_deg

    a_hi = 128   # ~50%
    a_lo = 25    # ~10%

    grad = QConicalGradient(QPointF(cx, cy), qt_angle)
    grad.setColorAt(0.00, QColor(255, 255, 255, a_hi))
    grad.setColorAt(0.25, QColor(255, 255, 255, a_lo))
    grad.setColorAt(0.50, QColor(255, 255, 255, a_hi))
    grad.setColorAt(0.75, QColor(255, 255, 255, a_lo))
    grad.setColorAt(1.00, QColor(255, 255, 255, a_hi))

    painter.save()
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QBrush(grad))
    painter.drawPath(ring)
    painter.restore()