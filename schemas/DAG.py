from typing import List
from openrouter.components import model
from pydantic import BaseModel, model_validator


class Tasks(BaseModel):
    task_title: str
    task_description: str
    dependency: List[str]
    tool_description: str


class TasksRepo(BaseModel):
    tasks: List[Tasks]

    @model_validator(mode="after")
    def not_self_dependent(self):
        for task in self.tasks:
            for dependency_title in task.dependency:
                if dependency_title == task.task_title:
                    raise ValueError(
                        "Self dependency found in {task}".format(task=task.task_title)
                    )
        return self

    @model_validator(mode="after")
    def check_no_cycles(self):
        depedency_repo = {}
        for task in self.tasks:
            for dependency_title in task.dependency:
                task_title = depedency_repo.get(dependency_title)
                if dependency_title == task_title:
                    raise ValueError(
                        "Cycling dependency found for {task}".format(task=task_title)
                    )
                depedency_repo[dependency_title] = task.task_title
        return self


class Step(Tasks):
    id: str


class DAG(BaseModel):
    steps: List[Step]

    @model_validator(mode="after")
    def is_not_empty(self):
        if len(self.steps) < 1:
            raise ValueError("The DAG List cannot be empty!")
        return self

    @model_validator(mode="after")
    def has_unique_ids(self):
        steps = []
        for step in self.steps:
            if step.id in steps:
                raise ValueError("Found duplicate ID {id}".format(id=step.id))
            steps.append(step.id)
        return self

    @model_validator(mode="after")
    def not_self_dependent(self):
        for step in self.steps:
            for dependency_id in step.dependency:
                if step.id == dependency_id:
                    raise ValueError("Self dependency detected")

        return self
