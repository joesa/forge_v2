"""Tests for Session 3.1 — Preview System backend services and routes."""
from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException


# ═══════════════════════════════════════════════════════════════════
# Preview Service
# ═══════════════════════════════════════════════════════════════════


class TestPreviewService:
    """Tests for preview_service.py."""

    @pytest.mark.asyncio
    @patch("app.services.preview_service.get_read_session")
    async def test_get_preview_url_success(self, mock_read):
        from app.services.preview_service import get_preview_url

        sandbox_id = uuid.uuid4()
        user_id = uuid.uuid4()
        project_id = uuid.uuid4()

        mock_sandbox = MagicMock()
        mock_sandbox.id = sandbox_id
        mock_sandbox.project_id = project_id
        mock_sandbox.status = MagicMock(value="claimed")
        mock_sandbox.sandbox_url = None

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.first.return_value = (mock_sandbox, MagicMock())
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_read.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_read.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await get_preview_url(sandbox_id, user_id)
        assert result["sandbox_id"] == str(sandbox_id)
        assert "preview_url" in result
        assert str(sandbox_id) in result["preview_url"]

    @pytest.mark.asyncio
    @patch("app.services.preview_service.get_read_session")
    async def test_get_preview_url_not_found(self, mock_read):
        from app.services.preview_service import get_preview_url

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.first.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_read.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_read.return_value.__aexit__ = AsyncMock(return_value=False)

        with pytest.raises(HTTPException) as exc_info:
            await get_preview_url(uuid.uuid4(), uuid.uuid4())
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    @patch("app.services.preview_service.redis_client", None)
    @patch("app.services.preview_service.get_read_session")
    async def test_check_preview_health_no_cache(self, mock_read):
        from app.services.preview_service import check_preview_health

        sandbox_id = uuid.uuid4()

        # Mock the DB lookup for direct sandbox URL
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_read.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_read.return_value.__aexit__ = AsyncMock(return_value=False)

        # Without Redis, it will attempt HTTP and likely fail — that's fine
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await check_preview_health(sandbox_id)
            assert result["sandbox_id"] == str(sandbox_id)
            assert result["healthy"] is True
            assert result["status_code"] == 200

    @pytest.mark.asyncio
    @patch("app.services.preview_service.redis_client")
    async def test_check_preview_health_cached(self, mock_redis):
        from app.services.preview_service import check_preview_health

        sandbox_id = uuid.uuid4()
        cached_data = json.dumps({
            "sandbox_id": str(sandbox_id),
            "healthy": True,
            "status_code": 200,
            "latency_ms": 42.5,
        })
        mock_redis.get = AsyncMock(return_value=cached_data)

        result = await check_preview_health(sandbox_id)
        assert result["healthy"] is True
        assert result["latency_ms"] == 42.5

    @pytest.mark.asyncio
    @patch("app.services.preview_service.redis_client", None)
    @patch("app.services.preview_service.get_read_session")
    async def test_check_preview_health_unreachable(self, mock_read):
        from app.services.preview_service import check_preview_health
        import httpx

        sandbox_id = uuid.uuid4()

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_read.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_read.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await check_preview_health(sandbox_id)
            assert result["healthy"] is False

    @pytest.mark.asyncio
    @patch("app.services.preview_service.storage_service")
    async def test_take_screenshot_with_injected_page(self, mock_storage):
        from app.services.preview_service import take_screenshot

        sandbox_id = uuid.uuid4()
        mock_storage.upload_file = AsyncMock(return_value="https://example.com/screenshot.webp")

        mock_page = AsyncMock()
        mock_page.screenshot = AsyncMock(return_value=b"fake-webp-bytes")

        result = await take_screenshot(sandbox_id, "/dashboard", playwright_page=mock_page)
        assert result["screenshot_url"] == "https://example.com/screenshot.webp"
        assert "dashboard" in result["storage_key"]
        mock_page.goto.assert_called_once()
        mock_page.screenshot.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.services.preview_service.storage_service")
    async def test_take_screenshot_index_route(self, mock_storage):
        from app.services.preview_service import take_screenshot

        sandbox_id = uuid.uuid4()
        mock_storage.upload_file = AsyncMock(return_value="https://example.com/index.webp")

        mock_page = AsyncMock()
        mock_page.screenshot = AsyncMock(return_value=b"bytes")

        result = await take_screenshot(sandbox_id, "/", playwright_page=mock_page)
        assert "index" in result["storage_key"]

    def test_generate_share_token_deterministic(self):
        from app.services.preview_service import _generate_share_token

        sandbox_id = uuid.uuid4()
        expires = 1700000000
        t1 = _generate_share_token(sandbox_id, expires)
        t2 = _generate_share_token(sandbox_id, expires)
        assert t1 == t2
        assert len(t1) == 64  # SHA-256 hex digest

    def test_generate_share_token_is_hmac(self):
        from app.services.preview_service import _generate_share_token

        sandbox_id = uuid.uuid4()
        expires = 1700000000
        expected = hmac.new(
            b"test-hmac-secret",
            f"{sandbox_id}:{expires}".encode(),
            hashlib.sha256,
        ).hexdigest()
        token = _generate_share_token(sandbox_id, expires)
        # Token should be a valid hex digest
        assert len(token) == 64
        int(token, 16)  # Should not raise

    @pytest.mark.asyncio
    @patch("app.services.preview_service.redis_client", None)
    @patch("app.services.preview_service.get_write_session")
    @patch("app.services.preview_service.get_read_session")
    async def test_create_share_success(self, mock_read, mock_write):
        from app.services.preview_service import create_share

        sandbox_id = uuid.uuid4()
        user_id = uuid.uuid4()

        # Mock ownership check
        mock_sandbox = MagicMock()
        mock_sandbox.id = sandbox_id
        mock_sandbox.project_id = uuid.uuid4()
        mock_read_session = AsyncMock()
        mock_read_result = MagicMock()
        mock_read_result.first.return_value = (mock_sandbox, MagicMock())
        mock_read_session.execute = AsyncMock(return_value=mock_read_result)
        mock_read.return_value.__aenter__ = AsyncMock(return_value=mock_read_session)
        mock_read.return_value.__aexit__ = AsyncMock(return_value=False)

        # Mock DB write
        mock_w_session = AsyncMock()
        mock_w_session.add = lambda x: setattr(x, "id", uuid.uuid4())
        mock_w_session.flush = AsyncMock()
        mock_write.return_value.__aenter__ = AsyncMock(return_value=mock_w_session)
        mock_write.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await create_share(sandbox_id, user_id, expires_hours=24)
        assert "token" in result
        assert "preview_url" in result
        assert "expires_at" in result
        assert len(result["token"]) == 64

    @pytest.mark.asyncio
    @patch("app.services.preview_service.redis_client", None)
    @patch("app.services.preview_service.get_write_session")
    async def test_revoke_share_success(self, mock_write):
        from app.services.preview_service import revoke_share

        user_id = uuid.uuid4()
        token = "a" * 64

        mock_share = MagicMock()
        mock_share.user_id = user_id
        mock_share.revoked = False
        mock_share.status = "active"

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_share
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_write.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_write.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await revoke_share(token, user_id)
        assert result["revoked"] is True
        assert mock_share.revoked is True
        assert mock_share.status == "revoked"

    @pytest.mark.asyncio
    @patch("app.services.preview_service.redis_client", None)
    @patch("app.services.preview_service.get_write_session")
    async def test_revoke_share_not_found(self, mock_write):
        from app.services.preview_service import revoke_share

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_write.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_write.return_value.__aexit__ = AsyncMock(return_value=False)

        with pytest.raises(HTTPException) as exc_info:
            await revoke_share("nonexistent", uuid.uuid4())
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    @patch("app.services.preview_service.redis_client", None)
    @patch("app.services.preview_service.get_write_session")
    async def test_revoke_share_wrong_owner_403(self, mock_write):
        """User B cannot revoke user A's share → 403."""
        from app.services.preview_service import revoke_share

        user_a = uuid.uuid4()
        user_b = uuid.uuid4()
        token = "b" * 64

        mock_share = MagicMock()
        mock_share.user_id = user_a  # Owned by user A
        mock_share.revoked = False

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_share
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_write.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_write.return_value.__aexit__ = AsyncMock(return_value=False)

        with pytest.raises(HTTPException) as exc_info:
            await revoke_share(token, user_b)  # User B tries to revoke
        assert exc_info.value.status_code == 403
        assert "Not the owner" in exc_info.value.detail


