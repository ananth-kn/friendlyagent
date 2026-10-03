import ctypes
import json
import os
import time
from dataclasses import asdict, dataclass
from typing import Any

import mss
import pyautogui
from pywinauto import Desktop


INTERACTIVE_TYPES = {
    "Button",
    "MenuItem",
    "TabItem",
    "TreeItem",
    "ListItem",
    "Edit",
    "ComboBox",
    "CheckBox",
    "RadioButton",
    "Hyperlink",
}

CONTAINER_TYPES = {
    "Pane",
    "Document",
    "ToolBar",
    "Group",
    "Tab",
    "List",
    "Tree",
    "Menu",
    "Window",
    "Custom",
}


def collect_ui_elements(control, results):
    """
    Walk the UI Automation tree without flattening every descendant.

    Interactive controls are collected, and we stop descending into them.
    Structural containers are traversed.
    """

    try:
        control_type = str(
            control.element_info.control_type or ""
        )

        if not control.is_visible():
            return

        rect = control.rectangle()

        if rect.width() <= 0 or rect.height() <= 0:
            return

        # If this is an interactive element, keep it
        # and DON'T recursively inspect everything inside it.
        if control_type in INTERACTIVE_TYPES:
            results.append(control)
            return

        # Only continue through structural containers.
        if control_type in CONTAINER_TYPES:
            try:
                children = control.children()
            except Exception:
                return

            for child in children:
                collect_ui_elements(child, results)

    except Exception:
        return
    
def is_on_screen(rect, screen_width, screen_height):
    return (
        rect.right > 0
        and rect.bottom > 0
        and rect.left < screen_width
        and rect.top < screen_height
        and rect.width() > 0
        and rect.height() > 0
    )

@dataclass
class Element:
    id: int
    type: str
    name: str
    automation_id: str
    class_name: str
    x: int
    y: int
    w: int
    h: int


