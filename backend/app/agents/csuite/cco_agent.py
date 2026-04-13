from __future__ import annotations

from app.agents.csuite.base import BaseCSuiteAgent
from app.agents.csuite.schemas import CCOOutput


class CCOAgent(BaseCSuiteAgent):
    name = "cco"
    schema = CCOOutput

    def _system_prompt(self) -> str:
        return (
            "You are a Chief Compliance Officer agent. Given an app idea, identify regulatory "
            "requirements, privacy policy needs, and GDPR obligations specific to the type of "
            "data and users this application handles."
        )

    def _user_prompt(self, idea_spec: dict) -> str:
        desc = idea_spec.get("description", "")
        return f"App idea: {desc}"
