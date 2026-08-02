from dotenv import load_dotenv
import os
from pathlib import Path

env = load_dotenv(Path(__file__).parent / ".env")
print(env)


class Config:
    PlannerPrompt = """You are a task planner. Break down the user's goal into a clear, ordered list of steps needed to accomplish it.
    Rules:
- Output ONLY valid JSON. No explanation, no preamble, no markdown code fences.
- Use this exact structure:
{{"steps": [{{"step": 1, "action": "..."}}, {{"step": 2, "action": "..."}}]}}
- Each "action" should be a single, concrete, self-contained instruction — specific enough that it could be executed on its own without seeing other steps.
- Keep the step count minimal — only as many steps as are actually necessary to reach the goal.
- Do not include steps for things that don't require action (e.g. "understand the goal").
  Goal:
{goal}
"""
    ExcecutorPrompt = """
    You are executing one step of a larger task plan. You will be given a single instruction.
Rules:
- Carry out the instruction directly. Do not ask clarifying questions.
- Do not restate the instruction back.
- Do not add commentary like "Sure, here's..." or "I've completed this step."
- Return only the direct output/result of the instruction.
Completed so far:
{completed}

Current task:
{task}

"""
    GROQ_KEY_1 = os.getenv("GROQ_API_KEY_1")
    GROQ_KEY_2 = os.getenv("GROQ_API_KEY_2")
    OPENROUTER_KEY_1 = os.getenv("OPENROUTER_KEY_1")


settings = Config()
