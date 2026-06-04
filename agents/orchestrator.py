"""
Agent 鐭╅樀缂栨帓鍣?================
璐熻矗涓夐樁娈垫祦姘寸嚎璋冨害锛?  1. 鐖嗘绛栧垝 Agent 鈫?鐢熸垚鐧鹃泦涓荤嚎澶х翰
  2. 鍒嗛泦鏋舵瀯甯?Agent 鈫?鍒囧垎 100 闆嗗崱鐐规竻鍗?  3. 瀵圭櫧鐢熸垚寮曟搸 鈫?骞跺彂/娴佸紡杈撳嚭瀹屾暣鍓ф湰

浣跨敤 LiteLLM 浣滀负 LLM 璺敱灞傦紝鏀寔浠绘剰妯″瀷鍒囨崲銆?"""

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
# LiteLLM 缁熶竴璋冪敤灏佽
# ============================================================================

def _llm_completion(
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    max_tokens: int,
    stream: bool = False,
) -> str | Generator:
    """
    缁熶竴鐨?LLM 璋冪敤鍏ュ彛锛屽皝瑁?LiteLLM completion銆?
    Args:
        system_prompt: 绯荤粺鎻愮ず璇?        user_prompt:  鐢ㄦ埛娑堟伅
        temperature:  鐢熸垚娓╁害
        max_tokens:   鏈€澶ц緭鍑?token
        stream:       鏄惁娴佸紡杩斿洖

    Returns:
        str 鎴?Generator锛堝綋 stream=True 鏃讹級
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
    """灏?LiteLLM 娴佸紡鍝嶅簲杞负瀛楃涓茬敓鎴愬櫒銆?""
    for chunk in response:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


# ============================================================================
# 缂栨帓鍣?# ============================================================================

