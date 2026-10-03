import argparse
import base64
import difflib
import json
import os
import re
from typing import Any
import time
import pyautogui
import win32gui
from groq import Groq
from mss import mss, tools
from pywinauto import Desktop
import ctypes
import win32api
from dotenv import load_dotenv
load_dotenv()

groq_api_key = os.getenv("GROQ_API_KEY")

MODEL = "qwen/qwen3.8-27b"
FUZZY_THRESHOLD = 0.90
REGION_PADDING = 100

QWEN_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "visual_region",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["found", "not_found", "ambiguous"],
                },
                "target_region": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "minItems": 4,
                    "maxItems": 4,
                },
                "description": {"type": "string"},
                "uia_hints": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "confidence": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1,
                },
            },
            "required": [
                "status",
                "target_region",
                "description",
                "uia_hints",
                "confidence",
            ],
        },
    },
}

QWEN_PROMPT = r"""
You are the visual targeting module of a computer-use agent.

You receive:
1. A screenshot of the current screen.
2. A GOAL describing what the agent wants to accomplish next.

Your job is NOT to find the exact click coordinate.

Instead, identify the SINGLE BEST VISIBLE NEXT ACTION that moves the agent
toward accomplishing the GOAL.

Think like a human:
- Understand the current application and visible state.
- Focus only on UI relevant to the GOAL.
- The goal may require multiple UI actions.
- If the final requested control is not currently visible, identify the
  visible control that should be activated FIRST to reveal or reach it.
- A menu, dropdown, dialog, tab, icon, or button that leads to the final
  action counts as a valid target.
- Do NOT return "not_found" merely because the final control is hidden
  behind a menu, dialog, dropdown, or another intermediate UI action.
- Do not invent invisible controls.
- Return ONE target region for the SINGLE BEST NEXT ACTION.
- The region only needs to be approximate.
- Ignore unrelated UI.

STATUS:
- "found": A useful visible next action exists. This includes an
  intermediate control that must be activated before the final goal can
  be reached.
- "not_found": No useful visible next action toward the GOAL is currently
  visible.
- "ambiguous": Multiple plausible next actions exist and you cannot
  confidently determine which one is the correct next action.

MULTI-STEP EXAMPLE:
Goal: "Run the program"
Current screen: A visible "Run" menu exists, but the actual run command
is inside that menu.

Return:
status = "found"
target = the visible "Run" menu

Do NOT return "not_found" because the final run command is not yet visible.

After the agent activates "Run", the screen will change and you will be
asked again to identify the next action.

UI AUTOMATION HINTS:
Provide 10 likely values for the target control's accessibility
"Name".

Put the most likely and specific names FIRST.

Include alternative names that the operating system or application might
use for the same control.

Prefer short names such as:
"Communities"
"Status"
"Attach"
"New chat"

Do NOT add role words such as:
"button"
"icon"
"menu item"

Do not describe coordinates inside the hints.

COORDINATES:
Return target_region as [x1, y1, x2, y2] in ACTUAL SCREEN PIXELS.
The screenshot resolution is {width}x{height}.
Origin is the top-left corner.

The region can be approximate. Accuracy of the region is less important
than correctly identifying the target and its approximate location.

GOAL:
{goal}
"""


def capture_screen() -> tuple[bytes, int, int]:
    # with mss() as sct:
    #     monitor = sct.monitors[1]  # primary monitor
    #     shot = sct.grab(monitor)
    #     png = tools.to_png(shot.rgb, shot.size)
    #     return png, shot.width, shot.height
    from PIL import Image

    path = "test.png"

    with open(path, "rb") as f:
        png = f.read()

    img = Image.open(path)
    return png, img.width, img.height


def qwen_locate(
    client: Groq,
    image_png: bytes,
    width: int,
    height: int,
    goal: str,
) -> dict[str, Any]:
    image_b64 = base64.b64encode(image_png).decode("ascii")
    prompt = QWEN_PROMPT.format(width=width, height=height, goal=goal)

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_b64}"
                        },
                    },
                ],
            }
        ],
        temperature=0,
        reasoning_effort="none",
        max_completion_tokens=500,
        response_format=QWEN_SCHEMA,
    )

    raw = response.choices[0].message.content
    return json.loads(raw)


