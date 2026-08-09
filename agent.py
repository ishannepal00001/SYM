from agents.mind import Mind
from agents.hands import Hands
from managers.messagemanager import MessageManager
from config import settings


class SYMAgent:
    def __init__(self, provider):
        self.planner = Mind(provider)
        self.executor = Hands(provider)
        self.messageManger = MessageManager()

    def agent_loop(self, goal: str):
        self.messageManger.add_user(prompt=goal)
        PLAN_DAG = self.planner.plan(goal=goal)
        self.messageManger.add_agent(
            agent="planner", prompt=settings.PlannerPrompt, content=PLAN_DAG
        )
        output = self.executor.execute(PLAN_DAG)
        self.messageManger.add_agent(
            agent="executor", prompt=settings.ExcecutorPrompt, content=output
        )
        print(output)
