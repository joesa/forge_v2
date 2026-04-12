"""Build agents package — 10 sequential agents + hotfix."""
from app.agents.build.scaffold_agent import ScaffoldAgent
from app.agents.build.router_agent import RouterAgent
from app.agents.build.component_agent import ComponentAgent
from app.agents.build.page_agent import PageAgent
from app.agents.build.api_agent import APIAgent
from app.agents.build.db_agent import DBAgent
from app.agents.build.auth_agent import AuthAgent
from app.agents.build.style_agent import StyleAgent
from app.agents.build.test_agent import TestAgent
from app.agents.build.review_agent import ReviewAgent
from app.agents.build.hotfix_agent import HotfixAgent, apply_hotfix

BUILD_AGENTS = [
    ScaffoldAgent(),
    RouterAgent(),
    ComponentAgent(),
    PageAgent(),
    APIAgent(),
    DBAgent(),
    AuthAgent(),
    StyleAgent(),
    TestAgent(),
]

REVIEW_AGENT = ReviewAgent()

__all__ = [
    "BUILD_AGENTS",
    "REVIEW_AGENT",
    "HotfixAgent",
    "apply_hotfix",
    "ScaffoldAgent",
    "RouterAgent",
    "ComponentAgent",
    "PageAgent",
    "APIAgent",
    "DBAgent",
    "AuthAgent",
    "StyleAgent",
    "TestAgent",
    "ReviewAgent",
]