class Orchestrator:
    """
    Agent 鐭╅樀缂栨帓鍣ㄣ€?
    鐢ㄦ硶锛?        orch = Orchestrator()
        outline = orch.generate_outline("閲嶇敓涔嬮兘甯傜鍖?)
        episodes = orch.generate_episodes(outline)
        for chunk in orch.generate_script_stream("閲嶇敓涔嬮兘甯傜鍖?, episodes):
            print(chunk, end="")
    """

    def __init__(
        self,
        model: Optional[str] = None,
        on_progress: Optional[Callable[[str], None]] = None,
    ):
        """
        Args:
            model:       瑕嗙洊榛樿妯″瀷
            on_progress: 杩涘害鍥炶皟锛屾帴鏀剁姸鎬佹弿杩板瓧绗︿覆
        """
        if model:
            global LLM_MODEL
            LLM_MODEL = model
        self.on_progress = on_progress or (lambda msg: logger.info(msg))

    # ------------------------------------------------------------------
    # 闃舵涓€锛氱垎娆剧瓥鍒?鈥?鐢熸垚鐧鹃泦涓荤嚎澶х翰
    # ------------------------------------------------------------------

    def generate_outline(self, topic: str) -> str:
        """
        杈撳叆棰樻潗锛岃緭鍑哄畬鏁寸殑鐧鹃泦涓荤嚎澶х翰銆?
        Args:
            topic: 缂栧墽杈撳叆鐨勯鏉?姊楁

        Returns:
            缁撴瀯鍖栧ぇ绾叉枃鏈?        """
        self.on_progress("馃 鐖嗘绛栧垝 Agent 姝ｅ湪鏋勬€濇晠浜嬧€?)
        outline = _llm_completion(
            system_prompt=PLANNER_SYSTEM,
            user_prompt=PLANNER_USER.format(topic=topic),
            temperature=TEMPERATURE_CREATIVE,
            max_tokens=MAX_TOKENS_OUTLINE,
            stream=False,
        )
        self.on_progress("鉁?鐧鹃泦涓荤嚎澶х翰宸茬敓鎴愶紝绛夊緟缂栧墽瀹″畾銆?)
        return outline

    # ------------------------------------------------------------------
    # 闃舵浜岋細鍒嗛泦鏋舵瀯 鈥?鍒囧垎 100 闆嗗崱鐐规竻鍗?    # ------------------------------------------------------------------

    def generate_episodes(self, outline: str) -> str:
        """
        杈撳叆澶х翰锛岃緭鍑哄畬鏁寸殑 100 闆嗗垎闆嗗崱鐐规竻鍗曘€?
        濡傛灉澶х翰杩囬暱锛岃嚜鍔ㄥ垎鎵硅皟鐢ㄤ互缁曡繃 token 闄愬埗锛?        姣忔鐢熸垚 EPISODES_PER_BATCH 闆嗭紝鏈€鍚庢嫾鎺ャ€?
        Args:
            outline: 宸茬‘璁ょ殑澶х翰鏂囨湰

        Returns:
            100 闆嗗垎闆嗗崱鐐规竻鍗曟枃鏈?        """
        self.on_progress("馃搼 鍒嗛泦鏋舵瀯甯?Agent 姝ｅ湪鍒囧垎 100 闆嗗崱鐐光€?)

        # 棣栨灏濊瘯锛氳 LLM 涓€娆℃€ц緭鍑哄叏閮紙瀵瑰己妯″瀷鍙锛?        try:
            episodes = _llm_completion(
                system_prompt=EPISODE_SYSTEM,
                user_prompt=EPISODE_USER.format(outline=outline),
                temperature=TEMPERATURE_STRUCTURED,
                max_tokens=MAX_TOKENS_EPISODES,
                stream=False,
            )
        except Exception as e:
            logger.warning("涓€娆℃€х敓鎴愮櫨闆嗗け璐ワ紙鍙兘鏄?token 闄愬埗锛夛紝鍥為€€鍒嗘壒妯″紡: %s", e)
            episodes = self._generate_episodes_batched(outline)

        self.on_progress("鉁?鐧鹃泦鍒嗛泦鍗＄偣娓呭崟宸茬敓鎴愶紝绛夊緟缂栧墽瀹″畾銆?)
        return episodes

    def _generate_episodes_batched(self, outline: str) -> str:
        """鍒嗘壒鐢熸垚鍒嗛泦鍗＄偣锛堝厹搴曟柟妗堬級銆?""
        batches = []
        batch_count = TOTAL_EPISODES // EPISODES_PER_BATCH

        for i in range(batch_count):
            start = i * EPISODES_PER_BATCH + 1
            end = (i + 1) * EPISODES_PER_BATCH
            self.on_progress(f"  馃搼 姝ｅ湪鐢熸垚绗?{start}~{end} 闆嗗崱鐐光€?)

            prompt = (
                EPISODE_USER.format(outline=outline)
                + f"\n\n銆愮壒鍒寚浠ゃ€戣鍙緭鍑虹 {start} 闆嗗埌绗?{end} 闆嗙殑鍒嗛泦鍗＄偣銆?
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
    # 闃舵涓夛細瀵圭櫧鐢熸垚 鈥?娴佸紡杈撳嚭鍓ф湰
    # ------------------------------------------------------------------

    def generate_script_stream(
        self,
        topic: str,
        episode_list: str,
        start_ep: int = 1,
        end_ep: Optional[int] = None,
    ) -> Generator[str, None, None]:
        """
        娴佸紡鐢熸垚瀹屾暣鍓ф湰瀵圭櫧銆?
        鎸夋壒娆＄敓鎴愶細姣忎釜 yield 杩斿洖涓€鎵瑰鐧芥枃鏈紝
        Streamlit 绔疮绉睍绀猴紝褰㈡垚鎵撳瓧鏈烘晥鏋溿€?
        Args:
            topic:         鍓у悕/棰樻潗
            episode_list:  宸茬‘璁ょ殑鍒嗛泦鍗＄偣娓呭崟
            start_ep:      璧峰闆嗘暟锛堥粯璁?1锛?            end_ep:        缁撴潫闆嗘暟锛堥粯璁?100锛?
        Yields:
            姣忔壒瀵圭櫧鏂囨湰鍧?        """
        if end_ep is None:
            end_ep = TOTAL_EPISODES

        # 瑙ｆ瀽鍒嗛泦鍗＄偣娓呭崟锛屾寜銆岀 X 闆嗐€嶅垎鍓?        episode_chunks = self._parse_episode_blocks(episode_list, start_ep, end_ep)

        self.on_progress(f"鉁嶏笍 瀵圭櫧寮曟搸鍚姩锛屽嵆灏嗙敓鎴?{start_ep}~{end_ep} 闆嗗墽鏈€?)

        # 鍒嗘壒鐢熸垚锛堟瘡鎵?EPISODES_PER_BATCH 闆嗭級
        for batch_idx in range(0, len(episode_chunks), EPISODES_PER_BATCH):
            batch = episode_chunks[batch_idx:batch_idx + EPISODES_PER_BATCH]
            batch_text = "\n\n---\n\n".join(batch)

            ep_start = start_ep + batch_idx
            ep_end = min(ep_start + EPISODES_PER_BATCH - 1, end_ep)

            self.on_progress(f"  鉁嶏笍 姝ｅ湪鐢熸垚绗?{ep_start}~{ep_end} 闆嗗鐧解€?)

            # 娴佸紡璋冪敤 LLM 杈撳嚭鏈壒瀵圭櫧
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

            # 閫?token yield
            chunk_prefix = f"\n\n## 绗?{ep_start}~{ep_end} 闆哱n\n"
            yield chunk_prefix

            for token in stream:
                yield token

        self.on_progress("鉁?鍓ф湰瀵圭櫧鍏ㄩ儴鐢熸垚瀹屾瘯锛?)

    # ------------------------------------------------------------------
    # 杈呭姪锛氳В鏋愬垎闆嗗崱鐐逛负鐙珛鍧?    # ------------------------------------------------------------------

    @staticmethod
    def _parse_episode_blocks(
        episode_text: str, start_ep: int, end_ep: int
    ) -> list[str]:
        """
        浠庡垎闆嗘竻鍗曟枃鏈腑鎻愬彇鎸囧畾鑼冨洿鐨勯泦鏁板潡銆?
        鍖归厤妯″紡锛氱 X 闆?/ 绗琗闆?/ Episode X 绛夈€?        """
        import re

        # 鎸夈€岀 X 闆嗐€嶅垎鍓?        pattern = r"(绗琝s*\d+\s*闆哰\s\S]*?)(?=绗琝s*\d+\s*闆唡$)"
        matches = list(re.finditer(pattern, episode_text))

        blocks = []
        for m in matches:
            # 鎻愬彇闆嗗彿
            ep_match = re.search(r"绗琝s*(\d+)\s*闆?, m.group(1))
            if ep_match:
                ep_num = int(ep_match.group(1))
                if start_ep <= ep_num <= end_ep:
                    blocks.append(m.group(1).strip())

        return blocks


# ============================================================================
# 鍋ュ悍妫€鏌?# ============================================================================

def check_llm_connection() -> tuple[bool, str]:
    """
    蹇€熸娴?LLM 杩炴帴鏄惁姝ｅ父銆?
    Returns:
        (鏄惁鍙敤, 娑堟伅)
    """
    try:
        _llm_completion(
            system_prompt="浣犳槸涓€涓姪鎵嬨€?,
            user_prompt="鍥炲'OK'銆?,
            temperature=0,
            max_tokens=10,
            stream=False,
        )
        return True, f"鉁?LLM 杩炴帴姝ｅ父 ({LLM_MODEL})"
    except Exception as e:
        return False, f"鉂?LLM 杩炴帴澶辫触: {str(e)[:200]}"
