"""
Agent 鐭╅樀缂栨帓鍣?v3
===================
v3 淇锛?  - 娴佸紡瀵圭櫧閫?token yield锛岀湡姝ｆ墦瀛楁満鏁堟灉
  - Token 鐢ㄩ噺鍦ㄦ瘡涓?yield 涓惡甯︼紝鍓嶇鍙疄鏃剁疮鍔?  - 鍒嗛泦 prompt 瑕佹眰姒傚喌+瀹屾暣100闆?"""

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
    PLANNER_SYSTEM,
    PLANNER_USER,
    EPISODE_SYSTEM,
    EPISODE_USER,
    DIALOGUE_SYSTEM,
    DIALOGUE_USER,
)

logger = logging.getLogger(__name__)


# ============================================================================
# 鏁版嵁缁撴瀯
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
# LLM 璋冪敤灏佽
# ============================================================================

def _llm_call(
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    max_tokens: int,
) -> tuple[str, TokenUsage]:
    """闈炴祦寮忚皟鐢?LLM锛岃繑鍥?(鍐呭, Token鐢ㄩ噺)銆?""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    kwargs: dict = {
        "model": LLM_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    if LLM_API_KEY:  kwargs["api_key"] = LLM_API_KEY
    if LLM_API_BASE: kwargs["api_base"] = LLM_API_BASE

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
) -> Generator[tuple[str, Optional[TokenUsage]], None, None]:
    """
    娴佸紡璋冪敤 LLM锛岄€愪釜 token yield銆?
    姣忎釜 yield: (token_text, usage_or_None)
    - 涓棿鐨?chunk锛歵oken_text 鏄閲忔枃鏈紝usage 涓?None
    - 鏈€鍚庝竴涓?chunk锛歵oken_text=""锛寀sage 鏈夊€?    """
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    kwargs: dict = {
        "model": LLM_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
    }
    if LLM_API_KEY:  kwargs["api_key"] = LLM_API_KEY
    if LLM_API_BASE: kwargs["api_base"] = LLM_API_BASE

    response = litellm.completion(**kwargs)

    usage = TokenUsage()
    accumulated = ""

    for chunk in response:
        if chunk.choices and chunk.choices[0].delta.content:
            token = chunk.choices[0].delta.content
            accumulated += token
            yield token, None

        # 娴佸紡鏈€鍚庝竴涓?chunk 鏈夋椂鎼哄甫 usage
        if hasattr(chunk, "usage") and chunk.usage:
            u = chunk.usage
            usage.input_tokens = u.prompt_tokens or 0
            usage.output_tokens = u.completion_tokens or 0

    # 鍏滃簳浼扮畻
    if usage.output_tokens == 0 and accumulated:
        usage.output_tokens = max(len(accumulated) // 2, 1)
        usage.input_tokens = len(system_prompt + user_prompt) // 2

    # 缁撴潫淇″彿
    yield "", usage


# ============================================================================
# 缂栨帓鍣?v3
# ============================================================================

class Orchestrator:

    def __init__(self, on_event: Optional[Callable[[ProgressEvent], None]] = None):
        self.on_event = on_event or (lambda ev: None)
        self._cumulative_usage = TokenUsage()

    def _emit(self, etype: str, message: str, data: Any = None):
        self.on_event(ProgressEvent(type=etype, message=message, data=data))

    # ------------------------------------------------------------------
    # 闃舵涓€锛氱垎娆剧瓥鍒?    # ------------------------------------------------------------------

    def generate_outline(self, topic: str) -> GenResult:
        self._emit("stage", "馃 鐖嗘绛栧垝 Agent 鍚姩")
        self._emit("step", f"鍒嗘瀽棰樻潗銆寋topic}銆嶁€?)
        t0 = time.time()

        content, usage = _llm_call(
            system_prompt=PLANNER_SYSTEM,
            user_prompt=PLANNER_USER.format(topic=topic),
            temperature=TEMPERATURE_CREATIVE,
            max_tokens=MAX_TOKENS_OUTLINE,
        )
        self._cumulative_usage.input_tokens += usage.input_tokens
        self._cumulative_usage.output_tokens += usage.output_tokens
        elapsed = time.time() - t0

        self._emit("token", f"杈撳叆 {usage.input_tokens:,} | 杈撳嚭 {usage.output_tokens:,} | 绱 {self._cumulative_usage.total:,} tokens")
        self._emit("done", f"澶х翰鐢熸垚瀹屾瘯锛岃€楁椂 {elapsed:.0f}s")
        return GenResult(content=content, usage=usage, elapsed_seconds=elapsed)

    # ------------------------------------------------------------------
    # 闃舵浜岋細鍒嗛泦鏋舵瀯
    # ------------------------------------------------------------------

    def generate_episodes(self, outline: str) -> GenResult:
        self._emit("stage", "馃搼 鍒嗛泦鏋舵瀯甯?Agent 鍚姩")
        self._emit("step", "鍒囧垎 100 闆嗗崱鐐规竻鍗曗€?)
        t0 = time.time()

        # 鎷兼帴棰濆鎸囦护锛氳姹傛鍐?+ 瀹屾暣 100 闆?        extra = (
            f"\n\n銆愬己鍒惰姹傘€慭n"
            f"1. 寮€澶村繀椤昏緭鍑轰竴琛屾鍐碉細銆屾湰鍓у叡 100 闆嗭紝鍒嗕负 10 涓钀斤紝姣?10 闆嗕负涓€涓珮娼崟鍏冦€傘€峔n"
            f"2. 蹇呴』瀹屾暣杈撳嚭鍏ㄩ儴 {TOTAL_EPISODES} 闆嗭紝涓€闆嗛兘涓嶈兘灏戯紝绂佹鐪佺暐鍜岀缉鍐欍€俓n"
            f"3. 姣忛泦涓ユ牸鎸夈€岀 X 闆嗭細鏍稿績浜嬩欢 / 鍐茬獊鐐?/ 缁撳熬閽╁瓙銆嶆牸寮忚緭鍑恒€俓n"
        )
        full_user = EPISODE_USER.format(outline=outline) + extra

        try:
            content, usage = _llm_call(
                system_prompt=EPISODE_SYSTEM,
                user_prompt=full_user,
                temperature=TEMPERATURE_STRUCTURED,
                max_tokens=MAX_TOKENS_EPISODES,
            )
        except Exception:
            logger.warning("涓€娆℃€х敓鎴愮櫨闆嗗け璐ワ紝鍥為€€鍒嗘壒妯″紡")
            content, usage = self._generate_episodes_batched(outline)

        self._cumulative_usage.input_tokens += usage.input_tokens
        self._cumulative_usage.output_tokens += usage.output_tokens
        elapsed = time.time() - t0

        # 缁熻瀹為檯鐢熸垚闆嗘暟
        ep_count = len(re.findall(r"绗琝s*\d+\s*闆?, content))
        self._emit("token", f"杈撳叆 {usage.input_tokens:,} | 杈撳嚭 {usage.output_tokens:,} | 绱 {self._cumulative_usage.total:,} tokens | 妫€娴嬪埌 {ep_count} 闆?)
        self._emit("done", f"鍒嗛泦娓呭崟鐢熸垚瀹屾瘯锛屽叡 {ep_count} 闆嗭紝鑰楁椂 {elapsed:.0f}s")
        return GenResult(content=content, usage=usage, elapsed_seconds=elapsed)

    def _generate_episodes_batched(self, outline: str) -> tuple[str, TokenUsage]:
        batches = []
        total_usage = TokenUsage()
        batch_count = TOTAL_EPISODES // EPISODES_PER_BATCH

        for i in range(batch_count):
            start = i * EPISODES_PER_BATCH + 1
            end = (i + 1) * EPISODES_PER_BATCH
            self._emit("step", f"鍒嗘壒锛氱 {start}~{end} 闆?({i+1}/{batch_count})")

            extra = (
                f"\n\n銆愬己鍒惰姹傘€戝彧杈撳嚭绗?{start}~{end} 闆嗭紝"
                f"姣忛泦鎸夈€岀 X 闆嗭細鏍稿績浜嬩欢 / 鍐茬獊鐐?/ 缁撳熬閽╁瓙銆嶆牸寮忋€傜姝㈢渷鐣ャ€?
            )
            prompt = EPISODE_USER.format(outline=outline) + extra
            text, usage = _llm_call(
                system_prompt=EPISODE_SYSTEM,
                user_prompt=prompt,
                temperature=TEMPERATURE_STRUCTURED,
                max_tokens=MAX_TOKENS_EPISODES // 2,
                stream=False,
            )
            batches.append(text)
            total_usage.input_tokens += usage.input_tokens
            total_usage.output_tokens += usage.output_tokens

        return "\n\n".join(batches), total_usage

    # ------------------------------------------------------------------
    # 闃舵涓夛細瀵圭櫧鐢熸垚 鈥?閫?token 娴佸紡 yield锛堟墦瀛楁満鏁堟灉锛?    # ------------------------------------------------------------------

    def generate_script_stream(
        self,
        topic: str,
        episode_list: str,
        start_ep: int = 1,
        end_ep: Optional[int] = None,
    ) -> Generator[tuple[str, Optional[TokenUsage]], None, None]:
        """
        娴佸紡鐢熸垚鍓ф湰瀵圭櫧锛岄€?token yield銆?
        姣忎釜 yield 杩斿洖 (鏂囨湰澧為噺, TokenUsage鎴朜one)銆?        - 鏂囨湰澧為噺锛氬崟涓垨灏戦噺 token 瀛楃
        - TokenUsage 闈?None 鏃惰〃绀鸿鎵规鐨?token 缁熻锛堢敤浜庡墠绔疮鍔狅級
        """
        if end_ep is None:
            end_ep = TOTAL_EPISODES

        episode_chunks = self._parse_episode_blocks(episode_list, start_ep, end_ep)

        total_batches = max((len(episode_chunks) + EPISODES_PER_BATCH - 1) // EPISODES_PER_BATCH, 1)
        self._emit("stage", "鉁嶏笍 瀵圭櫧鐢熸垚寮曟搸鍚姩")
        self._emit("step", f"鍏?{len(episode_chunks)} 闆嗗崱鐐癸紝鍒?{total_batches} 鎵癸紝閫愬瓧娴佸紡杈撳嚭鈥?)

        for batch_idx in range(0, len(episode_chunks), EPISODES_PER_BATCH):
            batch = episode_chunks[batch_idx:batch_idx + EPISODES_PER_BATCH]
            batch_text = "\n\n---\n\n".join(batch)

            ep_start = start_ep + batch_idx
            ep_end = min(ep_start + len(batch) - 1, end_ep)
            batch_num = batch_idx // EPISODES_PER_BATCH + 1

            self._emit("step", f"绗?{ep_start}~{ep_end} 闆嗗鐧?({batch_num}/{total_batches})")

            user_prompt = DIALOGUE_USER.format(
                topic=topic,
                episode_context=batch_text,
            )

            # 鍏?yield 鏍囬琛?            header = f"\n\n## 绗?{ep_start}~{ep_end} 闆哱n\n"
            for ch in header:
                yield ch, None

            # 閫?token 娴佸紡 yield
            for token_text, final_usage in _llm_stream(
                system_prompt=DIALOGUE_SYSTEM,
                user_prompt=user_prompt,
                temperature=TEMPERATURE_SCRIPT,
                max_tokens=MAX_TOKENS_SCRIPT,
            ):
                if token_text:
                    yield token_text, None
                if final_usage is not None:
                    self._cumulative_usage.input_tokens += final_usage.input_tokens
                    self._cumulative_usage.output_tokens += final_usage.output_tokens
                    self._emit("token", f"绗?{ep_start}~{ep_end} 闆嗗畬鎴?鈥?杈撳嚭 {final_usage.output_tokens:,} | 绱 {self._cumulative_usage.total:,} tokens")
                    yield "", final_usage

        self._emit("done", "鍏ㄩ儴瀵圭櫧鐢熸垚瀹屾瘯锛?)

    # ------------------------------------------------------------------
    # 灞炴€?& 杈呭姪
    # ------------------------------------------------------------------

    @property
    def cumulative_usage(self) -> TokenUsage:
        return self._cumulative_usage

    @staticmethod
    def _parse_episode_blocks(episode_text: str, start_ep: int, end_ep: int) -> list[str]:
        pattern = r"(绗琝s*\d+\s*闆哰\s\S]*?)(?=绗琝s*\d+\s*闆唡$)"
        blocks = []
        for m in re.finditer(pattern, episode_text):
            ep_match = re.search(r"绗琝s*(\d+)\s*闆?, m.group(1))
            if ep_match:
                ep_num = int(ep_match.group(1))
                if start_ep <= ep_num <= end_ep:
                    blocks.append(m.group(1).strip())
        return blocks


def check_llm_connection() -> tuple[bool, str]:
    try:
        content, usage = _llm_call(
            system_prompt="浣犳槸涓€涓姪鎵嬨€?,
            user_prompt="鍥炲 OK銆?,
            temperature=0,
            max_tokens=10,
        )
        return True, f"LLM 杩炴帴姝ｅ父 ({LLM_MODEL}), latency tokens={usage.total}"
    except Exception as e:
        return False, f"LLM 杩炴帴澶辫触: {str(e)[:200]}"
