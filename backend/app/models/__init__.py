"""ORM 模型汇总。

必须在这里导入所有模型，否则 Base.metadata.create_all() 看不到它们。
"""
from app.models.core import Environment, Project, User
from app.models.execution import AITask, Defect, Execution
from app.models.testcase import Scenario, ScenarioStep, TestCase, TestPlan, TestPlanCase
from app.models.websession import WebSession

__all__ = [
    "User",
    "Project",
    "Environment",
    "TestCase",
    "Scenario",
    "ScenarioStep",
    "TestPlan",
    "TestPlanCase",
    "Execution",
    "Defect",
    "AITask",
    "WebSession",
]
