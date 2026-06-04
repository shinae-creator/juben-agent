"""
Agent 矩阵编排器
================
负责三阶段流水线调度：
  1. 爆款策划 Agent → 生成百集主线大纲
  2. 分集架构师 Agent → 切分 100 集卡点清单
  3. 对白生成引擎 → 并发/流式输出完整剧本

使用 LiteLLM 作为 LLM 路由层，支持任意模型切换。
"""

import logging
from typing import Generator, Optional, Callable

import litellm

from config import (
    LLM_MODEL,
    LLM_API_KEY,
    LLM_API_BASE,
    TEMPERATURE_CREATIVE,
    TEMPERATURE_STRUCTURED,
    TEMPERATURE_SCRIPT,
    MAX_TOKENS_OUTLINE,
    MAX_TOKENS_EPISODES,
    MAX_TOKENS_SCRIPT,
    TOTAL_EPISODES,
    EPISODES_PER_BATCH,
)
from .prompts import (
    PLANNER_SYSTEM,
    PLANNER_USER,
    EPISODE_SYSTEM,
    EPISODE_USER,
    DIALOGUE_SYSTEM,
    DIALOGUE_USER,
    DIALOGUE_BATCH_USER,
)

logger = logging.getLogger(__name__)


# ============================================================================
# LiteLLM 统一调用封装
# ============================================================================

def _llm_completion(
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    max_tokens: int,
    stream: bool = False,
) -> str | Generator:
    """
    统一的 LLM 调用入口，封装 LiteLLM completion。

    Args:
        system_prompt: 系统提示词
        user_prompt:  用户消息
        temperature:  生成温度
        max_tokens:   最大输出 token
        stream:       是否流式返回

    Returns:
        str 或 Generator（当 stream=True 时）
    """
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    kwargs = {
        "model": LLM_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": stream,
    }

    if LLM_API_KEY:
        kwargs["api_key"] = LLM_API_KEY
    if LLM_API_BASE:
        kwargs["api_base"] = LLM_API_BASE

    response = litellm.completion(**kwargs)

    if stream:
        return _stream_generator(response)

    return response.choices[0].message.content


def _stream_generator(response) -> Generator[str, None, None]:
    """将 LiteLLM 流式响应转为字符串生成器。"""
    for chunk in response:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


# ============================================================================
# 编排器
# ============================================================================

