import json
from typing import Any, Dict
from config import settings
from schemas.DAG import TasksRepo


class Mind:
    def __init__(self, provider) -> None:
        self.provider = provider

    def plan(self, goal):
        """Returns a Structured JSON for the given task"""
        task: Dict[str, Any] = self.provider.chat(
            settings.PlannerPrompt.format(goal=goal)
        )
        print(task)
        dag_output = TasksRepo(**task)
        print(dag_output)
        print(f"This is the dag ouptut {dag_output}")
        return dag_output
