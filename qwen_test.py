import base64
import json
import pyautogui
from groq import Groq
import time
MODEL = "qwen/qwen3.8-27b"

# Capture current screen
print("capturing image in 5 seconds")
time.sleep(5)
img = pyautogui.screenshot()
img.save("test_screen.png")

with open("test_screen.png", "rb") as f:
    image_b64 = base64.b64encode(f.read()).decode()

client = Groq()
prompt="""You are the visual grounding and screen-understanding module of a computer-use agent.

You receive:
1. A screenshot of the current computer screen.
2. A GOAL describing what the main agent wants to accomplish or understand.

Your job is to determine the most relevant information or the SINGLE BEST NEXT ACTION needed to make progress toward the GOAL.

Think like a human using the computer:

- First understand the current application and visible state.
- Focus only on things relevant to the GOAL.
- Ignore unrelated UI and content.
- The required control may be indirect. It may be behind a menu, icon,
  dropdown, tab, dialog, hover state, or another control.
- Do not require the visible label to exactly match the GOAL.
- Infer the function of visible controls from their label, appearance,
  position, and surrounding context.
- If the required control is currently visible, return it.
- If the required control is hidden until hovering, return the visible
  element that should be hovered first.
- NEVER return coordinates for an element that is not currently visible.
- Return only the SINGLE BEST NEXT ACTION. Do not return a sequence.
- After an action is executed, a new screenshot will be provided and you
  will reassess the screen from the beginning.
- If the GOAL requires understanding rather than an action, return the
  relevant visible content instead.
- If the GOAL requires both understanding and action, return both.
- Never invent information, text, controls, or coordinates.
- For exact-text requests, preserve the text exactly.
- For understanding requests, summarize only the relevant content.

Coordinates must be normalized from 0 to 1000:
x=0 is the left edge, x=1000 is the right edge
y=0 is the top edge, y=1000 is the bottom edge.

GOAL: go to status page
"""

response = client.chat.completions.create(
    model="qwen/qwen3.8-27b",
    messages=[
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{image_b64}"
                    }
                }
            ]
        }
    ],
    temperature=0,
    max_completion_tokens=12000,
    reasoning_effort="none",
response_format = {
    "type": "json_schema",
    "json_schema": {
        "name": "visual_grounding",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["found", "not_found", "ambiguous"]
                },
                "mode": {
                    "type": "string",
                    "enum": ["action", "understanding", "both"]
                },
                "action": {
                    "type": ["string", "null"],
                    "enum": [
                        "click",
                        "double_click",
                        "right_click",
                        "hover",
                        "focus",
                        "select",
                        "drag",
                        "scroll",
                        None
                    ]
                },
                "target": {
                    "type": ["object", "null"],
                    "additionalProperties": False,
                    "properties": {
                        "type": {"type": "string"},
                        "label": {"type": "string"},
                        "description": {"type": "string"},
                        "center": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "minItems": 2,
                            "maxItems": 2
                        }
                    },
                    "required": [
                        "type",
                        "label",
                        "description",
                        "center"
                    ]
                },
                "content": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "summary": {"type": "string"},
                        "exact_text": {
                            "type": "array",
                            "items": {"type": "string"}
                        }
                    },
                    "required": [
                        "summary",
                        "exact_text"
                    ]
                },
                "next_step": {"type": "string"},
                "confidence": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1
                }
            },
            "required": [
                "status",
                "mode",
                "action",
                "target",
                "content",
                "next_step",
                "confidence"
            ]
        }
    }
}
)

result = json.loads(response.choices[0].message.content)

print("Model:", result)

if result.get("found"):
    screen_w, screen_h = pyautogui.size()

    x = round(result["x"] / 1000 * screen_w)
    y = round(result["y"] / 1000 * screen_h)

    print(f"Screen coordinates: ({x}, {y})")