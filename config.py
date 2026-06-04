"""
LLM 閰嶇疆涓績
===========
閫氳繃鐜鍙橀噺娉ㄥ叆妯″瀷鍜屽瘑閽ワ紝鏀寔 LiteLLM 鏀寔鐨勬墍鏈夋ā鍨嬫彁渚涘晢銆?"""

import os

# ---- LLM 妯″瀷閰嶇疆 ----
LLM_MODEL = os.getenv("LLM_MODEL", "openai/deepseek-v4-pro")
LLM_API_KEY = os.getenv("LLM_API_KEY", os.getenv("DEEPSEEK_API_KEY", ""))
LLM_API_BASE = os.getenv("LLM_API_BASE", "https://api.deepseek.com")

# ---- 鐢熸垚鍙傛暟 ----
TEMPERATURE_CREATIVE = 0.85   # 鍒涙剰闃舵锛堝ぇ绾层€佷汉璁撅級
TEMPERATURE_STRUCTURED = 0.7  # 缁撴瀯鍖栭樁娈碉紙鍒嗛泦鍒囧垎锛?TEMPERATURE_SCRIPT = 0.9      # 瀵圭櫧鐢熸垚锛堥渶瑕佸鏍峰寲鐨勮瑷€琛ㄨ揪锛?
MAX_TOKENS_OUTLINE = 4096     # 澶х翰杈撳嚭涓婇檺
MAX_TOKENS_EPISODES = 8192    # 鐧鹃泦娓呭崟杈撳嚭涓婇檺
MAX_TOKENS_SCRIPT = 4096      # 鍗曟壒瀵圭櫧杈撳嚭涓婇檺锛堝垎鎵硅皟鐢級

# ---- 鐧鹃泦鍒囧垎閰嶇疆 ----
TOTAL_EPISODES = 100
EPISODES_PER_BATCH = 20       # 姣忔壒鐢熸垚鐨勯泦鏁帮紙鍑忚交 LLM 鍘嬪姏锛?
# ---- 鍓ф湰鐢熸垚骞跺彂閰嶇疆 ----
SCRIPT_CONCURRENCY = 5        # 鍚屾椂鐢熸垚鐨勯泦鏁?