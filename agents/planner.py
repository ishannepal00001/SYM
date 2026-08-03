import json
from typing import Any, Dict
from config import settings


class Planner:
    def __init__(self, provider) -> None:
        self.provider = provider

    def plan(self, goal) -> list[Dict[int, str]]:
        """Returns a Structured JSON for the given task"""
        task: Dict[str, Any] = self.provider.chat(
            settings.PlannerPrompt.format(goal=goal)
        )
        print(task)
        json_task = json.loads(str(task))

        return [
            {idx: action["action"]}
            for idx, action in enumerate(json_task["steps"], start=1)
        ]
