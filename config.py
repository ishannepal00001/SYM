from dotenv import load_dotenv
import os
from pathlib import Path

env = load_dotenv(Path(__file__).parent / ".env")
print(env)


class Config:
    PlannerPrompt = """
    You are a task planner. Given a user goal and a list of available tool 
capabilities, break the goal into an ordered list of tasks forming a 
dependency graph.
Output a JSON object matching this structure:
{{
  "tasks": [
    {{
      "task_title": "Short unique title, used as the reference key for dependencies",
      "task_description": "What this task does and why it's needed",
      "tool_description": "The capability required to do this, described 
                            in plain terms — what it needs to look up, 
                            compute, or act on. Leave as an empty string 
                            if this task needs no external capability 
                            (e.g. pure reasoning over prior results).",
      "dependency": ["task_title_of_an_earlier_task", ...]
    }}
  ]
}}
Rules:
1. Emit tasks in the order they must run. A task's "dependency" list may 
   only contain "task_title"s of tasks that appear BEFORE it in this 
   list. Never reference a task's own title, and never reference a title 
   that doesn't exist yet at the point you emit it.
2. Only add a dependency if this task needs the actual OUTPUT of that 
   task to run — not because the topics are related. If a task can run 
   independently, give it an empty dependency list.
3. Each "task_title" must be unique across the whole list.
4. Keep tasks atomic — one distinct unit of work per task. If a task 
   needs two separate capabilities, split it into two tasks with a 
   dependency between them.
5. "tool_description" describes what's needed, never a tool or API name — 
   you don't know what tools exist by name, only what capabilities are 
   available (listed below). If nothing external is needed, use "".
6. Do not include tasks that aren't necessary to achieve the goal.
Example (calibration only — do not reuse):
Goal: "check the weather and suggest an outfit"
{{
  "tasks": [
    {{"task_title": "get_location", 
     "task_description": "Determine the user's current location", 
     "tool_description": "resolve a device or IP address to a city", 
     "dependency": []}},
    {{"task_title": "get_weather", 
     "task_description": "Get current conditions for the resolved location", 
     "tool_description": "look up current weather conditions for a given location", 
     "dependency": ["get_location"]}},
    {{"task_title": "suggest_outfit", 
     "task_description": "Recommend clothing based on weather conditions", 
     "tool_description": "", 
     "dependency": ["get_weather"]}}
  ]
}}
Now plan for this goal:
{goal}
"""
    ExcecutorPrompt = """
    You are executing one step of a larger task plan. You will be given a single instruction.
Rules:
- Carry out the instruction directly. Do not ask clarifying questions.
- Do not restate the instruction back.
- Do not add commentary like "Sure, here's..." or "I've completed this step."
- Return only the direct output/result of the instruction.

Current task:
{task}
"""
    GROQ_KEY_1 = os.getenv("GROQ_API_KEY_1")
    GROQ_KEY_2 = os.getenv("GROQ_API_KEY_2")
    OPENROUTER_KEY_1 = os.getenv("OPENROUTER_KEY_1")


settings = Config()
