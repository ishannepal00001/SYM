import json
from typing import Any, Dict
from config import settings


class Mind:
    def __init__(self, provider) -> None:
        self.provider = provider

    def plan(self, goal):
        """Returns a Structured JSON for the given task"""
        task: Dict[str, Any] = self.provider.chat(
            settings.PlannerPrompt.format(goal=goal)
        )
        json_task = json.loads(str(task))
        print(json_task)
        return json_task
