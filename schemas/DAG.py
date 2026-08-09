from typing import List
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
        repo = {task.task_title: task for task in self.tasks}
        marked = set()
        unmarked = set()

        def visit(task):
            if task.task_title in marked:
                return
            if task.task_title in unmarked:
                raise ValueError(
                    "Cycling dependeny found: {title}".format(title=task.task_title)
                )
            unmarked.add(task.task_title)
            for dependency_title in task.dependency:
                dep_task = repo.get(dependency_title)
                if dep_task is not None:
                    visit(dep_task)
            marked.add(task.task_title)
            unmarked.remove(task.task_title)

        for task in self.tasks:
            visit(task)

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

    @model_validator(mode="after")
    def check_no_cycles(self):
        repo = {step.id: step for step in self.steps}
        marked = set()
        unmarked = set()

        def visit(step):
            if step.id in marked:
                return
            if step.id in unmarked:
                raise ValueError(
                    "Cycling dependeny found: {title}".format(title=step.id)
                )
            unmarked.add(step.id)
            for dependency_id in step.dependency:
                dep_task = repo.get(dependency_id)
                if dep_task is not None:
                    visit(dep_task)
            marked.add(step.id)
            unmarked.remove(step.id)

        for task in self.steps:
            visit(task)

        return self
