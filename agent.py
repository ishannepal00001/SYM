from agents.mind import Mind
from agents.hands import Hands


class SYMAgent:
    def __init__(self, provider):
        self.planner = Mind(provider)
        self.executor = Hands(provider)

    def agent_loop(self, goal: str):
        PLAN_DAG = self.planner.plan(goal=goal)
        output = self.executor.execute(PLAN_DAG)
        print(output)
