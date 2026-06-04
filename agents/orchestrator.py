"""
Agent 鐭╅樀缂栨帓鍣?v2
===================
涓夐樁娈垫祦姘寸嚎 + Token 鐢ㄩ噺杩借釜 + 瀹炴椂杩涘害鍥炶皟銆?
鐩告瘮 v1 鐨勫寮猴細
  - GenResult 缁熶竴杩斿洖鍐呭 + Token 鐢ㄩ噺
  - on_progress 鍥炶皟鏀寔澶氬眰鐘舵€侊紙闃舵/瀛愭楠?token锛?  - 娴佸紡鐢熸垚鏈熼棿鍙疄鏃舵姤鍛?token 娑堣€?"""

import logging
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
    """鍗曟 LLM 璋冪敤鐨?Token 缁熻"""
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class GenResult:
    """缁熶竴鐨勭敓鎴愮粨鏋?""
    content: str = ""
    usage: TokenUsage = field(default_factory=TokenUsage)
    elapsed_seconds: float = 0.0

    @property
    def total_tokens(self) -> int:
        return self.usage.total


@dataclass
class ProgressEvent:
    """杩涘害浜嬩欢锛屼緵 Streamlit 绔秷璐?""
    type: str       # "stage" | "step" | "token" | "done" | "error"
    message: str
    data: Any = None


# ============================================================================
# LiteLLM 灏佽锛堝甫 Token 杩借釜锛?# ============================================================================