def clamp_region(
    region: list[int], width: int, height: int, padding: int = 0
) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = map(int, region)
    x1, x2 = sorted((x1, x2))
    y1, y2 = sorted((y1, y2))

    x1 = max(0, x1 - padding)
    y1 = max(0, y1 - padding)
    x2 = min(width, x2 + padding)
    y2 = min(height, y2 + padding)

    return x1, y1, x2, y2


def rect_intersection_area(
    a: tuple[int, int, int, int],
    b: tuple[int, int, int, int],
) -> int:
    left = max(a[0], b[0])
    top = max(a[1], b[1])
    right = min(a[2], b[2])
    bottom = min(a[3], b[3])

    if right <= left or bottom <= top:
        return 0

    return (right - left) * (bottom - top)


def rect_center(rect: tuple[int, int, int, int]) -> tuple[int, int]:
    return (
        (rect[0] + rect[2]) // 2,
        (rect[1] + rect[3]) // 2,
    )


def normalize_name(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[\W_]+", " ", value, flags=re.UNICODE)
    return re.sub(r"\s+", " ", value).strip()


def score_name(candidate: str, hint: str) -> float:
    c = normalize_name(candidate)
    h = normalize_name(hint)
    
    if not c or not h:
        return 0.0

    if c == h:
        return 1.0

    # Qwen hint is contained as a meaningful phrase
    if h in c:
        return 0.98

    if c in h:
        return 0.95

    return difflib.SequenceMatcher(None, c, h).ratio()


def get_active_window() -> tuple[Any, int]:
    hwnd = win32gui.GetForegroundWindow()
    if not hwnd:
        raise RuntimeError("Could not get the foreground window.")

    app = Desktop(backend="uia").window(handle=hwnd)
    return app, hwnd

def collect_uia_candidates(
    app: Any,
    region: tuple[int, int, int, int],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen = set()
    ACTIONABLE_TYPES = {
        "Button",
        "CheckBox",
        "ComboBox",
        "Edit",
        "Hyperlink",
        "ListItem",
        "MenuItem",
        "RadioButton",
        "ScrollBar",
        "Slider",
        "SplitButton",
        "TabItem",
        "TreeItem",
        "DataItem",
    }

    # TIMER
    t0 = time.perf_counter()

    controls = app.descendants()

    t1 = time.perf_counter()

    print(f"UIA descendants() : {t1 - t0:.4f}s")
    print(f"Controls returned  : {len(controls)}")

    for control in controls:
        try:
            r = control.rectangle()
            rect = (r.left, r.top, r.right, r.bottom)

            if rect[2] <= rect[0] or rect[3] <= rect[1]:
                continue

            if rect_intersection_area(rect, region) == 0:
                continue

            try:
                if not control.element_info.visible:
                    continue
            except Exception:
                pass

            name = (
                getattr(control.element_info, "name", None)
                or control.window_text()
                or ""
            )

            control_type = getattr(
                control.element_info, "control_type", None
            ) or ""

            if not name and control_type not in ACTIONABLE_TYPES:
                continue

            automation_id = getattr(
                control.element_info, "automation_id", None
            ) or ""

            class_name = getattr(
                control.element_info, "class_name", None
            ) or ""

            key = (name, control_type, rect, automation_id)

            if key in seen:
                continue

            seen.add(key)

            candidates.append(
                {
                    "name": str(name),
                    "control_type": str(control_type),
                    "automation_id": str(automation_id),
                    "class_name": str(class_name),
                    "rect": list(rect),
                    "center": list(rect_center(rect)),
                }
            )

        except Exception:
            continue

    return candidates


def resolve_exact_or_fuzzy(
    candidates: list[dict[str, Any]],
    hints: list[str],
) -> tuple[dict[str, Any] | None, str | None, float]:
    ACTIONABLE_TYPES = {
    "Button",
    "CheckBox",
    "ComboBox",
    "Edit",
    "Hyperlink",
    "ListItem",
    "MenuItem",
    "RadioButton",
    "ScrollBar",
    "Slider",
    "SplitButton",
    "TabItem",
    "TreeItem",
    "DataItem",
}

    actionable = [
        c for c in candidates
        if c["control_type"] in ACTIONABLE_TYPES
    ]

    if actionable:
        candidates = actionable

    if not candidates or not hints:
        return None, None, 0.0

    scored: list[tuple[float, dict[str, Any], str]] = []

    for candidate in candidates:
        best = 0.0
        best_hint = ""

        for hint in hints:
            score = score_name(candidate["name"], hint)
            if score > best:
                best = score
                best_hint = hint
        print(f"candidate: {candidate['name']}, score: {score}, hint: {best_hint}")
        scored.append((best, candidate, best_hint))

        ACTIONABLE_PRIORITY = {
        "Button": 10,
        "SplitButton": 9,
        "MenuItem": 8,
        "CheckBox": 7,
        "RadioButton": 7,
        "ComboBox": 6,
        "TabItem": 5,
        "ListItem": 4,
        "TreeItem": 3,
        "DataItem": 2,
        "Edit": 1,
    }

    scored.sort(
        key=lambda item: (
            item[0],
            ACTIONABLE_PRIORITY.get(item[1]["control_type"], 0)
        ),
        reverse=True
    )
    print("\nTOP UIA MATCHES:")
    for score, candidate, hint in scored[:5]:
        print(
            f"  score={score:.3f} | "
            f"hint='{hint}' | "
            f"name='{candidate['name']}' | "
            f"type='{candidate['control_type']}' | "
            f"center={candidate['center']}"
        )

    top_score, top_candidate, top_hint = scored[0]
    second_score, second_candidate, second_hint = scored[1] if len(scored) > 1 else (0, None, "")

    if top_score >= 1.0:
        return top_candidate, "exact", top_score

    if top_score >= FUZZY_THRESHOLD:
        score_gap = top_score - second_score

        if (
            len(scored) == 1
            or score_gap >= 0.05
            or (
                score_gap == 0
                and ACTIONABLE_PRIORITY.get(top_candidate["control_type"], 0)
                > ACTIONABLE_PRIORITY.get(second_candidate["control_type"], 0)
            )
        ):
            return top_candidate, "fuzzy", top_score

    return None, None, top_score


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--goal", required=True)
    parser.add_argument("--move", action="store_true")
    parser.add_argument("--click", action="store_true")
    args = parser.parse_args()

    if args.click and not args.move:
        args.move = True



    client = Groq(api_key=groq_api_key)

    image_png, width, height = capture_screen()
    print(f"Screen: {width}x{height}")

    qwen = qwen_locate(
        client=client,
        image_png=image_png,
        width=width,
        height=height,
        goal=args.goal,
    )

    print("\nQwen:")
    print(json.dumps(qwen, indent=2, ensure_ascii=False))

    if qwen["status"] != "found":
        print("\nNo usable target region.")
        return

    region = clamp_region(qwen["target_region"], width, height)
    expanded_region = clamp_region(
        qwen["target_region"],
        width,
        height,
        padding=REGION_PADDING,
    )

    app, hwnd = get_active_window()
    title = win32gui.GetWindowText(hwnd)

    print(f"\nActive window: {title}")
    print(f"Qwen region: {region}")
    print(f"Expanded region: {expanded_region}")

    from time import perf_counter

    t = perf_counter()
    candidates = collect_uia_candidates(
    app,
    (0, 0, width, height),
)
    print(f"UIA collection: {perf_counter() - t:.3f}s")

    t = perf_counter()
    target, method, score = resolve_exact_or_fuzzy(
        candidates,
        qwen["uia_hints"],
    )
    print(f"Matching: {perf_counter() - t:.3f}s")

    if target:
        x, y = target["center"]

        print("\nRESOLVED")
        print(f"Method: {method}")
        print(f"Match score: {score:.3f}")
        print(f"UIA name: {target['name']}")
        print(f"UIA type: {target['control_type']}")
        print(f"Exact screen coordinates: ({x}, {y})")

        if args.move:
            pyautogui.moveTo(x, y, duration=0.15)

        if args.click:
            pyautogui.click(x, y)

        return

    print("\nNO DIRECT UIA MATCH")
    print("Do not click yet.")
    print("These candidates should be sent to the 120B reasoning layer next.")


if __name__ == "__main__":
    main()
    candidate = "New Terminal (Ctrl+Shift+`) [Alt] Split Terminal (Ctrl+Shift+5)"
    hint = "New Terminal"

    print(normalize_name(candidate))
    print(normalize_name(hint))
    print(normalize_name(hint) in normalize_name(candidate))
