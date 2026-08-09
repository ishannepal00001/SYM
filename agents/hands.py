from typing import Any, Dict
from config import settings


class Hands:
    def __init__(self, provider) -> None:
        self.provider = provider

    def execute(self, tasks):
        completed = []
        output = self.provider.chat(
            settings.ExcecutorPrompt.format(completed=completed, task=tasks)
        )
        return output
