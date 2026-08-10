from agents.mind import Mind
from agents.hands import Hands
from managers.messagemanager import MessageManager
from config import settings


class SYMAgent:
    def __init__(self, provider):
        self.planner = Mind(provider)
        self.executor = Hands(provider)
        self.ready = []
        self.pending = {}
        self.messageManger = MessageManager()

    def _get_ready(self, task_dag):
        print(f"\n{task_dag}")
        for idx, task in enumerate(task_dag):
            if len(task.dependency) == 0:
                print(task)
                self.ready.append(task.task_title)

    def agent_loop(self, goal: str):
        self.messageManger.add_user(prompt=goal)
        PLAN_DAG = self.planner.plan(goal=goal)
        print(PLAN_DAG)
        self._get_ready(PLAN_DAG.tasks)

        # self.messageManger.add_agent(
        #     agent="planner", prompt=settings.PlannerPrompt, content=PLAN_DAG
        # )
        # output = self.executor.execute(PLAN_DAG)
        # self.messageManger.add_agent(
        #     agent="executor", prompt=settings.ExcecutorPrompt, content=output
        # )
