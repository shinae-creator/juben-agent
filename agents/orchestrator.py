"""
Agent 矩阵编排器 v3
===================
v3 修复：
  - 流式对白逐 token yield，真正打字机效果
  - Token 用量在每个 yield 中携带，前端可实时累加
  - 分集 prompt 要求概况+完整100集
"""

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Generator, Optional, Callable, Any

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
    fmt_planner,
    fmt_episode,
    DIALOGUE_SYSTEM,
    DIALOGUE_USER,
)

logger = logging.getLogger(__name__)


# ============================================================================
# 数据结构
# ============================================================================

@dataclass
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class GenResult:
    content: str = ""
    usage: TokenUsage = field(default_factory=TokenUsage)
    elapsed_seconds: float = 0.0

    @property
    def total_tokens(self) -> int:
        return self.usage.total


@dataclass
class ProgressEvent:
    type: str       # "stage" | "step" | "token" | "done" | "error"
    message: str
    data: Any = None


# ============================================================================
# LLM 调用封装
# ============================================================================

def _llm_call(
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    max_tokens: int,
    model: str | None = None,
    api_key: str | None = None,
    api_base: str | None = None,
) -> tuple[str, TokenUsage]:
    """非流式调用 LLM，返回 (内容, Token用量)。"""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    kwargs: dict = {
        "model": model or LLM_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    key = api_key or LLM_API_KEY
    base = api_base or LLM_API_BASE
    if key:   kwargs["api_key"] = key
    if base:  kwargs["api_base"] = base

    response = litellm.completion(**kwargs)
    content = response.choices[0].message.content or ""
    usage = TokenUsage()
    if hasattr(response, "usage") and response.usage:
        usage.input_tokens = response.usage.prompt_tokens or 0
        usage.output_tokens = response.usage.completion_tokens or 0
    else:
        usage.output_tokens = max(len(content) // 2, 1)
        usage.input_tokens = len(system_prompt + user_prompt) // 2
    return content, usage


def _llm_stream(
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    max_tokens: int,
    model: str | None = None,
    api_key: str | None = None,
    api_base: str | None = None,
) -> Generator[tuple[str, Optional[TokenUsage]], None, None]:
    """
    流式调用 LLM，逐个 token yield。

    每个 yield: (token_text, usage_or_None)
    - 中间的 chunk：token_text 是增量文本，usage 为 None
    - 最后一个 chunk：token_text=""，usage 有值
    """
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    kwargs: dict = {
        "model": model or LLM_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
    }
    key = api_key or LLM_API_KEY
    base = api_base or LLM_API_BASE
    if key:   kwargs["api_key"] = key
    if base:  kwargs["api_base"] = base

    response = litellm.completion(**kwargs)

    usage = TokenUsage()
    accumulated = ""

    for chunk in response:
        if chunk.choices and chunk.choices[0].delta.content:
            token = chunk.choices[0].delta.content
            accumulated += token
            yield token, None

        # 流式最后一个 chunk 有时携带 usage
        if hasattr(chunk, "usage") and chunk.usage:
            u = chunk.usage
            usage.input_tokens = u.prompt_tokens or 0
            usage.output_tokens = u.completion_tokens or 0

    # 兜底估算
    if usage.output_tokens == 0 and accumulated:
        usage.output_tokens = max(len(accumulated) // 2, 1)
        usage.input_tokens = len(system_prompt + user_prompt) // 2

    # 结束信号
    yield "", usage


# ============================================================================
# 编排器 v3
# ============================================================================

class Orchestrator:

    def __init__(
        self,
        on_event: Optional[Callable[[ProgressEvent], None]] = None,
        model: str | None = None,
        api_key: str | None = None,
        api_base: str | None = None,
        total_episodes: int = TOTAL_EPISODES,
    ):
        self.on_event = on_event or (lambda ev: None)
        self._cumulative_usage = TokenUsage()
        self._model = model
        self._api_key = api_key
        self._api_base = api_base
        self._total_episodes = total_episodes

    def _emit(self, etype: str, message: str, data: Any = None):
        self.on_event(ProgressEvent(type=etype, message=message, data=data))

    # ------------------------------------------------------------------
    # 阶段一：爆款策划
    # ------------------------------------------------------------------

    def generate_outline(self, topic: str) -> GenResult:
        self._emit("stage", "🧠 爆款策划 Agent 启动")
        self._emit("step", f"分析题材「{topic}」…")
        t0 = time.time()

        system, user = fmt_planner(self._total_episodes, topic)
        content, usage = _llm_call(
            system_prompt=system,
            user_prompt=user,
            temperature=TEMPERATURE_CREATIVE,
            max_tokens=MAX_TOKENS_OUTLINE,
            model=self._model,
            api_key=self._api_key,
            api_base=self._api_base,
        )
        self._cumulative_usage.input_tokens += usage.input_tokens
        self._cumulative_usage.output_tokens += usage.output_tokens
        elapsed = time.time() - t0

        self._emit("token", f"输入 {usage.input_tokens:,} | 输出 {usage.output_tokens:,} | 累计 {self._cumulative_usage.total:,} tokens")
        self._emit("done", f"大纲生成完毕，耗时 {elapsed:.0f}s")
        return GenResult(content=content, usage=usage, elapsed_seconds=elapsed)

    # ------------------------------------------------------------------
    # 阶段二：分集架构
    # ------------------------------------------------------------------

    def generate_episodes(self, outline: str) -> GenResult:
        total = self._total_episodes
        self._emit("stage", "📑 分集架构师 Agent 启动")
        self._emit("step", f"切分 {total} 集卡点清单（JSON 结构化）…")
        t0 = time.time()

        system, user = fmt_episode(total, outline, use_json=True)
        # 额外强制要求（兜底 — JSON 格式也加一句强调）
        extra = (
            f"\n\n【再次强调】输出纯 JSON 数组，共 {total} 个元素。"
            f"以 [ 开头，以 ] 结尾。评分必须自然波动。第 {total} 集四维全部 9-10 分。"
        )
        full_user = user + extra

        try:
            content, usage = _llm_call(
                system_prompt=system,
                user_prompt=full_user,
                temperature=TEMPERATURE_STRUCTURED,
                max_tokens=MAX_TOKENS_EPISODES,
                model=self._model,
                api_key=self._api_key,
                api_base=self._api_base,
            )
        except Exception:
            logger.warning("一次性生成分集失败，回退分批模式")
            content, usage = self._generate_episodes_batched(outline)

        self._cumulative_usage.input_tokens += usage.input_tokens
        self._cumulative_usage.output_tokens += usage.output_tokens
        elapsed = time.time() - t0

        # 统计实际生成集数（JSON 或 旧格式）
        ep_count = _count_episodes(content)
        self._emit("token", f"输入 {usage.input_tokens:,} | 输出 {usage.output_tokens:,} | 累计 {self._cumulative_usage.total:,} tokens | 检测到 {ep_count} 集")
        self._emit("done", f"分集清单生成完毕，共 {ep_count} 集，耗时 {elapsed:.0f}s")
        return GenResult(content=content, usage=usage, elapsed_seconds=elapsed)

    def _generate_episodes_batched(self, outline: str) -> tuple[str, TokenUsage]:
        batches = []
        total_usage = TokenUsage()
        total = self._total_episodes
        batch_count = max(total // EPISODES_PER_BATCH, 1)
        system, base_user = fmt_episode(total, outline, use_json=True)

        for i in range(batch_count):
            start = i * EPISODES_PER_BATCH + 1
            end = min((i + 1) * EPISODES_PER_BATCH, total)
            self._emit("step", f"分批：第 {start}~{end} 集 ({i+1}/{batch_count})")

            extra = (
                f"\n\n【强制要求】只输出第 {start}~{end} 集的 JSON 数组元素。"
                f"以 [ 开头，以 ] 结尾。每个元素含 episode_num/title/summary/cliffhanger + 4 维评分。"
            )
            prompt = base_user + extra
            text, usage = _llm_call(
                system_prompt=system,
                user_prompt=prompt,
                temperature=TEMPERATURE_STRUCTURED,
                max_tokens=MAX_TOKENS_EPISODES // 2,
                model=self._model,
                api_key=self._api_key,
                api_base=self._api_base,
            )
            batches.append(text)
            total_usage.input_tokens += usage.input_tokens
            total_usage.output_tokens += usage.output_tokens

        return "\n".join(batches), total_usage

    # ------------------------------------------------------------------
    # 阶段一（流式版）：逐 token yield，前端实时展示
    # ------------------------------------------------------------------

    def generate_outline_stream(
        self, topic: str
    ) -> Generator[tuple[str, Optional[TokenUsage]], None, None]:
        """流式生成大纲，逐 token yield。前端可实时看到大纲逐字出现。"""
        self._emit("stage", "🧠 爆款策划 Agent 启动（流式）")
        self._emit("step", f"分析题材「{topic}」…")

        system, user = fmt_planner(self._total_episodes, topic)
        for token, final_usage in _llm_stream(
            system_prompt=system,
            user_prompt=user,
            temperature=TEMPERATURE_CREATIVE,
            max_tokens=MAX_TOKENS_OUTLINE,
            model=self._model,
            api_key=self._api_key,
            api_base=self._api_base,
        ):  # ← outline streaming
            if token:
                yield token, None
            if final_usage is not None:
                self._cumulative_usage.input_tokens += final_usage.input_tokens
                self._cumulative_usage.output_tokens += final_usage.output_tokens
                self._emit("token", f"输入 {final_usage.input_tokens:,} | 输出 {final_usage.output_tokens:,} | 累计 {self._cumulative_usage.total:,} tokens")
                self._emit("done", "大纲流式生成完毕")
                yield "", final_usage

    # ------------------------------------------------------------------
    # 阶段二（流式版）：逐 token yield
    # ------------------------------------------------------------------

    def generate_episodes_stream(
        self, outline: str
    ) -> Generator[tuple[str, Optional[TokenUsage]], None, None]:
        """流式生成分集清单，逐 token yield。"""
        total = self._total_episodes
        self._emit("stage", "📑 分集架构师 Agent 启动（流式）")
        self._emit("step", f"切分 {total} 集卡点清单（JSON 结构化）…")

        system, user = fmt_episode(total, outline, use_json=True)
        # 额外强制要求（兜底 — JSON 格式）
        extra = (
            f"\n\n【再次强调】输出纯 JSON 数组，{total} 个元素。"
            f"以 [ 开头，以 ] 结尾。评分必须自然波动。第 {total} 集四维全部 9-10 分。"
        )
        full_user = user + extra

        for token, final_usage in _llm_stream(
            system_prompt=system,
            user_prompt=full_user,
            temperature=TEMPERATURE_STRUCTURED,
            max_tokens=MAX_TOKENS_EPISODES,
            model=self._model,
            api_key=self._api_key,
            api_base=self._api_base,
        ):
            if token:
                yield token, None
            if final_usage is not None:
                self._cumulative_usage.input_tokens += final_usage.input_tokens
                self._cumulative_usage.output_tokens += final_usage.output_tokens
                ep_count = 0  # 流式场景下粗略估计
                self._emit("token", f"输入 {final_usage.input_tokens:,} | 输出 {final_usage.output_tokens:,} | 累计 {self._cumulative_usage.total:,} tokens")
                self._emit("done", "分集清单流式生成完毕")
                yield "", final_usage

    # ------------------------------------------------------------------
    # 阶段三：对白生成 — 逐 token 流式 yield（打字机效果）
    # ------------------------------------------------------------------

    def generate_script_stream(
        self,
        topic: str,
        episode_list: str,
        start_ep: int = 1,
        end_ep: Optional[int] = None,
    ) -> Generator[tuple[str, Optional[TokenUsage]], None, None]:
        """
        流式生成剧本对白，逐 token yield。

        每个 yield 返回 (文本增量, TokenUsage或None)。
        - 文本增量：单个或少量 token 字符
        - TokenUsage 非 None 时表示该批次的 token 统计（用于前端累加）
        """
        if end_ep is None:
            end_ep = self._total_episodes

        episode_chunks = self._parse_episode_blocks(episode_list, start_ep, end_ep)

        total_batches = max((len(episode_chunks) + EPISODES_PER_BATCH - 1) // EPISODES_PER_BATCH, 1)
        self._emit("stage", "✍️ 对白生成引擎启动")
        self._emit("step", f"共 {len(episode_chunks)} 集卡点，分 {total_batches} 批，逐字流式输出…")

        for batch_idx in range(0, len(episode_chunks), EPISODES_PER_BATCH):
            batch = episode_chunks[batch_idx:batch_idx + EPISODES_PER_BATCH]
            batch_text = "\n\n---\n\n".join(batch)

            ep_start = start_ep + batch_idx
            ep_end = min(ep_start + len(batch) - 1, end_ep)
            batch_num = batch_idx // EPISODES_PER_BATCH + 1

            self._emit("step", f"第 {ep_start}~{ep_end} 集对白 ({batch_num}/{total_batches})")

            user_prompt = DIALOGUE_USER.format(
                topic=topic,
                episode_context=batch_text,
            )

            # 先 yield 标题行
            header = f"\n\n## 第 {ep_start}~{ep_end} 集\n\n"
            for ch in header:
                yield ch, None

            # 逐 token 流式 yield
            for token_text, final_usage in _llm_stream(
                system_prompt=DIALOGUE_SYSTEM,
                user_prompt=user_prompt,
                temperature=TEMPERATURE_SCRIPT,
                max_tokens=MAX_TOKENS_SCRIPT,
                model=self._model,
                api_key=self._api_key,
                api_base=self._api_base,
            ):
                if token_text:
                    yield token_text, None
                if final_usage is not None:
                    self._cumulative_usage.input_tokens += final_usage.input_tokens
                    self._cumulative_usage.output_tokens += final_usage.output_tokens
                    self._emit("token", f"第 {ep_start}~{ep_end} 集完成 — 输出 {final_usage.output_tokens:,} | 累计 {self._cumulative_usage.total:,} tokens")
                    yield "", final_usage

        self._emit("done", "全部对白生成完毕！")

    # ------------------------------------------------------------------
    # 属性 & 辅助
    # ------------------------------------------------------------------

    @property
    def cumulative_usage(self) -> TokenUsage:
        return self._cumulative_usage

    def _parse_episode_blocks(self, episode_text: str, start_ep: int, end_ep: int) -> list[str]:
        """解析分集文本为单集 block 列表。

        自动检测格式：JSON（以 [ 开头）→ 旧 markdown。
        """
        stripped = episode_text.strip()
        if stripped.startswith("["):
            # JSON 格式：先转为 markdown 再解析
            try:
                from .episode_parser import parse_episodes, serialize_to_markdown
                total_hint = max(end_ep, self._total_episodes)  # 正确的集数上界
                cards = parse_episodes(episode_text, total_episodes=total_hint)
                episode_text = serialize_to_markdown(cards)
            except Exception:
                logger.warning("JSON→markdown 转换失败，回退原始正则解析")
        return self._parse_episode_blocks_legacy(episode_text, start_ep, end_ep)

    @staticmethod
    def _parse_episode_blocks_legacy(episode_text: str, start_ep: int, end_ep: int) -> list[str]:
        pattern = r"(第\s*\d+\s*集[\s\S]*?)(?=第\s*\d+\s*集|$)"
        blocks = []
        for m in re.finditer(pattern, episode_text):
            ep_match = re.search(r"第\s*(\d+)\s*集", m.group(1))
            if ep_match:
                ep_num = int(ep_match.group(1))
                if start_ep <= ep_num <= end_ep:
                    blocks.append(m.group(1).strip())
        return blocks


def _count_episodes(content: str) -> int:
    """统计分集内容中的集数（兼容 JSON 和旧 markdown 格式）。"""
    # JSON 格式：统计 "episode_num" 出现次数
    json_count = len(re.findall(r'"episode_num"\s*:', content))
    if json_count > 0:
        return json_count
    # 旧格式：统计 "第 X 集" 出现次数
    return len(re.findall(r"第\s*\d+\s*集", content))


def check_llm_connection() -> tuple[bool, str]:
    try:
        content, usage = _llm_call(
            system_prompt="你是一个助手。",
            user_prompt="回复 OK。",
            temperature=0,
            max_tokens=10,
        )
        return True, f"LLM 连接正常 ({LLM_MODEL}), latency tokens={usage.total}"
    except Exception as e:
        return False, f"LLM 连接失败: {str(e)[:200]}"
