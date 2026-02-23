# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/. 
# 
# Author: @ahsanihlwn
# Copyright (c) 2026 @ahsanihlwn

import re

class RennsStyle:

    styles = {}

    @classmethod
    def load(cls, path):
        cls.styles.clear()

        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        # Strip komentar /* ... */ (CSS-style, bisa multiline)
        content = re.sub(r'/[*].*?[*]/', '', content, flags=re.DOTALL)

        pattern = r"(.*?)\s*\{(.*?)\}"
        matches = re.findall(pattern, content, re.DOTALL)

        for selector, body in matches:
            selector = selector.strip()
            if not selector:
                continue

            # Pisah pseudo-state dulu: ".bool:hover toggle" → head=".bool:hover", component="toggle"
            # tapi ".bool toggle" → head=".bool", component="toggle"
            # Trik: split by spasi setelah handle pseudo-state
            parts = selector.split()

            if len(parts) == 2:
                # Format baru: ".bool toggle" atau ".bool:hover toggle-knob"
                head = parts[0]      # ".bool" atau ".bool:hover"
                component = parts[1] # "toggle" atau "toggle-knob"
            else:
                # Format lama: ".primary" atau ".primary:hover"
                head = parts[0]
                component = None

            # Pisah pseudo-state dari head
            if ":" in head:
                class_part, state = head.split(":", 1)
                state = state.strip()
            else:
                class_part = head
                state = "base"

            # Strip leading dot
            if class_part.startswith("."):
                class_part = class_part[1:]

            # Parse properties
            props = {}
            lines = body.split(";")
            for line in lines:
                line = line.strip()
                if ":" in line:
                    key, value = line.split(":", 1)
                    props[key.strip()] = value.strip()

            # Simpan ke styles dict
            # Struktur: styles[class_name][component or "_"][state] = props
            # "_" = no component (style lama)
            cls.styles.setdefault(class_part, {})
            key = component if component else "_"
            cls.styles[class_part].setdefault(key, {})
            cls.styles[class_part][key][state] = props

    @classmethod
    def get(cls, class_name, state, component=None):
        """
        Ambil style props.
        - component=None  → format lama, key="_"
        - component="toggle" → sub-komponen toggle
        """
        key = component if component else "_"
        return cls.styles.get(class_name, {}).get(key, {}).get(state, {})

    @classmethod
    def parse_transition(cls, value: str):
        parts = value.strip().split()

        duration = 0.25
        easing = "ease"

        for part in parts:
            if part.endswith("s"):
                try:
                    duration = float(part.replace("s", ""))
                except:
                    pass
            else:
                easing = part

        return duration, easing

    @classmethod
    def apply(cls, widget, class_name, component=None):
        base = cls.get(class_name, "base", component)

        # WIDTH / HEIGHT
        width = base.get("width")
        height = base.get("height")

        if width and height:
            try:
                widget.resize(int(width), int(height))
                widget.base_size = int(width)
            except:
                pass

        # BORDER RADIUS saja — background TIDAK di-set ke QSS
        # Background sudah di-handle overlay._bg_color via color_anim
        # Kalau background di-set ke QSS: override WA_TranslucentBackground
        # → widget punya background solid, blur/transparency tidak kelihatan
        radius = base.get("border-radius")
        if radius:
            widget.setStyleSheet(f"border-radius: {radius}px;")
        else:
            widget.setStyleSheet("")

        widget.update_visual_state()

