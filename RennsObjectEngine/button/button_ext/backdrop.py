# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Author: @ahsanihlwn
# Copyright (c) 2026 @ahsanihlwn

"""
backdrop.py — pre-baked blur layer system (iOS/macOS style).

Arsitektur:
- Raw texture disimpan per window
- Layer blur di-bake LAZY: pertama kali radius X diminta, baru di-blur dan di-cache
- Saat paint: crop dari cached layer — O(1)

Cara pakai:
    # Di Main.showEvent atau resizeEvent:
    from RennsObjectEngine.button.button_ext.backdrop import set_window_texture
    pm = QPixmap("background.png").scaled(self.size(),
             Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    set_window_texture(self, pm)
"""

import re
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (
    QGraphicsScene, QGraphicsPixmapItem, QGraphicsBlurEffect
)

# { win_id: QPixmap }  — raw texture
_raw: dict = {}

# { win_id: { radius_int: QPixmap } }  — blurred layers, lazy
_layers: dict = {}

_BAKE_RADII = [0, 4, 8, 12, 16, 20, 24, 32, 40, 48]


def _snap_radius(r: float) -> int:
    return min(_BAKE_RADII, key=lambda x: abs(x - r))


def _do_blur(src: QPixmap, radius: int) -> QPixmap:
    """Blur pixmap. Dipanggil lazy saat pertama kali radius diminta."""
    if radius <= 0:
        return src.copy()
    dpr   = src.devicePixelRatio()
    scene = QGraphicsScene()
    item  = QGraphicsPixmapItem(src)
    fx    = QGraphicsBlurEffect()
    fx.setBlurRadius(radius * dpr)
    fx.setBlurHints(QGraphicsBlurEffect.QualityHint)
    item.setGraphicsEffect(fx)
    scene.addItem(item)
    out = QPixmap(src.size())
    out.setDevicePixelRatio(dpr)
    out.fill(Qt.transparent)
    p = QPainter(out)
    scene.render(p)
    p.end()
    return out


def set_window_texture(win, pixmap: QPixmap):
    """
    Simpan raw texture. Layer blur di-bake lazy saat pertama kali dipakai.
    Aman dipanggil dari __init__, showEvent, maupun resizeEvent.
    """
    if not pixmap or pixmap.isNull():
        return
    win_id = id(win)
    _raw[win_id]    = pixmap
    _layers[win_id] = {}          # reset cache blur lama


def invalidate_window(win):
    """Reset hanya blur cache, raw texture tetap ada supaya tidak ngedip."""
    win_id = id(win)
    if win_id in _layers:
        _layers[win_id] = {}   # hapus blur cache saja, raw tetap → tidak ngedip


def parse_backdrop_blur(css: str) -> float:
    m = re.search(r'blur[(]\s*([0-9.]+)', css)
    if m:
        try: return float(m.group(1))
        except: pass
    return 0.0


def draw_backdrop_blur(painter: QPainter, overlay,
                       btn_rect, radius: float, css: str,
                       transform=None):
    """
    Draw blur di btn_rect.
    transform: QTransform lengkap (scale+rotate+elastic+flatten) dari overlay.paintEvent.
    Clip path di-transform dengan benar menggunakan transform.map(path)
    bukan mapRect() yang hanya akurat untuk axis-aligned transform.
    """
    blur_r = parse_backdrop_blur(css)

    win = overlay.window()
    if not win:
        return

    win_id = id(win)
    raw    = _raw.get(win_id)
    if raw is None or raw.isNull():
        return

    snapped = _snap_radius(blur_r)

    if win_id not in _layers:
        _layers[win_id] = {}
    if snapped not in _layers[win_id]:
        _layers[win_id][snapped] = _do_blur(raw, snapped)

    layer = _layers[win_id][snapped]
    if layer.isNull():
        return

    dpr = layer.devicePixelRatio()
    tw  = layer.width()  / dpr
    th  = layer.height() / dpr
    win_w = win.width()
    win_h = win.height()
    sx = (tw / win_w) if win_w > 0 else 1.0
    sy = (th / win_h) if win_h > 0 else 1.0

    # ── Buat pre-transform clip path (rounded rect di canvas coords) ─
    pre_path = QPainterPath()
    pre_path.addRoundedRect(QRectF(btn_rect), radius, radius)

    # ── Transform clip path dengan transform lengkap ─────────────────
    # transform.map(path) akurat untuk shear/flatten, bukan mapRect()
    # mapRect() hanya mengembalikan bounding box → salah untuk flatten/shear
    if transform is not None and not transform.isIdentity():
        clip_path = transform.map(pre_path)
    else:
        clip_path = pre_path

    # ── Crop area dari bounding rect path yang sudah di-transform ────
    bb = clip_path.boundingRect()  # bounding box clip path dalam overlay coords
    win_pos = overlay.mapTo(win, bb.topLeft().toPoint())

    crop_x = int(win_pos.x() * sx * dpr)
    crop_y = int(win_pos.y() * sy * dpr)
    crop_w = max(1, int(bb.width()  * sx * dpr))
    crop_h = max(1, int(bb.height() * sy * dpr))

    cropped = layer.copy(crop_x, crop_y, crop_w, crop_h)
    if cropped.isNull():
        return

    # ── Draw: clip = transformed path, draw di bounding box ─────────
    painter.save()
    painter.setClipPath(clip_path)
    painter.drawPixmap(bb, cropped, QRectF(cropped.rect()))
    painter.restore()