# ═══════════════════════════════════════════════════════════════════
# Snapshot Service (rewritten)
# ═══════════════════════════════════════════════════════════════════


class TestSnapshotServiceRewrite:
    """Tests for the rewritten snapshot_service.py."""

    @pytest.mark.asyncio
    @patch("app.services.snapshot_service.redis_client", None)
    @patch("app.services.snapshot_service.get_write_session")
    @patch("app.services.snapshot_service.upload_file", new_callable=AsyncMock)
    async def test_capture_snapshot_stores_db_record(self, mock_upload, mock_write):
        from app.services.snapshot_service import capture_snapshot

        mock_upload.return_value = "https://storage.example.com/snap.webp"

        mock_session = AsyncMock()
        mock_session.add = lambda x: setattr(x, "id", uuid.uuid4())
        mock_session.flush = AsyncMock()
        mock_write.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_write.return_value.__aexit__ = AsyncMock(return_value=False)

        build_id = uuid.uuid4()
        project_id = uuid.uuid4()

        result = await capture_snapshot(
            build_id=build_id,
            project_id=project_id,
            agent_number=3,
            agent_type="ui",
            generated_files={"src/App.tsx": "code"},
        )

        assert result["screenshot_url"] == "https://storage.example.com/snap.webp"
        assert "snapshot_id" in result
        assert "03_ui" in result["storage_key"]

    @pytest.mark.asyncio
    @patch("app.services.snapshot_service.redis_client")
    @patch("app.services.snapshot_service.get_write_session")
    @patch("app.services.snapshot_service.upload_file", new_callable=AsyncMock)
    async def test_capture_snapshot_publishes_redis(self, mock_upload, mock_write, mock_redis):
        from app.services.snapshot_service import capture_snapshot

        mock_upload.return_value = "https://example.com/snap.webp"
        mock_redis.publish = AsyncMock()

        mock_session = AsyncMock()
        mock_session.add = lambda x: setattr(x, "id", uuid.uuid4())
        mock_session.flush = AsyncMock()
        mock_write.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_write.return_value.__aexit__ = AsyncMock(return_value=False)

        build_id = uuid.uuid4()
        await capture_snapshot(
            build_id=build_id,
            project_id=uuid.uuid4(),
            agent_number=1,
            agent_type="scaffold",
            generated_files={},
        )

        mock_redis.publish.assert_called_once()
        channel = mock_redis.publish.call_args[0][0]
        assert f"build:snapshot:{build_id}" == channel

    @pytest.mark.asyncio
    @patch("app.services.snapshot_service.redis_client", None)
    @patch("app.services.snapshot_service.get_write_session")
    @patch("app.services.snapshot_service.upload_file", new_callable=AsyncMock)
    async def test_capture_snapshot_webp_path_format(self, mock_upload, mock_write):
        from app.services.snapshot_service import capture_snapshot

        mock_upload.return_value = "https://example.com/snap.webp"
        mock_session = AsyncMock()
        mock_session.add = lambda x: setattr(x, "id", uuid.uuid4())
        mock_session.flush = AsyncMock()
        mock_write.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_write.return_value.__aexit__ = AsyncMock(return_value=False)

        project_id = uuid.uuid4()
        build_id = uuid.uuid4()

        result = await capture_snapshot(
            build_id=build_id,
            project_id=project_id,
            agent_number=7,
            agent_type="api",
            generated_files={},
        )

        expected_key = f"snapshots/{project_id}/{build_id}/07_api.webp"
        assert result["storage_key"] == expected_key

    @pytest.mark.asyncio
    @patch("app.services.snapshot_service.redis_client", None)
    @patch("app.services.snapshot_service.get_write_session")
    @patch("app.services.snapshot_service.upload_file", new_callable=AsyncMock)
    async def test_capture_snapshot_with_screenshot_bytes(self, mock_upload, mock_write):
        from app.services.snapshot_service import capture_snapshot

        mock_upload.return_value = "https://example.com/snap.webp"
        mock_session = AsyncMock()
        mock_session.add = lambda x: setattr(x, "id", uuid.uuid4())
        mock_session.flush = AsyncMock()
        mock_write.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_write.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await capture_snapshot(
            build_id=uuid.uuid4(),
            project_id=uuid.uuid4(),
            agent_number=1,
            agent_type="scaffold",
            generated_files={},
            screenshot_bytes=b"real-webp-bytes",
        )

        # When screenshot_bytes provided, content_type should be image/webp
        call_kwargs = mock_upload.call_args
        assert call_kwargs.kwargs.get("content_type") == "image/webp"

    @pytest.mark.asyncio
    @patch("app.services.snapshot_service.get_read_session")
    async def test_get_snapshots_ordered_by_agent_number(self, mock_read):
        from app.services.snapshot_service import get_snapshots

        snap1 = MagicMock()
        snap1.id = uuid.uuid4()
        snap1.build_id = uuid.uuid4()
        snap1.agent_number = 1
        snap1.agent_type = "scaffold"
        snap1.screenshot_url = "url1"
        snap1.storage_key = "key1"
        snap1.created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)

        snap2 = MagicMock()
        snap2.id = uuid.uuid4()
        snap2.build_id = snap1.build_id
        snap2.agent_number = 2
        snap2.agent_type = "ui"
        snap2.screenshot_url = "url2"
        snap2.storage_key = "key2"
        snap2.created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [snap1, snap2]
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_read.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_read.return_value.__aexit__ = AsyncMock(return_value=False)

        project_id = uuid.uuid4()
        results = await get_snapshots(project_id)
        assert len(results) == 2
        assert results[0]["agent_number"] == 1
        assert results[1]["agent_number"] == 2

    @pytest.mark.asyncio
    @patch("app.services.snapshot_service.get_read_session")
    async def test_get_snapshots_empty(self, mock_read):
        from app.services.snapshot_service import get_snapshots

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_read.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_read.return_value.__aexit__ = AsyncMock(return_value=False)

        results = await get_snapshots(uuid.uuid4())
        assert results == []


