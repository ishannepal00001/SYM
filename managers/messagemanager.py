from config import settings


class MessageManager:
    def __init__(self):
        self.messages = list()

    def __manage_connection(self):
        pass

    def add_agent(self, agent: str, prompt: str, content: str):
        if agent.lower() == "planner":
            self.messages.append(
                {"role": agent.lower(), "content": prompt.format(goal=content)}
            )
        if agent.lower() == "executor":
            self.messages.append(
                {"role": agent.lower(), "content": prompt.format(task=content)}
            )

    def add_user(self, prompt: str):
        self.messages.append({"role": "user", "content": prompt.lower()})