class Renns:
    """
    Factory universal untuk semua UI element.

    Usage:
        Renns.object("primary",  parent=self, text="pencet",    on_click=self.handler)
        Renns.object("primary2", parent=self, icon="button.png", on_click=self.handler)
        Renns.toggle("bool",     parent=self)
        Renns.wrap(my_widget,   "primary",   parent=self)
    """

    @staticmethod
    def object(class_name: str, parent=None,
               text: str = None, icon: str = None,
               on_click=None):
        from .button.button import RennsButton
        w = RennsButton(
            icon_path=icon,
            render_type="rect" if not icon else "icon",
            parent=parent,
        )
        if text:
            w.setText(text)
        w.setClass(class_name)
        if on_click:
            w.clicked.connect(on_click)
        return w

    @staticmethod
    def toggle(class_name: str, parent=None, on_change=None):
        from .toggle import RennsToggle
        w = RennsToggle(class_name, parent=parent)
        if on_change:
            w._on_change = on_change
        return w

    @staticmethod
    def action_group(class_name: str, children: list,
                     parent=None, icon: str = None, text: str = None,
                     direction: str = None, anchor: str = None):
        """
        Bikin action group — trigger button di layout, klik → floating pill overlay.

        children: list of dict:
            [
                {"class": "fab-item", "text": "Edit",   "on_click": fn},
                {"class": "fab-item", "text": "Delete", "on_click": fn},
            ]

        direction: "horizontal" | "vertical"  (override CSS action-direction)
        anchor: "left"|"center"|"right"|"top"|"bottom"  (override CSS action-anchor)
        """
        from .button.button import RennsButton
        from .action_group import RennsActionGroup

        trigger = RennsButton(
            icon_path=icon,
            render_type="icon" if icon else "rect",
            parent=None,
        )
        if text:
            trigger.setText(text)
        trigger.setClass(class_name)

        group = RennsActionGroup(
            class_name=class_name,
            trigger=trigger,
            items=children,
            parent=parent,
        )

        if direction:
            group._direction = direction
        if anchor:
            group._anchor = anchor

        return group

    @staticmethod
    def wrap(widget, class_name: str, parent=None):
        """Attach overlay + CSS ke QWidget apapun."""
        from PySide6.QtWidgets import QWidget
        from PySide6.QtCore import QEvent, QTimer
        from PySide6.QtGui import QColor
        from .button.button_ext.css_color import parse_css_color
        from .button.overlay import RennsOverlay, OVERLAY_MULTIPLIER
        from .button.button_ext.animation import resolve_easing
        from .button.button_ext.transform import parse_transform

        class _Wrapped(QWidget):
            def __init__(self, widget, class_name, parent):
                super().__init__(parent)
                self._class_name = class_name
                self._hovered = False
                self._pressed = False
                self.inner    = widget
                self.overlay  = None

                base = RennsStyle.get(class_name, "base")
                try:    w = int(float(base.get("width",  widget.width()  or 64)))
                except: w = widget.width() or 64
                try:    h = int(float(base.get("height", widget.height() or 64)))
                except: h = widget.height() or 64

                self.setFixedSize(w, h)
                widget.setParent(self)
                widget.setGeometry(0, 0, w, h)
                widget.installEventFilter(self)

            def showEvent(self, event):
                super().showEvent(event)
                if not self.overlay:
                    base = RennsStyle.get(self._class_name, "base")
                    try:    bw = int(float(base.get("width",  self.width())))
                    except: bw = self.width()
                    try:    bh = int(float(base.get("height", self.height())))
                    except: bh = self.height()
                    self.overlay = RennsOverlay(self.window(), None)
                    self.overlay.render_mode = "rect"
                    self.overlay._btn_w = bw
                    self.overlay._btn_h = bh
                    self.overlay.resize(bw * OVERLAY_MULTIPLIER, bh * OVERLAY_MULTIPLIER)
                    self.overlay.show()
                    self._update()
                QTimer.singleShot(0, self._sync)

            def _sync(self):
                if not self.overlay: return
                c = self.mapTo(self.window(), self.rect().center())
                self.overlay.move(c.x() - self.overlay.width() // 2,
                                  c.y() - self.overlay.height() // 2)

            def moveEvent(self, e):   super().moveEvent(e);   self._sync()
            def resizeEvent(self, e): super().resizeEvent(e); self._sync()

            def eventFilter(self, obj, event):
                t = event.type()
                if   t == QEvent.Enter:              self._hovered = True;  self._update()
                elif t == QEvent.Leave:              self._hovered = False; self._update()
                elif t == QEvent.MouseButtonPress:   self._pressed = True;  self._update()
                elif t == QEvent.MouseButtonRelease: self._pressed = False; self._update()
                return False

            def _update(self):
                if not self.overlay: return
                state  = "active" if self._pressed else "hover" if self._hovered else "base"
                props  = RennsStyle.get(self._class_name, state)
                base   = RennsStyle.get(self._class_name, "base")
                merged = {**base, **props}
                bg = merged.get("background")
                if bg:
                    dur, easing = RennsStyle.parse_transition(merged.get("transition", "0.25s ease"))
                    self.overlay.color_anim.stop()
                    self.overlay.color_anim.setStartValue(self.overlay.bgColor)
                    self.overlay.color_anim.setEndValue(parse_css_color(bg))
                    self.overlay.color_anim.setDuration(int(dur * 1000))
                    self.overlay.color_anim.setEasingCurve(resolve_easing(easing))
                    self.overlay.color_anim.start()
                scale, rotate = parse_transform(merged.get("transform"))
                dur, easing   = RennsStyle.parse_transition(merged.get("transition", "0.25s ease"))
                self.overlay.anim.stop()
                self.overlay.anim.setStartValue(self.overlay.scale)
                self.overlay.anim.setEndValue(scale)
                self.overlay.anim.setDuration(int(dur * 1000))
                self.overlay.anim.setEasingCurve(resolve_easing(easing))
                self.overlay.anim.start()
                self.overlay.style_data = merged
                self.overlay.update()

        return _Wrapped(widget, class_name, parent)