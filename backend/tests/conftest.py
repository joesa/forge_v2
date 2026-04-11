from unittest.mock import patch


# Disable Redis rate limiter for all tests — prevents event loop leak
_redis_patch = patch("app.core.redis.redis_client", None)
_redis_patch_mw = patch("app.middleware.rate_limit.redis_client", None)


def pytest_configure(config):
    _redis_patch.start()
    _redis_patch_mw.start()


def pytest_unconfigure(config):
    _redis_patch.stop()
    _redis_patch_mw.stop()
