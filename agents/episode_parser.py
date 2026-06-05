"""
分集结构化解析器
===============
将 LLM 输出的 JSON（或旧格式 markdown）解析为 List[EpisodeCard]，
并支持反向序列化为兼容格式文本。

核心策略：
  1. JSON 优先解析（处理 ```json 围栏、尾逗号、截断）
  2. 正则回退（旧格式 markdown → 默认评分 5）
  3. 缺失集数补齐（placeholder 卡片）
"""

import json
import logging
import re
from typing import Optional

from .schemas import EpisodeCard

logger = logging.getLogger(__name__)


# ────────────────────────────── 主入口 ──────────────────────────────

def parse_episodes(raw_text: str, total_episodes: int) -> list[EpisodeCard]:
    """
    将 LLM 原始输出解析为 EpisodeCard 列表。

    策略：JSON → 正则 → 补齐
    始终返回长度为 total_episodes 的列表。
    """
    # 1. 尝试 JSON
    items = _parse_json_flexible(raw_text)
    if items:
        cards = []
        for item in items:
            try:
                cards.append(EpisodeCard(**item))
            except Exception as exc:
                logger.warning(f"EpisodeCard 构造失败: {exc} — item={item}")
                # 尝试用 episode_num 创建占位卡片
                ep_num = item.get("episode_num", 0)
                cards.append(EpisodeCard(episode_num=ep_num))
        if cards:
            return _fill_missing(cards, total_episodes)
        logger.warning("JSON 列表为空，回退正则解析")

    # 2. 回退正则
    cards = _parse_legacy_markdown(raw_text, total_episodes)
    if cards:
        return _fill_missing(cards, total_episodes)

    # 3. 完全失败 → 全占位卡片
    logger.warning("无法从任何格式解析分集，生成占位卡片")
    return [EpisodeCard(episode_num=i) for i in range(1, total_episodes + 1)]


def serialize_to_markdown(cards: list[EpisodeCard]) -> str:
    """
    将 EpisodeCard 列表序列化为兼容旧格式的 markdown 文本，
    确保 Orchestrator._parse_episode_blocks() 可正确切分。
    """
    total = len(cards)
    groups = total // 10

    lines = [f"【本剧共 {total} 集 | 分 {groups} 个段落单元 | 每 10 集为一个高潮段落】", ""]
    for card in cards:
        ep = card.episode_num
        climax_tag = ""
        if ep % 10 == 0 or ep == total:
            climax_tag = " ★ 高潮集"
            if ep == total:
                climax_tag += " · 大结局"

        lines.append(f"第 {ep} 集：{climax_tag}")
        lines.append(f"  🎯 核心事件：{card.summary}")
        lines.append(
            f"  ⚡ 冲突点：冲突烈度 {card.conflict_intensity}/10，"
            f"爽感 {card.pleasure_index}/10"
        )
        lines.append(f"  🪝 结尾钩子：{card.cliffhanger}")
        lines.append(f"  📊 评分：冲突{card.conflict_intensity} "
                     f"爽感{card.pleasure_index} "
                     f"悬念{card.hook_strength} "
                     f"情感{card.emotional_resonance} "
                     f"| 均分{card.avg_score:.1f}")
        lines.append("")
    return "\n".join(lines)


# ────────────────────────────── JSON 解析 ──────────────────────────────

def _parse_json_flexible(text: str) -> Optional[list[dict]]:
    """
    从文本中提取 JSON 数组，处理常见 LLM 输出问题：
    - ```json ... ``` 代码围栏
    - 尾逗号
    - 部分截断
    """
    if not text.strip():
        return None

    # 去除 markdown 代码围栏
    cleaned = text.strip()
    if cleaned.startswith("```"):
        # 去掉 ```json（可能有或没有 json 标记）
        cleaned = re.sub(r"^```(?:json)?\s*\n?", "", cleaned, count=1)
        cleaned = re.sub(r"\n?```\s*$", "", cleaned, count=1)

    # 找到 JSON 数组
    array_match = re.search(r"\[[\s\S]*\]", cleaned)
    if not array_match:
        return None

    json_str = array_match.group(0)

    # 尝试直接解析
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        pass

    # 尝试修复：去除尾逗号
    fixed = re.sub(r",\s*\]", "]", json_str)
    fixed = re.sub(r",\s*}", "}", fixed)
    try:
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass

    # 最后手段：逐个对象抢救
    return _salvage_objects(cleaned)


def _salvage_objects(text: str) -> Optional[list[dict]]:
    """逐个匹配 {...} 对象，抢救可解析的部分。"""
    objects = []
    # 匹配顶层 JSON 对象（简单方式，不处理嵌套）
    for match in re.finditer(r"\{[^{}]*\}", text):
        obj_str = match.group(0)
        # 修复尾逗号
        obj_str = re.sub(r",\s*}", "}", obj_str)
        try:
            obj = json.loads(obj_str)
            if isinstance(obj, dict) and "episode_num" in obj:
                objects.append(obj)
        except json.JSONDecodeError:
            continue
    return objects if objects else None


# ────────────────────────────── 旧格式回退 ──────────────────────────────

def _parse_legacy_markdown(text: str, total_episodes: int) -> list[EpisodeCard]:
    """
    从旧格式 markdown 中正则提取分集信息。

    旧格式示例：
    第 1 集：
      🎯 核心事件：...
      ⚡ 冲突点：...
      🪝 结尾钩子：...
    """
    cards = []
    # 匹配每一集 block
    pattern = (
        r"第\s*(\d+)\s*集[：:]?\s*\n?"
        r"(.*?)(?=第\s*\d+\s*集|$)"
    )
    for match in re.finditer(pattern, text, re.DOTALL):
        ep_num = int(match.group(1))
        block = match.group(2).strip()

        # 提取各字段
        title = ""
        summary = ""
        cliffhanger = ""

        # 标题行（第一行非空且不含 emoji 的文本）
        title_match = re.search(
            r"^(?:★\s*(?:高潮集|大结局)[·\s]*)?(.+?)$", block, re.MULTILINE
        )
        if title_match:
            candidate = title_match.group(1).strip()
            # 过滤掉 emoji 字段行
            if not re.match(r"[🎯⚡🪝📊]", candidate) and len(candidate) < 40:
                title = candidate

        # 核心事件 / 剧情概要
        ev_match = re.search(r"🎯\s*核心事件[：:]\s*(.+?)(?:\n|$)", block)
        if ev_match:
            summary = ev_match.group(1).strip()

        # 结尾钩子
        hk_match = re.search(r"🪝\s*结尾钩子[：:]\s*(.+?)(?:\n|$)", block)
        if hk_match:
            cliffhanger = hk_match.group(1).strip()

        cards.append(EpisodeCard(
            episode_num=ep_num,
            title=title,
            summary=summary or block[:100].replace("\n", " "),
            cliffhanger=cliffhanger,
            conflict_intensity=5,
            pleasure_index=5,
            hook_strength=5,
            emotional_resonance=5,
        ))

    return cards


# ────────────────────────────── 辅助 ──────────────────────────────

def _fill_missing(cards: list[EpisodeCard], total: int) -> list[EpisodeCard]:
    """补齐缺失的集数，确保长度为 total。"""
    existing = {c.episode_num for c in cards}
    for ep in range(1, total + 1):
        if ep not in existing:
            cards.append(EpisodeCard(episode_num=ep))
    cards.sort(key=lambda c: c.episode_num)
    return cards[:total]
