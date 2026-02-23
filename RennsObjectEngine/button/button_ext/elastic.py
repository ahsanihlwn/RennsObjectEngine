# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/. 
# 
# Author: @ahsanihlwn
# Copyright (c) 2026 @ahsanihlwn

import math


def apply_elastic(button, event):
    """
    Efek elastic drag:
    - Object bergerak dalam bounding box button
    - Makin deket tepi, makin berat (asymptotic via tanh)
    - Makin jauh, makin gepeng sesuai ARAH drag (bukan cuma X/Y)
    """
    if button._drag_origin is None:
        button._drag_origin = event.position()

    delta = event.position() - button._drag_origin
    dx = delta.x()
    dy = delta.y()

    distance = math.sqrt(dx * dx + dy * dy)
    if distance == 0:
        button.overlay._elastic_offset_x = 0.0
        button.overlay._elastic_offset_y = 0.0
        button.overlay._elastic_flatten = 0.0
        button.overlay.update()
        return

    vx = dx / distance
    vy = dy / distance

    raw = distance / (button.width() * button._elastic_radius)

    # tanh: smooth asymptote, tidak pernah mencapai 1.0
    mapped = math.tanh(raw * 1.2)

    # Offset max 85% dari setengah button
    offset = mapped * 0.85
    button.overlay._elastic_offset_x = vx * offset
    button.overlay._elastic_offset_y = vy * offset

    # Flatten sesuai vektor arah drag
    button.overlay._elastic_flatten = mapped * 0.8
    button.overlay._elastic_vec_x = vx
    button.overlay._elastic_vec_y = vy

    button.overlay.update()


def reset_elastic(overlay, duration_ms=520):
    """
    Snapback dengan damped flatten oscillation.

    Flatten saat lepas dipakai sebagai peak, lalu oscillate:
      peak → 0 → -(peak/5) → 0 → +(peak/25) → 0 → settle

    Negatif = arah terbalik (gepeng berlawanan) karena overlay.paintEvent
    sudah support flatten negatif (if abs(flatten) > 0.001).

    Posisi offset snapback: spring ringan dengan sedikit overshoot.
    """
    from PySide6.QtCore import QPropertyAnimation, QEasingCurve, QPointF

    # ── Posisi: spring ringan ─────────────────────────────────
    spring = QEasingCurve(QEasingCurve.BezierSpline)
    spring.addCubicBezierSegment(
        QPointF(0.25, 1.06),
        QPointF(0.55, 0.98),
        QPointF(1.00, 1.00)
    )

    anim_x = QPropertyAnimation(overlay, b"elastic_offset_x")
    anim_x.setDuration(duration_ms)
    anim_x.setStartValue(overlay._elastic_offset_x)
    anim_x.setEndValue(0.0)
    anim_x.setEasingCurve(spring)
    anim_x.start()
    overlay._snapback_x = anim_x

    anim_y = QPropertyAnimation(overlay, b"elastic_offset_y")
    anim_y.setDuration(duration_ms)
    anim_y.setStartValue(overlay._elastic_offset_y)
    anim_y.setEndValue(0.0)
    anim_y.setEasingCurve(spring)
    anim_y.start()
    overlay._snapback_y = anim_y

    # ── Flatten: damped oscillation via single BezierSpline ───
    #
    # Qt: output = start + easing(t) * (end - start)
    # start = peak, end = 0  →  output = peak * (1 - easing(t))
    #
    # easing(t) = 0   → output = peak        (gepeng penuh, arah drag)
    # easing(t) = 1   → output = 0           (normal)
    # easing(t) = 1.2 → output = -0.2*peak   (gepeng berlawanan, 1/5 peak)
    # easing(t) = 0.96→ output = +0.04*peak  (gepeng searah, 1/25 peak)
    #
    # Timeline easing:
    #   t=0.00: 0.00  (output = peak)
    #   t=0.35: 1.00  (output = 0, normal)
    #   t=0.50: 1.20  (output = -0.20*peak, gepeng berlawanan)
    #   t=0.62: 1.00  (output = 0)
    #   t=0.72: 0.96  (output = +0.04*peak, gepeng searah kecil)
    #   t=0.80: 1.00
    #   t=1.00: 1.00  (settle)

    flatten_curve = QEasingCurve(QEasingCurve.BezierSpline)
    flatten_curve.addCubicBezierSegment(
        QPointF(0.15, 0.00),
        QPointF(0.28, 1.00),
        QPointF(0.35, 1.00)
    )
    flatten_curve.addCubicBezierSegment(
        QPointF(0.40, 1.00),
        QPointF(0.46, 1.20),
        QPointF(0.50, 1.20)
    )
    flatten_curve.addCubicBezierSegment(
        QPointF(0.54, 1.20),
        QPointF(0.59, 1.00),
        QPointF(0.62, 1.00)
    )
    flatten_curve.addCubicBezierSegment(
        QPointF(0.65, 1.00),
        QPointF(0.69, 0.96),
        QPointF(0.72, 0.96)
    )
    flatten_curve.addCubicBezierSegment(
        QPointF(0.75, 0.96),
        QPointF(0.78, 1.00),
        QPointF(0.80, 1.00)
    )
    flatten_curve.addCubicBezierSegment(
        QPointF(0.88, 1.00),
        QPointF(0.95, 1.00),
        QPointF(1.00, 1.00)
    )

    peak = overlay._elastic_flatten
    anim_f = QPropertyAnimation(overlay, b"elastic_flatten_prop")
    anim_f.setDuration(duration_ms)
    anim_f.setStartValue(peak)
    anim_f.setEndValue(0.0)
    anim_f.setEasingCurve(flatten_curve)
    anim_f.start()
    overlay._snapback_f = anim_f