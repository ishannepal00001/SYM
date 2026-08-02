from ..config import settings


class Executor:
    def __init__(self, provider) -> None:
        self.provider = provider

    def execute(self, tasks: list[str]):
        completed = []
        result = []
        for task in tasks:
            output = self.provider.chat(
                settings.ExcecutorPrompt.format(completed=completed, task=task)
            )
            result.append(output)
            yield output
