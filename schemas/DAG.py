from typing import List
from openrouter.components import model
from pydantic import BaseModel, model_validator


class Tasks(BaseModel):
    task_title: str
    task_description: str
    dependency: List[str]
    tool_description: str


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
    def is_acyclic(self):
        return self
