"""Layer 8 — Post-build verification suite.

Called sequentially from ReviewAgent:
  visual_regression → sast → perf → a11y → dead_code → seed
"""
