from agents.mouth import Mouth
from agents.throat import Thorat
from agents.mind import Mind
from agents.hands import Hands
from managers.messagemanager import MessageManager
from agents.ear import Ear


class SYMAgent:
    def __init__(self, provider):
        self.planner = Mind(provider)
        self.executor = Hands(provider)
        self.ear = Ear()
        self.throat = Thorat(provider)
        self.mouth = Mouth()
        self.ready = []
        self.pending = {}
        self.messageManger = MessageManager()

    def agent_loop(self):
        output = self.ear.hear()
        print(output)
        self.messageManger.add_user(prompt=str(output))
        output = self.throat.talk(topic=output)
        print(output)
        self.mouth.speak(output, voice="en_GB-northern_english_male-medium.onnx")

        # PLAN_DAG = self.planner.plan(goal=output)
        # print(PLAN_DAG)
        # self.messageManger.add_agent(
        #     agent="planner", prompt=settings.PlannerPrompt, content=str(PLAN_DAG)
        # )
        # output = self.executor.execute(str(PLAN_DAG))
        # self.messageManger.add_agent(
        #     agent="executor", prompt=settings.ExcecutorPrompt, content=output
        # )
