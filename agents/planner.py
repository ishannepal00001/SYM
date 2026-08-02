from ..config import settings


class Planner:
    def __init__(self, provider) -> None:
        self.provider = provider

    def planner(self, goal):
        """Returns a Structured JSON for the given task"""
        task = self.provider.chat(settings.PlannerPrompt.format(goal=goal))
        cleaned_task = task.strip()
        return cleaned_task
