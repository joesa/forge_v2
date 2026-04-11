import inngest

from app.config import settings

forge_inngest = inngest.Inngest(
    app_id="forge",
    event_key=settings.INNGEST_EVENT_KEY,
    signing_key=settings.INNGEST_SIGNING_KEY,
    is_production=(settings.FORGE_ENV == "production"),
)
