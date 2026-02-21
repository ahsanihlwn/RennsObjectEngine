# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/. 
# 
# Author: @ahsanihlwn
# Copyright (c) 2026 @ahsanihlwn

from PySide6.QtCore import QEasingCurve, QPointF

def resolve_easing(name: str) -> QEasingCurve:
    if name == "linear":
        return QEasingCurve(QEasingCurve.Linear)

    elif name == "ease":
        return QEasingCurve(QEasingCurve.InOutCubic)

    elif name == "ease-in":
        return QEasingCurve(QEasingCurve.InCubic)

    elif name == "ease-out":
        return QEasingCurve(QEasingCurve.OutCubic)

    elif name == "ease-in-out":
        return QEasingCurve(QEasingCurve.InOutCubic)

    elif name == "bounce":
        curve = QEasingCurve(QEasingCurve.BezierSpline)
        curve.addCubicBezierSegment(
            QPointF(0.175, 0.885),
            QPointF(0.32, 1.275),
            QPointF(1.0, 1.0)
        )
        return curve

    elif name == "spring":
        curve = QEasingCurve(QEasingCurve.OutElastic)
        curve.setAmplitude(1.0)
        curve.setPeriod(0.4)
        return curve

    return QEasingCurve(QEasingCurve.InOutCubic)
