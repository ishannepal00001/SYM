from config import settings


class Thorat:
    def __init__(self, provider) -> None:
        self.provider = provider

    def talk(self, topic):
        task = self.provider.chat(
            settings.TalkerPrompt + "{goal}".format(goal=str(topic))
        )
        return task
