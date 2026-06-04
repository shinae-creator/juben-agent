"""
Agent 矩阵 — 短剧剧本全自动生成引擎
====================================

三阶段流水线：
  1. PlannerAgent   — 爆款策划：输入题材 → 输出百集主线大纲
  2. EpisodeAgent   — 分集架构师：输入大纲 → 输出 100 集卡点清单
  3. DialogueAgent  — 酒馆对白引擎：输入分集 → 流式输出完整剧本
"""

from .orchestrator import Orchestrator

__all__ = ["Orchestrator"]