class Computer:
    """Windows computer-use layer using Microsoft UI Automation via pywinauto."""

    def __init__(self, screenshot_dir: str = "computer_state"):
        self.screenshot_dir = screenshot_dir
        os.makedirs(self.screenshot_dir, exist_ok=True)
        self._elements: dict[int, Element] = {}

    # --------------------------- observation ---------------------------

    def screenshot(self) -> str:
        path = os.path.abspath(os.path.join(self.screenshot_dir, "screen.png"))
        with mss.MSS() as sct:
            sct.shot(output=path)
        return path

    def mouse_position(self) -> tuple[int, int]:
        p = pyautogui.position()
        return int(p.x), int(p.y)

    def observe(self, include_screenshot: bool = True) -> dict[str, Any]:
        print("observing")
        screenshot_path = self.screenshot() if include_screenshot else None
        # pywinauto does not expose Desktop(...).get_active().
        # Ask Windows directly for the foreground window handle, then wrap it in UIA.
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        if not hwnd:
            raise RuntimeError("Could not determine the active Windows window.")

        window = Desktop(backend="uia").window(handle=hwnd).wrapper_object()

        elements: list[Element] = []
        next_id = 1

        controls = []

        try:
            for child in window.children():
                collect_ui_elements(child, controls)
        except Exception:
            controls = []

        # Get screen dimensions
        with mss.MSS() as sct:
            monitor = sct.monitors[0]
            screen_width = monitor["width"]
            screen_height = monitor["height"]

        seen = set()

        for control in controls:
            try:
                control_type = str(
                    control.element_info.control_type or ""
                )

                if not control.is_visible() or not control.is_enabled():
                    continue

                rect = control.rectangle()

                if not is_on_screen(
                    rect,
                    screen_width,
                    screen_height
                ):
                    continue

                name = control.window_text() or ""
                automation_id = str(
                    control.element_info.automation_id or ""
                )
                class_name = str(
                    control.element_info.class_name or ""
                )

                # Prevent the same visible UI element from being added
                # repeatedly by applications such as WhatsApp.
                signature = (
                    control_type,
                    name,
                    automation_id,
                    class_name,
                    int(rect.left),
                    int(rect.top),
                    int(rect.width()),
                    int(rect.height()),
                )

                if signature in seen:
                    continue

                seen.add(signature)

                elements.append(
                    Element(
                        id=next_id,
                        type=control_type,
                        name=name,
                        automation_id=automation_id,
                        class_name=class_name,
                        x=int(rect.left),
                        y=int(rect.top),
                        w=int(rect.width()),
                        h=int(rect.height()),
                    )
                )

                next_id += 1

            except Exception:
                continue

        self._elements = {e.id: e for e in elements}
        mouse_x, mouse_y = self.mouse_position()

        return {
            "window": self._window_name(window),
            "mouse": {"x": mouse_x, "y": mouse_y},
            "elements": [asdict(e) for e in elements],
            "screenshot": screenshot_path,
            "timestamp": time.time(),
        }

    @staticmethod
    def _window_name(window) -> str:
        try:
            return window.window_text() or ""
        except Exception:
            return ""

    # ----------------------------- actions -----------------------------

    def _get_element(self, element_id: int) -> Element:
        element = self._elements.get(element_id)
        if element is None:
            raise ValueError(
                f"Unknown element_id={element_id}. "
                "Call observe() again because element IDs expire after observation."
            )
        return element

    @staticmethod
    def _center(element: Element) -> tuple[int, int]:
        return element.x + element.w // 2, element.y + element.h // 2

    def click(self, element_id: int) -> None:
        element = self._get_element(element_id)
        pyautogui.click(*self._center(element))

    def type_text(self, element_id: int, text: str, interval: float = 0.01) -> None:
        element = self._get_element(element_id)
        pyautogui.click(*self._center(element))
        pyautogui.write(text, interval=interval)

    def keypress(self, key: str) -> None:
        pyautogui.press(key)

    def hotkey(self, *keys: str) -> None:
        pyautogui.hotkey(*keys)

    def scroll(self, amount: int) -> None:
        pyautogui.scroll(amount)

    def drag(self, from_element_id: int, to_element_id: int, duration: float = 0.3) -> None:
        start = self._center(self._get_element(from_element_id))
        end = self._center(self._get_element(to_element_id))
        pyautogui.moveTo(*start, duration=0.1)
        pyautogui.dragTo(*end, duration=duration, button="left")

    def move(self, element_id: int, duration: float = 0.1) -> None:
        pyautogui.moveTo(*self._center(self._get_element(element_id)), duration=duration)

    def wait(self, seconds: float) -> None:
        if not 0 <= seconds <= 30:
            raise ValueError("wait must be between 0 and 30 seconds")
        time.sleep(seconds)

    def execute(self, action: dict[str, Any]) -> None:
        action_type = action.get("action")

        if action_type == "click":
            self.click(int(action["element_id"]))
        elif action_type == "type":
            self.type_text(int(action["element_id"]), str(action["text"]))
        elif action_type == "keypress":
            self.keypress(str(action["key"]))
        elif action_type == "hotkey":
            keys = action.get("keys", [])
            if not isinstance(keys, list) or not keys:
                raise ValueError("hotkey requires a non-empty 'keys' list")
            self.hotkey(*(str(k) for k in keys))
        elif action_type == "scroll":
            self.scroll(int(action.get("amount", -5)))
        elif action_type == "drag":
            self.drag(int(action["from_element_id"]), int(action["to_element_id"]))
        elif action_type == "move":
            self.move(int(action["element_id"]))
        elif action_type == "wait":
            self.wait(float(action.get("seconds", 1)))
        elif action_type == "done":
            return
        else:
            raise ValueError(f"Unsupported action: {action_type!r}")


if __name__ == "__main__":
    computer = Computer()

    print("Computer observer started.")
    print("Capturing screen every 5 seconds.")
    print("Press Ctrl+C to stop.\n")
    
    iteration = 0

    try:
        while True:
            iteration += 1
            time.sleep(5)
            state = computer.observe(include_screenshot=True)

            print("=" * 70)
            print(f"Observation #{iteration}")
            print(f"Window: {state['window']}")
            print(
                f"Mouse: ({state['mouse']['x']}, "
                f"{state['mouse']['y']})"
            )
            print(f"UI elements: {len(state['elements'])}")
            print(f"Screenshot: {state['screenshot']}")
            print(f"TOTAL ELEMENTS: {len(state['elements'])}")

            for element in state["elements"]:
                print(
                    f"[{element['id']:3}] "
                    f"{element['type']:<15} "
                    f"{element['name'][:80]}"
                )
            # Show the full processed state if you want it
            # print(json.dumps(state, indent=2, ensure_ascii=False))

            

    except KeyboardInterrupt:
        print("\nObserver stopped.")
