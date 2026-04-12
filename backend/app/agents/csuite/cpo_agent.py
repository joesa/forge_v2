from __future__ import annotations

from app.agents.csuite.base import BaseCSuiteAgent
from app.agents.csuite.schemas import CPOOutput


class CPOAgent(BaseCSuiteAgent):
    name = "cpo"
    schema = CPOOutput

    async def _run(self, idea_spec: dict) -> dict:
        return {
            "feature_prioritization": {
                "must": ["User authentication", "Core CRUD operations", "Responsive layout"],
                "should": ["Search functionality", "Email notifications", "Dashboard analytics"],
                "could": ["Dark mode", "Export to CSV", "API documentation page"],
                "wont": ["Mobile native app", "Offline mode", "Multi-tenancy"],
            },
            "mvp_scope": "Authentication + core CRUD + responsive UI + deployment",
            "user_stories": [
                {"title": "User registration", "description": "As a user I can sign up with email and password", "priority": "must"},
                {"title": "User login", "description": "As a user I can log in to access my data", "priority": "must"},
                {"title": "Create item", "description": "As a user I can create a new item", "priority": "must"},
                {"title": "View items", "description": "As a user I can view all my items", "priority": "must"},
                {"title": "Edit item", "description": "As a user I can update an existing item", "priority": "must"},
                {"title": "Delete item", "description": "As a user I can remove an item", "priority": "must"},
                {"title": "Search items", "description": "As a user I can search through my items", "priority": "should"},
                {"title": "Dashboard", "description": "As a user I can see summary analytics", "priority": "should"},
                {"title": "Profile settings", "description": "As a user I can update my profile", "priority": "should"},
                {"title": "Export data", "description": "As a user I can export my data as CSV", "priority": "could"},
            ],
            "success_metrics": [
                "Time to first working build < 5 minutes",
                "Zero build failures on first attempt",
                "User retention > 40% at day 7",
            ],
        }