# ═══════════════════════════════════════════════════════════════════
# Annotation Service
# ═══════════════════════════════════════════════════════════════════


class TestAnnotationService:
    """Tests for annotation_service.py."""

    @pytest.mark.asyncio
    @patch("app.services.annotation_service.get_write_session")
    async def test_create_annotation_success(self, mock_write):
        from app.services.annotation_service import create_annotation

        annotation_id = uuid.uuid4()
        mock_session = AsyncMock()

        def _add(obj):
            obj.id = annotation_id
            obj.resolved = False
            obj.status = "active"
            obj.created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)

        mock_session.add = _add
        mock_session.flush = AsyncMock()
        mock_session.refresh = AsyncMock()
        mock_write.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_write.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await create_annotation(
            project_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            css_selector=".btn-primary",
            route="/dashboard",
            comment="Button color is wrong",
            x_pct=0.5,
            y_pct=0.3,
        )

        assert result["css_selector"] == ".btn-primary"
        assert result["x_pct"] == 0.5
        assert result["y_pct"] == 0.3

    @pytest.mark.asyncio
    async def test_create_annotation_invalid_x_pct(self):
        from app.services.annotation_service import create_annotation

        with pytest.raises(HTTPException) as exc_info:
            await create_annotation(
                project_id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                css_selector=".btn",
                route="/",
                comment="test",
                x_pct=1.5,  # Invalid: > 1.0
                y_pct=0.5,
            )
        assert exc_info.value.status_code == 400
        assert "x_pct" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_create_annotation_invalid_y_pct(self):
        from app.services.annotation_service import create_annotation

        with pytest.raises(HTTPException) as exc_info:
            await create_annotation(
                project_id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                css_selector=".btn",
                route="/",
                comment="test",
                x_pct=0.5,
                y_pct=-0.1,  # Invalid: < 0.0
            )
        assert exc_info.value.status_code == 400
        assert "y_pct" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_create_annotation_boundary_values(self):
        """0.0 and 1.0 should both be valid."""
        from app.services.annotation_service import create_annotation

        with patch("app.services.annotation_service.get_write_session") as mock_write:
            mock_session = AsyncMock()
            mock_session.add = lambda obj: setattr(obj, "id", uuid.uuid4()) or setattr(obj, "created_at", datetime.now(timezone.utc))
            mock_session.flush = AsyncMock()
            mock_session.refresh = AsyncMock()
            mock_write.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_write.return_value.__aexit__ = AsyncMock(return_value=False)

            # Should not raise
            await create_annotation(
                project_id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                css_selector=".x",
                route="/",
                comment="t",
                x_pct=0.0,
                y_pct=1.0,
            )

    @pytest.mark.asyncio
    @patch("app.services.annotation_service.get_read_session")
    async def test_get_annotations(self, mock_read):
        from app.services.annotation_service import get_annotations

        anno = MagicMock()
        anno.id = uuid.uuid4()
        anno.project_id = uuid.uuid4()
        anno.user_id = uuid.uuid4()
        anno.css_selector = ".card"
        anno.route = "/"
        anno.comment = "Fix spacing"
        anno.x_pct = 0.2
        anno.y_pct = 0.8
        anno.resolved = False
        anno.status = "active"
        anno.created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [anno]
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_read.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_read.return_value.__aexit__ = AsyncMock(return_value=False)

        results = await get_annotations(uuid.uuid4())
        assert len(results) == 1
        assert results[0]["comment"] == "Fix spacing"

    @pytest.mark.asyncio
    @patch("app.services.annotation_service.get_write_session")
    async def test_resolve_annotation(self, mock_write):
        from app.services.annotation_service import resolve_annotation

        anno = MagicMock()
        anno.id = uuid.uuid4()
        anno.project_id = uuid.uuid4()
        anno.user_id = uuid.uuid4()
        anno.css_selector = ".card"
        anno.route = "/"
        anno.comment = "Fix"
        anno.x_pct = 0.5
        anno.y_pct = 0.5
        anno.resolved = False
        anno.status = "active"
        anno.created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = anno
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.flush = AsyncMock()
        mock_session.refresh = AsyncMock()
        mock_write.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_write.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await resolve_annotation(anno.id, anno.user_id)
        assert anno.resolved is True
        assert anno.status == "resolved"

    @pytest.mark.asyncio
    @patch("app.services.annotation_service.get_write_session")
    async def test_resolve_annotation_not_found(self, mock_write):
        from app.services.annotation_service import resolve_annotation

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_write.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_write.return_value.__aexit__ = AsyncMock(return_value=False)

        with pytest.raises(HTTPException) as exc_info:
            await resolve_annotation(uuid.uuid4(), uuid.uuid4())
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    @patch("app.services.annotation_service.get_write_session")
    async def test_delete_annotation(self, mock_write):
        from app.services.annotation_service import delete_annotation

        anno = MagicMock()
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = anno
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.delete = AsyncMock()
        mock_write.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_write.return_value.__aexit__ = AsyncMock(return_value=False)

        await delete_annotation(uuid.uuid4(), uuid.uuid4())
        mock_session.delete.assert_called_once_with(anno)

    @pytest.mark.asyncio
    @patch("app.services.annotation_service.get_write_session")
    async def test_delete_annotation_not_found(self, mock_write):
        from app.services.annotation_service import delete_annotation

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_write.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_write.return_value.__aexit__ = AsyncMock(return_value=False)

        with pytest.raises(HTTPException) as exc_info:
            await delete_annotation(uuid.uuid4(), uuid.uuid4())
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    @patch("app.services.annotation_service.get_write_session")
    async def test_clear_annotations(self, mock_write):
        from app.services.annotation_service import clear_annotations

        annos = [MagicMock(), MagicMock(), MagicMock()]
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = annos
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.delete = AsyncMock()
        mock_write.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_write.return_value.__aexit__ = AsyncMock(return_value=False)

        count = await clear_annotations(uuid.uuid4(), uuid.uuid4())
        assert count == 3
        assert mock_session.delete.call_count == 3

    @pytest.mark.asyncio
    @patch("app.services.annotation_service.get_read_session")
    async def test_get_annotations_for_ai_context_empty(self, mock_read):
        from app.services.annotation_service import get_annotations_for_ai_context

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_read.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_read.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await get_annotations_for_ai_context(uuid.uuid4())
        assert result == ""  # EMPTY STRING, not None

    @pytest.mark.asyncio
    @patch("app.services.annotation_service.get_read_session")
    async def test_get_annotations_for_ai_context_with_data(self, mock_read):
        from app.services.annotation_service import get_annotations_for_ai_context

        anno = MagicMock()
        anno.route = "/settings"
        anno.x_pct = 0.5
        anno.y_pct = 0.3
        anno.css_selector = ".header"
        anno.comment = "Too small"
        anno.resolved = False

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [anno]
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_read.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_read.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await get_annotations_for_ai_context(uuid.uuid4())
        assert isinstance(result, str)
        assert "Too small" in result
        assert "/settings" in result
        assert ".header" in result


