from typing import List
from pydantic import BaseModel


class Tasks(BaseModel):
    task_title: str
    task_description: str
    dependency: list[str]
    tool_description: str


class Step(Tasks):
    id: str


class DAG(BaseModel):
    steps: List[Step]