class Orchestrator:
    """
    Agent 矩阵编排器。

    用法：
        orch = Orchestrator()
        outline = orch.generate_outline("重生之都市神医")
        episodes = orch.generate_episodes(outline)
        for chunk in orch.generate_script_stream("重生之都市神医", episodes):
            print(chunk, end="")
    """

    def __init__(
        self,
        model: Optional[str] = None,
        on_progress: Optional[Callable[[str], None]] = None,
    ):
        """
        Args:
            model:       覆盖默认模型
            on_progress: 进度回调，接收状态描述字符串
        """
        if model:
            global LLM_MODEL
            LLM_MODEL = model
        self.on_progress = on_progress or (lambda msg: logger.info(msg))

    # ------------------------------------------------------------------
    # 阶段一：爆款策划 — 生成百集主线大纲
    # ------------------------------------------------------------------

    def generate_outline(self, topic: str) -> str:
        """
        输入题材，输出完整的百集主线大纲。

        Args:
            topic: 编剧输入的题材/梗概

        Returns:
            结构化大纲文本
        """
        self.on_progress("🧠 爆款策划 Agent 正在构思故事…")
        outline = _llm_completion(
            system_prompt=PLANNER_SYSTEM,
            user_prompt=PLANNER_USER.format(topic=topic),
            temperature=TEMPERATURE_CREATIVE,
            max_tokens=MAX_TOKENS_OUTLINE,
            stream=False,
        )
        self.on_progress("✅ 百集主线大纲已生成，等待编剧审定。")
        return outline

    # ------------------------------------------------------------------
    # 阶段二：分集架构 — 切分 100 集卡点清单
    # ------------------------------------------------------------------

    def generate_episodes(self, outline: str) -> str:
        """
        输入大纲，输出完整的 100 集分集卡点清单。

        如果大纲过长，自动分批调用以绕过 token 限制：
        每次生成 EPISODES_PER_BATCH 集，最后拼接。

        Args:
            outline: 已确认的大纲文本

        Returns:
            100 集分集卡点清单文本
        """
        self.on_progress("📑 分集架构师 Agent 正在切分 100 集卡点…")

        # 首次尝试：让 LLM 一次性输出全部（对强模型可行）
        try:
            episodes = _llm_completion(
                system_prompt=EPISODE_SYSTEM,
                user_prompt=EPISODE_USER.format(outline=outline),
                temperature=TEMPERATURE_STRUCTURED,
                max_tokens=MAX_TOKENS_EPISODES,
                stream=False,
            )
        except Exception as e:
            logger.warning("一次性生成百集失败（可能是 token 限制），回退分批模式: %s", e)
            episodes = self._generate_episodes_batched(outline)

        self.on_progress("✅ 百集分集卡点清单已生成，等待编剧审定。")
        return episodes

    def _generate_episodes_batched(self, outline: str) -> str:
        """分批生成分集卡点（兜底方案）。"""
        batches = []
        batch_count = TOTAL_EPISODES // EPISODES_PER_BATCH

        for i in range(batch_count):
            start = i * EPISODES_PER_BATCH + 1
            end = (i + 1) * EPISODES_PER_BATCH
            self.on_progress(f"  📑 正在生成第 {start}~{end} 集卡点…")

            prompt = (
                EPISODE_USER.format(outline=outline)
                + f"\n\n【特别指令】请只输出第 {start} 集到第 {end} 集的分集卡点。"
            )
            batch_text = _llm_completion(
                system_prompt=EPISODE_SYSTEM,
                user_prompt=prompt,
                temperature=TEMPERATURE_STRUCTURED,
                max_tokens=MAX_TOKENS_EPISODES,
                stream=False,
            )
            batches.append(batch_text)

        return "\n\n".join(batches)

    # ------------------------------------------------------------------
    # 阶段三：对白生成 — 流式输出剧本
    # ------------------------------------------------------------------

    def generate_script_stream(
        self,
        topic: str,
        episode_list: str,
        start_ep: int = 1,
        end_ep: Optional[int] = None,
    ) -> Generator[str, None, None]:
        """
        流式生成完整剧本对白。

        按批次生成：每个 yield 返回一批对白文本，
        Streamlit 端累积展示，形成打字机效果。

        Args:
            topic:         剧名/题材
            episode_list:  已确认的分集卡点清单
            start_ep:      起始集数（默认 1）
            end_ep:        结束集数（默认 100）

        Yields:
            每批对白文本块
        """
        if end_ep is None:
            end_ep = TOTAL_EPISODES

        # 解析分集卡点清单，按「第 X 集」分割
        episode_chunks = self._parse_episode_blocks(episode_list, start_ep, end_ep)

        self.on_progress(f"✍️ 对白引擎启动，即将生成 {start_ep}~{end_ep} 集剧本…")

        # 分批生成（每批 EPISODES_PER_BATCH 集）
        for batch_idx in range(0, len(episode_chunks), EPISODES_PER_BATCH):
            batch = episode_chunks[batch_idx:batch_idx + EPISODES_PER_BATCH]
            batch_text = "\n\n---\n\n".join(batch)

            ep_start = start_ep + batch_idx
            ep_end = min(ep_start + EPISODES_PER_BATCH - 1, end_ep)

            self.on_progress(f"  ✍️ 正在生成第 {ep_start}~{ep_end} 集对白…")

            # 流式调用 LLM 输出本批对白
            user_prompt = DIALOGUE_USER.format(
                topic=topic,
                episode_context=batch_text,
            )

            stream = _llm_completion(
                system_prompt=DIALOGUE_SYSTEM,
                user_prompt=user_prompt,
                temperature=TEMPERATURE_SCRIPT,
                max_tokens=MAX_TOKENS_SCRIPT,
                stream=True,
            )

            # 逐 token yield
            chunk_prefix = f"\n\n## 第 {ep_start}~{ep_end} 集\n\n"
            yield chunk_prefix

            for token in stream:
                yield token

        self.on_progress("✅ 剧本对白全部生成完毕！")

    # ------------------------------------------------------------------
    # 辅助：解析分集卡点为独立块
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_episode_blocks(
        episode_text: str, start_ep: int, end_ep: int
    ) -> list[str]:
        """
        从分集清单文本中提取指定范围的集数块。

        匹配模式：第 X 集 / 第X集 / Episode X 等。
        """
        import re

        # 按「第 X 集」分割
        pattern = r"(第\s*\d+\s*集[\s\S]*?)(?=第\s*\d+\s*集|$)"
        matches = list(re.finditer(pattern, episode_text))

        blocks = []
        for m in matches:
            # 提取集号
            ep_match = re.search(r"第\s*(\d+)\s*集", m.group(1))
            if ep_match:
                ep_num = int(ep_match.group(1))
                if start_ep <= ep_num <= end_ep:
                    blocks.append(m.group(1).strip())

        return blocks


# ============================================================================
# 健康检查
# ============================================================================

def check_llm_connection() -> tuple[bool, str]:
    """
    快速检测 LLM 连接是否正常。

    Returns:
        (是否可用, 消息)
    """
    try:
        _llm_completion(
            system_prompt="你是一个助手。",
            user_prompt="回复'OK'。",
            temperature=0,
            max_tokens=10,
            stream=False,
        )
        return True, f"✅ LLM 连接正常 ({LLM_MODEL})"
    except Exception as e:
        return False, f"❌ LLM 连接失败: {str(e)[:200]}"