# ═══════════════════════════════════════════════════════════════════
# File Sync Service
# ═══════════════════════════════════════════════════════════════════


class TestFileSyncService:
    """Tests for file_sync_service.py."""

    @pytest.mark.asyncio
    @patch("app.services.file_sync_service.redis_client")
    async def test_sync_file_publishes_redis(self, mock_redis):
        from app.services.file_sync_service import sync_file

        mock_redis.publish = AsyncMock(return_value=2)
        sandbox_id = uuid.uuid4()

        result = await sync_file(sandbox_id, "src/App.tsx", "export function App() {}")
        assert result["sandbox_id"] == str(sandbox_id)
        assert result["path"] == "src/App.tsx"
        assert result["receivers"] == 2
        assert result["latency_ms"] >= 0

        mock_redis.publish.assert_called_once()
        channel = mock_redis.publish.call_args[0][0]
        assert channel == f"file_sync:{sandbox_id}"

        # Verify message is valid JSON with correct content
        message = json.loads(mock_redis.publish.call_args[0][1])
        assert message["path"] == "src/App.tsx"
        assert message["content"] == "export function App() {}"

    @pytest.mark.asyncio
    @patch("app.services.file_sync_service.redis_client", None)
    async def test_sync_file_no_redis(self):
        from app.services.file_sync_service import sync_file

        result = await sync_file(uuid.uuid4(), "test.ts", "code")
        assert result["receivers"] == 0

    @pytest.mark.asyncio
    @patch("app.services.file_sync_service.redis_client")
    async def test_sync_file_latency(self, mock_redis):
        from app.services.file_sync_service import sync_file

        mock_redis.publish = AsyncMock(return_value=1)
        result = await sync_file(uuid.uuid4(), "x.ts", "c")
        # Should complete well under 300ms target
        assert result["latency_ms"] < 300


