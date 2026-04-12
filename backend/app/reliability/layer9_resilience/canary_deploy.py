"""Layer 9 — Canary Deploy: progressive rollout 5% → 25% → 100% with auto-rollback."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)

ERROR_RATE_THRESHOLD = 0.001  # 0.1% — auto-rollback if exceeded


class CanaryStage(str, Enum):
    CANARY_5 = "canary_5"
    CANARY_25 = "canary_25"
    FULL_100 = "full_100"
    ROLLED_BACK = "rolled_back"


STAGE_TRAFFIC = {
    CanaryStage.CANARY_5: 5,
    CanaryStage.CANARY_25: 25,
    CanaryStage.FULL_100: 100,
}

STAGE_ORDER = [CanaryStage.CANARY_5, CanaryStage.CANARY_25, CanaryStage.FULL_100]


@dataclass
class CanaryMetrics:
    total_requests: int = 0
    error_count: int = 0

    @property
    def error_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.error_count / self.total_requests


@dataclass
class CanaryResult:
    stage: CanaryStage
    traffic_percent: int
    metrics: CanaryMetrics
    rolled_back: bool = False
    rollback_reason: str = ""
    promoted: bool = False


class CanaryDeployer:
    """Progressive canary deployment manager.

    Stages: 5% → 25% → 100% traffic.
    Auto-rollback at error_rate >= 0.1%.
    """

    def __init__(self, deployment_id: str) -> None:
        self.deployment_id = deployment_id
        self.current_stage = CanaryStage.CANARY_5
        self.history: list[CanaryResult] = []
        self._rolled_back = False

    @property
    def is_rolled_back(self) -> bool:
        return self._rolled_back

    @property
    def is_fully_deployed(self) -> bool:
        return self.current_stage == CanaryStage.FULL_100 and not self._rolled_back

    @property
    def traffic_percent(self) -> int:
        if self._rolled_back:
            return 0
        return STAGE_TRAFFIC.get(self.current_stage, 0)

    def evaluate_stage(self, metrics: CanaryMetrics) -> CanaryResult:
        """Evaluate current stage metrics and decide: promote or rollback.

        Args:
            metrics: Request/error counts for the current canary stage.

        Returns:
            CanaryResult indicating what happened.
        """
        if self._rolled_back:
            return CanaryResult(
                stage=CanaryStage.ROLLED_BACK,
                traffic_percent=0,
                metrics=metrics,
                rolled_back=True,
                rollback_reason="already_rolled_back",
            )

        traffic = STAGE_TRAFFIC.get(self.current_stage, 0)

        # Check error rate threshold
        if metrics.error_rate >= ERROR_RATE_THRESHOLD:
            self._rolled_back = True
            self.current_stage = CanaryStage.ROLLED_BACK
            result = CanaryResult(
                stage=CanaryStage.ROLLED_BACK,
                traffic_percent=0,
                metrics=metrics,
                rolled_back=True,
                rollback_reason=(
                    f"error_rate_{metrics.error_rate:.4f}_exceeds_threshold_"
                    f"{ERROR_RATE_THRESHOLD}"
                ),
            )
            self.history.append(result)
            logger.warning(
                "Canary %s: ROLLBACK at %d%% traffic — error rate %.4f >= %.4f",
                self.deployment_id, traffic, metrics.error_rate, ERROR_RATE_THRESHOLD,
            )
            return result

        # Promote to next stage
        result = CanaryResult(
            stage=self.current_stage,
            traffic_percent=traffic,
            metrics=metrics,
            promoted=True,
        )
        self.history.append(result)

        current_idx = STAGE_ORDER.index(self.current_stage)
        if current_idx < len(STAGE_ORDER) - 1:
            self.current_stage = STAGE_ORDER[current_idx + 1]
            logger.info(
                "Canary %s: promoted from %d%% to %d%% traffic",
                self.deployment_id, traffic,
                STAGE_TRAFFIC[self.current_stage],
            )
        else:
            logger.info(
                "Canary %s: fully deployed at 100%%",
                self.deployment_id,
            )

        return result

    def force_rollback(self, reason: str = "manual") -> CanaryResult:
        """Force an immediate rollback regardless of metrics."""
        traffic = self.traffic_percent
        self._rolled_back = True
        self.current_stage = CanaryStage.ROLLED_BACK
        result = CanaryResult(
            stage=CanaryStage.ROLLED_BACK,
            traffic_percent=0,
            metrics=CanaryMetrics(),
            rolled_back=True,
            rollback_reason=reason,
        )
        self.history.append(result)
        logger.warning(
            "Canary %s: forced rollback from %d%% — %s",
            self.deployment_id, traffic, reason,
        )
        return result
