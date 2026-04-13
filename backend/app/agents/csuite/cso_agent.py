from __future__ import annotations

from app.agents.csuite.base import BaseCSuiteAgent
from app.agents.csuite.schemas import CSOOutput


class CSOAgent(BaseCSuiteAgent):
    name = "cso"
    schema = CSOOutput

    def _system_prompt(self) -> str:
        return (
            "You are a Chief Security Officer agent. Given an app idea, define the auth "
            "architecture, encryption requirements, compliance needs, and a threat model "
            "with mitigations and severity ratings. Tailor to the specific app and its data."
        )

    def _user_prompt(self, idea_spec: dict) -> str:
        desc = idea_spec.get("description", "")
        return f"App idea: {desc}"
