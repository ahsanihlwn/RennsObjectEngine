# RennsObjectEngine

RennsObjectEngine is a PySide6-based UI animation engine that separates logic, visual rendering, and styling (RSS). It provides interactive components with smooth animations, elastic drag effects, and CSS-like state handling.

---

## License

This project is licensed under the **Mozilla Public License 2.0 (MPL-2.0)**.

---

## 1. Installation & Basic Setup

```python
import RennsObjectEngine as objects
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout
from PySide6.QtCore import Qt
import sys
```

Load the RSS file before creating any components:

```python
objects.RennsStyle.load("style1.rss")
```

---

## 2. Creating Components

### Button

```python
layout.addWidget(
    objects.Renns.object(
        "primary",
        parent=self,
        text="Click Me",
        on_click=self.handler
    )
)
```

Using an icon:

```python
objects.Renns.object(
    "primary2",
    parent=self,
    icon="button.png",
    on_click=self.handler
)
```

---

### Toggle

```python
layout.addWidget(
    objects.Renns.toggle(
        "bool",
        parent=self,
        on_change=self.on_toggle
    )
)
```

Handler:

```python
def on_toggle(self, state):
    print("ON" if state else "OFF")
```

---

## 3. RSS Structure (Style File)

Example:

```css
.primary {
    width: 120;
    height: 120;
    background: #2d7fff;
    border-radius: 20;
    transition: 0.4s ease;
}

.primary:hover {
    transform: scale(1.1);
    background: #4c8fff;
}

.primary:active {
    transform: scale(0.95);
}
```

---

## 4. Supported Properties

### Size

* `width`
* `height`
* `border-radius`

### Colors

* `background`
* `border-color`
* `border-width`
* `opacity`
* `color` (for text)

Background changes are animated using color transitions in the overlay layer.

---

### Transform

Supported:

```css
transform: scale(1.2);
transform: rotate(5deg);
transform: scale(1.1) rotate(8deg);
```

* `scale(x)`
* `rotate(xdeg)`

---

### Transition

Format:

```css
transition: 0.3s ease;
transition: 0.5s bounce;
transition: 0.4s spring;
```

Default: `0.25s ease`

---

## 5. Available Easing Functions

* `linear`
* `ease`
* `ease-in`
* `ease-out`
* `ease-in-out`
* `bounce`
* `spring`

Example:

```css
transition: 0.4s spring;
```

---

## 6. Elastic Drag (Advanced)

Add to base style:

```css
.primary {
    elastic-drag: 1.2;
}
```

Effect:

* The component can be dragged while pressed
* The further from center, the stronger the resistance (using tanh mapping)
* Snapback uses an elastic animation

---

## 7. Supported States

* `base`
* `hover`
* `active`

Example:

```css
.primary:hover { ... }
.primary:active { ... }
```

---

## 8. Render Modes

In Button:

```python
render_type="icon"
render_type="rect"
```

* `icon` → rendered using QIcon
* `rect` → rendered using RSS-based shape properties

---

## 9. Full RSS Example

```css
.primary {
    width: 140;
    height: 140;
    background: #2d7fff;
    border-radius: 24;
    border-color: #ffffff;
    border-width: 2;
    transform: scale(1);
    transition: 0.4s spring;
    elastic-drag: 1.2;
}

.primary:hover {
    transform: scale(1.1) rotate(3deg);
    background: #3f8fff;
}

.primary:active {
    transform: scale(0.9);
    background: #1f5fff;
}
```

---

## 10. Core Features

* Animated scale
* Animated rotation
* Smooth color transitions
* Elastic drag interaction
* Spring-based snapback
* Bounce easing support
* Hover & Active state handling
* Toggle component with signal support
* Rectangular rendering mode
* Icon rendering mode

---

## 11. Architecture

* **RennsButton** → Interaction logic
* **RennsOverlay** → Visual rendering & animation layer
* **RennsStyle** → RSS parsing & style management

Styling is fully separated from component logic.

---

## 12. Important Notes

* RSS must be loaded before creating any widgets
* Defining `width` and `height` is recommended for layout stability
* Default transition is `0.25s ease`
* `elastic-drag` is active only while pressing and dragging
* Without `transition`, transforms apply instantly