def _llm_completion(
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    max_tokens: int,
    stream: bool = False,
    on_chunk: Optional[Callable[[str], None]] = None,
) -> tuple[str, TokenUsage]:
    """
    璋冪敤 LLM锛岃繑鍥?(鍐呭, Token鐢ㄩ噺)銆?
    褰?stream=True 鏃讹紝on_chunk 姣忔敹鍒颁竴涓?token 灏卞洖璋冦€?    """
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    kwargs: dict = {
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

    usage = TokenUsage()

    if stream:
        accumulated = ""
        for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                token = chunk.choices[0].delta.content
                accumulated += token
                if on_chunk:
                    on_chunk(token)
            # 娴佸紡鍝嶅簲鍙兘鍦ㄦ渶鍚庝竴涓?chunk 鎼哄甫 usage
            if hasattr(chunk, "usage") and chunk.usage:
                usage.input_tokens = getattr(chunk.usage, "prompt_tokens", 0) or 0
                usage.output_tokens = getattr(chunk.usage, "completion_tokens", 0) or 0

        # 濡傛灉娴佸紡鏈惡甯?usage锛屽垯浼扮畻
        if usage.output_tokens == 0 and accumulated:
            usage.output_tokens = len(accumulated) // 2  # 绮楃暐浼扮畻锛堜腑鏂囩害 2 chars/token锛?            usage.input_tokens = len(system_prompt + user_prompt) // 2

        return accumulated, usage
    else:
        content = response.choices[0].message.content or ""
        if hasattr(response, "usage") and response.usage:
            usage.input_tokens = response.usage.prompt_tokens or 0
            usage.output_tokens = response.usage.completion_tokens or 0
        else:
            usage.output_tokens = len(content) // 2
            usage.input_tokens = len(system_prompt + user_prompt) // 2
        return content, usage


# ============================================================================
# 缂栨帓鍣?v2
# ============================================================================

class Orchestrator:
    """Agent 鐭╅樀缂栨帓鍣紙甯﹁繘搴︿簨浠跺拰 Token 杩借釜锛?""

    def __init__(
        self,
        on_event: Optional[Callable[[ProgressEvent], None]] = None,
    ):
        """
        Args:
            on_event: 杩涘害浜嬩欢鍥炶皟锛屾瘡鍙戠敓浜嬩欢鏃惰皟鐢ㄣ€?                      閫傚悎 Streamlit 绔啓鍏?session_state 鏃ュ織鍒楄〃銆?        """
        self.on_event = on_event or (lambda ev: None)
        self._cumulative_usage = TokenUsage()
        self._stage_start = 0.0

    def _emit(self, etype: str, message: str, data: Any = None):
        self.on_event(ProgressEvent(type=etype, message=message, data=data))

    # ------------------------------------------------------------------
    # 闃舵涓€锛氱垎娆剧瓥鍒?    # ------------------------------------------------------------------

    def generate_outline(self, topic: str) -> GenResult:
        self._emit("stage", "馃 鐖嗘绛栧垝 Agent 鍚姩")
        self._emit("step", f"姝ｅ湪鍒嗘瀽棰樻潗銆寋topic}銆嶁€?)
        t0 = time.time()

        content, usage = _llm_completion(
            system_prompt=PLANNER_SYSTEM,
            user_prompt=PLANNER_USER.format(topic=topic),
            temperature=TEMPERATURE_CREATIVE,
            max_tokens=MAX_TOKENS_OUTLINE,
            stream=False,
        )

        self._cumulative_usage.input_tokens += usage.input_tokens
        self._cumulative_usage.output_tokens += usage.output_tokens

        elapsed = time.time() - t0
        self._emit("token", f"澶х翰鐢熸垚瀹屾垚 鈥?杈撳叆 {usage.input_tokens} tokens锛岃緭鍑?{usage.output_tokens} tokens")
        self._emit("done", f"澶х翰鐢熸垚瀹屾瘯锛岃€楁椂 {elapsed:.0f}s")

        return GenResult(content=content, usage=usage, elapsed_seconds=elapsed)

    # ------------------------------------------------------------------
    # 闃舵浜岋細鍒嗛泦鏋舵瀯
    # ------------------------------------------------------------------

    def generate_episodes(self, outline: str) -> GenResult:
        self._emit("stage", "馃搼 鍒嗛泦鏋舵瀯甯?Agent 鍚姩")
        self._emit("step", "姝ｅ湪灏嗗ぇ绾插垏鍒嗕负 100 闆嗗崱鐐规竻鍗曗€?)
        t0 = time.time()

        try:
            content, usage = _llm_completion(
                system_prompt=EPISODE_SYSTEM,
                user_prompt=EPISODE_USER.format(outline=outline),
                temperature=TEMPERATURE_STRUCTURED,
                max_tokens=MAX_TOKENS_EPISODES,
                stream=False,
            )
        except Exception as e:
            logger.warning("涓€娆℃€х敓鎴愮櫨闆嗗け璐ワ紝鍥為€€鍒嗘壒妯″紡: %s", e)
            content, usage = self._generate_episodes_batched(outline)

        self._cumulative_usage.input_tokens += usage.input_tokens
        self._cumulative_usage.output_tokens += usage.output_tokens

        elapsed = time.time() - t0
        self._emit("token", f"鍒嗛泦瀹屾垚 鈥?杈撳叆 {usage.input_tokens} tokens锛岃緭鍑?{usage.output_tokens} tokens")
        self._emit("done", f"鐧鹃泦鍒嗛泦娓呭崟鐢熸垚瀹屾瘯锛岃€楁椂 {elapsed:.0f}s")

        return GenResult(content=content, usage=usage, elapsed_seconds=elapsed)

    def _generate_episodes_batched(self, outline: str) -> tuple[str, TokenUsage]:
        """鍒嗘壒鐢熸垚鍒嗛泦鍗＄偣锛堝甫杩涘害锛夈€?""
        batches = []
        total_usage = TokenUsage()
        batch_count = TOTAL_EPISODES // EPISODES_PER_BATCH

        for i in range(batch_count):
            start = i * EPISODES_PER_BATCH + 1
            end = (i + 1) * EPISODES_PER_BATCH
            self._emit("step", f"姝ｅ湪鐢熸垚绗?{start}~{end} 闆嗗崱鐐光€?({i+1}/{batch_count})")

            prompt = (
                EPISODE_USER.format(outline=outline)
                + f"\n\n銆愮壒鍒寚浠ゃ€戣鍙緭鍑虹 {start} 闆嗗埌绗?{end} 闆嗙殑鍒嗛泦鍗＄偣銆?
            )
            batch_text, usage = _llm_completion(
                system_prompt=EPISODE_SYSTEM,
                user_prompt=prompt,
                temperature=TEMPERATURE_STRUCTURED,
                max_tokens=MAX_TOKENS_EPISODES // 2,
                stream=False,
            )
            batches.append(batch_text)
            total_usage.input_tokens += usage.input_tokens
            total_usage.output_tokens += usage.output_tokens

        return "\n\n".join(batches), total_usage

    # ------------------------------------------------------------------
    # 闃舵涓夛細瀵圭櫧鐢熸垚锛堟祦寮忥級
    # ------------------------------------------------------------------

    def generate_script_stream(
        self,
        topic: str,
        episode_list: str,
        start_ep: int = 1,
        end_ep: Optional[int] = None,
    ) -> Generator[tuple[str, Optional[TokenUsage]], None, None]:
        """
        娴佸紡鐢熸垚瀹屾暣鍓ф湰瀵圭櫧銆?
        姣忎釜 yield 杩斿洖 (鏂囨湰鍧? TokenUsage鎴朜one)銆?        褰?TokenUsage 闈?None 鏃惰〃绀鸿鎵规鐨?token 缁熻銆?
        Usage:
            for chunk, batch_usage in orch.generate_script_stream(...):
                accumulated += chunk
                if batch_usage:
                    total_tokens += batch_usage.total
        """
        if end_ep is None:
            end_ep = TOTAL_EPISODES

        episode_chunks = self._parse_episode_blocks(episode_list, start_ep, end_ep)

        self._emit("stage", "鉁嶏笍 瀵圭櫧鐢熸垚寮曟搸鍚姩")
        self._emit("step", f"鍗冲皢鐢熸垚 {start_ep}~{end_ep} 闆嗗墽鏈鐧解€?)
        self._emit("step", f"鍏?{len(episode_chunks)} 闆嗗崱鐐癸紝姣?{EPISODES_PER_BATCH} 闆嗕负涓€鎵?)

        for batch_idx in range(0, len(episode_chunks), EPISODES_PER_BATCH):
            batch = episode_chunks[batch_idx:batch_idx + EPISODES_PER_BATCH]
            batch_text = "\n\n---\n\n".join(batch)

            ep_start = start_ep + batch_idx
            ep_end = min(ep_start + EPISODES_PER_BATCH - 1, end_ep)
            batch_num = batch_idx // EPISODES_PER_BATCH + 1
            total_batches = (len(episode_chunks) + EPISODES_PER_BATCH - 1) // EPISODES_PER_BATCH

            self._emit("step", f"姝ｅ湪鐢熸垚绗?{ep_start}~{ep_end} 闆嗗鐧解€?({batch_num}/{total_batches})")

            user_prompt = DIALOGUE_USER.format(
                topic=topic,
                episode_context=batch_text,
            )

            batch_tokens = []
            def _on_token(t: str):
                batch_tokens.append(t)

            content, usage = _llm_completion(
                system_prompt=DIALOGUE_SYSTEM,
                user_prompt=user_prompt,
                temperature=TEMPERATURE_SCRIPT,
                max_tokens=MAX_TOKENS_SCRIPT,
                stream=True,
                on_chunk=_on_token,
            )

            self._cumulative_usage.input_tokens += usage.input_tokens
            self._cumulative_usage.output_tokens += usage.output_tokens
            self._emit("token", f"绗?{ep_start}~{ep_end} 闆?鈥?杈撳嚭 {usage.output_tokens} tokens")

            yield f"\n\n## 绗?{ep_start}~{ep_end} 闆哱n\n", None
            yield content, usage

        self._emit("done", "鍏ㄩ儴鍓ф湰瀵圭櫧鐢熸垚瀹屾瘯锛?)

    # ------------------------------------------------------------------
    # 灞炴€?    # ------------------------------------------------------------------

    @property
    def cumulative_usage(self) -> TokenUsage:
        return self._cumulative_usage

    # ------------------------------------------------------------------
    # 杈呭姪
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_episode_blocks(
        episode_text: str, start_ep: int, end_ep: int
    ) -> list[str]:
        import re
        pattern = r"(绗琝s*\d+\s*闆哰\s\S]*?)(?=绗琝s*\d+\s*闆唡$)"
        matches = list(re.finditer(pattern, episode_text))
        blocks = []
        for m in matches:
            ep_match = re.search(r"绗琝s*(\d+)\s*闆?, m.group(1))
            if ep_match:
                ep_num = int(ep_match.group(1))
                if start_ep <= ep_num <= end_ep:
                    blocks.append(m.group(1).strip())
        return blocks


def check_llm_connection() -> tuple[bool, str]:
    """蹇€熸娴?LLM 杩炴帴鏄惁姝ｅ父銆?""
    try:
        content, usage = _llm_completion(
            system_prompt="浣犳槸涓€涓姪鎵嬨€?,
            user_prompt="鍥炲 OK锛屽彧鍥炲杩欎袱涓瓧姣嶃€?,
            temperature=0,
            max_tokens=10,
            stream=False,
        )
        return True, f"LLM 杩炴帴姝ｅ父 ({LLM_MODEL}), latency tokens={usage.total}"
    except Exception as e:
        return False, f"LLM 杩炴帴澶辫触: {str(e)[:200]}"
