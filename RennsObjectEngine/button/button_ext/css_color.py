# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Author: @ahsanihlwn
# Copyright (c) 2026 @ahsanihlwn

"""
css_color.py — parse CSS color string ke QColor dengan benar.

QColor(string) hanya support: #RRGGBB, #AARRGGBB, named colors.
TIDAK support: rgba(r,g,b,0.55) dengan alpha float 0-1.

Pakai parse_css_color() sebagai pengganti QColor(css_string).
"""

import re
from PySide6.QtGui import QColor

# ─── CSS named color shortcuts ────────────────────────────────────────────────
# Format: name → (r, g, b)  — semua opaque kecuali transparent
_NAMED: dict = {
    # basics
    "white":       (255, 255, 255),
    "black":       (0,   0,   0),
    "red":         (255, 59,  48),   # iOS-style red
    "blue":        (10,  132, 255),  # iOS-style blue
    "green":       (52,  199, 89),   # iOS-style green
    "cyan":        (90,  200, 250),  # iOS-style cyan
    "orange":      (255, 149, 0),    # iOS-style orange
    "brown":       (162, 132, 94),   # iOS-style brown
    "yellow":      (255, 214, 10),   # iOS-style yellow
    "yelow":       (255, 214, 10),   # typo alias
    "pink":        (255, 45,  85),   # iOS-style pink
    "purple":      (175, 82,  222),  # iOS-style purple
    "gray":        (142, 142, 147),  # iOS-style gray
    "grey":        (142, 142, 147),
    "transparent": (0,   0,   0,   0),  # special: tuple of 4
    # extras yang sering dipakai
    "indigo":      (88,  86,  214),
    "teal":        (48,  209, 191),
    "mint":        (99,  230, 190),
    "lavender":    (204, 204, 255),
    "cream":       (255, 253, 240),
    "navy":        (0,   0,   128),
    "maroon":      (128, 0,   0),
    "olive":       (128, 128, 0),
    "lime":        (0,   255, 0),
    "magenta":     (255, 0,   255),
    "violet":      (143, 0,   255),
    "gold":        (255, 200, 0),
    "silver":      (192, 192, 192),
}


def parse_css_color(value: str) -> QColor:
    """
    Parse CSS color string ke QColor dengan benar.
    Support:
        rgba(45, 47, 58, 0.55)   ← alpha float 0.0-1.0
        rgb(45, 47, 58)
        #2d2f3a
        #2d2f3a80                ← hex dengan alpha
        white, black, red, ...   ← named shortcuts
        red/50                   ← named color dengan opacity % (0-100)
    """
    if not value:
        return QColor(0, 0, 0, 0)

    value = value.strip()

    # rgba(r, g, b, a) — a adalah 0.0-1.0
    m = re.match(r'rgba\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*([0-9.]+)\s*\)', value)
    if m:
        r = max(0, min(255, int(m.group(1))))
        g = max(0, min(255, int(m.group(2))))
        b = max(0, min(255, int(m.group(3))))
        a = max(0, min(255, int(float(m.group(4)) * 255)))
        return QColor(r, g, b, a)

    # rgb(r, g, b)
    m = re.match(r'rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)', value)
    if m:
        r = max(0, min(255, int(m.group(1))))
        g = max(0, min(255, int(m.group(2))))
        b = max(0, min(255, int(m.group(3))))
        return QColor(r, g, b, 255)

    # named/XX — opacity shortcut, e.g. "red/50", "blue/30"
    m = re.match(r'^([a-zA-Z]+)/(\d+)$', value)
    if m:
        name = m.group(1).lower()
        opacity = max(0, min(100, int(m.group(2))))
        alpha = int(opacity / 100 * 255)
        if name in _NAMED:
            t = _NAMED[name]
            return QColor(t[0], t[1], t[2], alpha)

    # named colors (lowercased lookup)
    lower = value.lower()
    if lower in _NAMED:
        t = _NAMED[lower]
        if len(t) == 4:
            return QColor(t[0], t[1], t[2], t[3])
        return QColor(t[0], t[1], t[2], 255)

    # Fallback: hex, Qt built-in named colors
    c = QColor(value)
    return c if c.isValid() else QColor(0, 0, 0, 0)