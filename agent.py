import os
import json
import requests
import time
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from typing import Annotated
from typing_extensions import TypedDict

from computer import Computer


load_dotenv()

VISION_URL = "http://127.0.0.1:8005/analyze"

computer = Computer()


# ============================================================
# COMPUTER TOOL
# ============================================================

@tool
def screenshot():
    """
    Take a screenshot of the current computer screen and analyze it
    using OmniParser. Returns the visible UI elements, their types,
    text, bounding boxes, and click coordinates.
    """

    print("calling screenshot in 5 secs")
    time.sleep(5)
    screenshot_path = computer.screenshot()

    with open(screenshot_path, "rb") as f:
        response = requests.post(
            VISION_URL,
            files={
                "file": (
                    "screen.png",
                    f,
                    "image/png"
                )
            },
            timeout=120,
        )

    response.raise_for_status()
    result =json.dumps(response.json())
    print(result)
    return result

tools = [screenshot]


# ============================================================
# LLM
# ============================================================

llm = ChatGroq(
    model="openai/gpt-oss-120b",
    temperature=0,
)

llm_with_tools = llm.bind_tools(tools)


# ============================================================
# LANGGRAPH STATE
# ============================================================

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]


SYSTEM_PROMPT = """
You are a computer-use agent.

You interact with a user's Windows computer through tools.

You currently have one tool:

- screenshot:
  Captures the current screen and returns detected UI elements.

When you need to know what is currently visible on the screen,
call screenshot.

Do not invent UI elements, coordinates, text, or application state.
Only use information returned by the screenshot tool.

For now, you cannot click, type, or otherwise modify the computer.
"""


# ============================================================
# LLM NODE
# ============================================================

def call_model(state: AgentState):

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        *state["messages"],
    ]

    response = llm_with_tools.invoke(messages)

    return {
        "messages": [response]
    }


# ============================================================
# ROUTING
# ============================================================

def should_continue(state: AgentState):

    last_message = state["messages"][-1]

    if getattr(last_message, "tool_calls", None):
        return "tools"

    return END


# ============================================================
# GRAPH
# ============================================================

graph_builder = StateGraph(AgentState)

graph_builder.add_node("agent", call_model)
graph_builder.add_node("tools", ToolNode(tools))

graph_builder.add_edge(START, "agent")

graph_builder.add_conditional_edges(
    "agent",
    should_continue,
    {
        "tools": "tools",
        END: END,
    },
)

graph_builder.add_edge("tools", "agent")

graph = graph_builder.compile()


# ============================================================
# MAIN
# ============================================================

def main():

    user_input = input("\nYou: ")

    result = graph.invoke({
        "messages": [
            HumanMessage(content=user_input)
        ]
    })

    final_message = result["messages"][-1]

    print("\nAgent:")
    print(final_message.content)


if __name__ == "__main__":
    main()