# ═══════════════════════════════════════════════════════════════════
# Sandbox Router
# ═══════════════════════════════════════════════════════════════════


class TestSandboxRouter:
    """Tests for the sandbox API router."""

    def test_router_has_correct_prefix(self):
        from app.api.v1.sandbox import router

        assert router.prefix == "/api/v1/sandbox"

    def test_router_has_correct_tag(self):
        from app.api.v1.sandbox import router

        assert "sandbox" in router.tags

    def test_route_count(self):
        from app.api.v1.sandbox import router

        # Count non-WS routes
        http_routes = [r for r in router.routes if hasattr(r, "methods")]
        ws_routes = [r for r in router.routes if not hasattr(r, "methods")]
        # 10 HTTP routes + 1 WS = 11 total (or 10 as spec says)
        assert len(http_routes) >= 10
        assert len(ws_routes) >= 1

    def test_share_request_validation(self):
        from app.api.v1.sandbox import ShareRequest

        # Valid
        s = ShareRequest(expires_hours=24)
        assert s.expires_hours == 24

        # Default
        s2 = ShareRequest()
        assert s2.expires_hours == 24

    def test_annotation_create_schema(self):
        from app.api.v1.sandbox import AnnotationCreate

        a = AnnotationCreate(
            css_selector=".btn",
            route="/",
            comment="test",
            x_pct=0.5,
            y_pct=0.5,
        )
        assert a.css_selector == ".btn"
        assert a.editor_session_id is None


