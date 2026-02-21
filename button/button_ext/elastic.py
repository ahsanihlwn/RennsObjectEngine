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


def reset_elastic(overlay, duration_ms=400):
    """Snapback ke center dengan spring."""
    from PySide6.QtCore import QPropertyAnimation, QEasingCurve

    anim_x = QPropertyAnimation(overlay, b"elastic_offset_x")
    anim_x.setDuration(duration_ms)
    anim_x.setStartValue(overlay._elastic_offset_x)
    anim_x.setEndValue(0.0)
    anim_x.setEasingCurve(QEasingCurve.OutElastic)
    anim_x.start()
    overlay._snapback_x = anim_x

    anim_y = QPropertyAnimation(overlay, b"elastic_offset_y")
    anim_y.setDuration(duration_ms)
    anim_y.setStartValue(overlay._elastic_offset_y)
    anim_y.setEndValue(0.0)
    anim_y.setEasingCurve(QEasingCurve.OutElastic)
    anim_y.start()
    overlay._snapback_y = anim_y

    anim_f = QPropertyAnimation(overlay, b"elastic_flatten_prop")
    anim_f.setDuration(int(duration_ms * 0.5))
    anim_f.setStartValue(overlay._elastic_flatten)
    anim_f.setEndValue(0.0)
    anim_f.setEasingCurve(QEasingCurve.OutCubic)
    anim_f.start()
    overlay._snapback_f = anim_f