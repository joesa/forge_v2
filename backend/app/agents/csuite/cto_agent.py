from __future__ import annotations

from app.agents.csuite.base import BaseCSuiteAgent
from app.agents.csuite.schemas import CTOOutput


class CTOAgent(BaseCSuiteAgent):
    name = "cto"
    schema = CTOOutput

    def _system_prompt(self) -> str:
        return (
            "You are a CTO agent. Given an app idea, recommend a concrete tech stack "
            "(frontend, backend, database, hosting), API design approach, scalability strategy, "
            "and identify the top technical risks. Tailor every recommendation to the specific app "
            "described — do NOT give generic boilerplate."
        )

    def _user_prompt(self, idea_spec: dict) -> str:
        desc = idea_spec.get("description", "")
        framework = idea_spec.get("framework", "")
        services = idea_spec.get("services", [])
        return (
            f"App idea: {desc}\n"
            f"Preferred framework: {framework}\n"
            f"Cloud services requested: {', '.join(services) if services else 'none specified'}"
        )