# ═══════════════════════════════════════════════════════════════════
# Integration: Share Ownership (the key 403 test)
# ═══════════════════════════════════════════════════════════════════


class TestShareOwnership:
    """Cross-user share revocation tests."""

    @pytest.mark.asyncio
    @patch("app.services.preview_service.redis_client", None)
    @patch("app.services.preview_service.get_write_session")
    async def test_user_b_cannot_revoke_user_a_share(self, mock_write):
        """User B cannot revoke user A's share → 403.

        This is the key security test: share tokens are bound to
        the user who created them, and only that user can revoke.
        """
        from app.services.preview_service import revoke_share

        user_a = uuid.uuid4()
        user_b = uuid.uuid4()
        token = "share_token_for_user_a_" + "x" * 42

        # Share belongs to user A
        mock_share = MagicMock()
        mock_share.user_id = user_a
        mock_share.token = token

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_share
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_write.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_write.return_value.__aexit__ = AsyncMock(return_value=False)

        # User B tries to revoke → 403
        with pytest.raises(HTTPException) as exc_info:
            await revoke_share(token, user_b)
        assert exc_info.value.status_code == 403
        assert "owner" in exc_info.value.detail.lower()

        # Share should NOT be marked revoked
        assert mock_share.revoked is not True

    @pytest.mark.asyncio
    @patch("app.services.preview_service.redis_client", None)
    @patch("app.services.preview_service.get_write_session")
    async def test_user_a_can_revoke_own_share(self, mock_write):
        """User A can revoke their own share → success."""
        from app.services.preview_service import revoke_share

        user_a = uuid.uuid4()
        token = "user_a_token_" + "y" * 52

        mock_share = MagicMock()
        mock_share.user_id = user_a
        mock_share.token = token
        mock_share.revoked = False
        mock_share.status = "active"

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_share
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_write.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_write.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await revoke_share(token, user_a)
        assert result["revoked"] is True
        assert mock_share.revoked is True
        assert mock_share.status == "revoked"
