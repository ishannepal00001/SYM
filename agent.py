from agents.executor import Executor
from agents.planner import Planner


class SYMAgent:
    def __init__(self, provider):
        self.planner = Planner(provider)
        self.executor = Executor(provider)

    def agent_loop(self, goal: str):
        PLAN_DAG = self.planner.plan(goal=goal)
        for plan in self.executor.execute(PLAN_DAG):
            print(plan)
