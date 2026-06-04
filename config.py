"""
LLM 配置中心
===========
通过环境变量注入模型和密钥，支持 LiteLLM 支持的所有模型提供商。
"""

import os

# ---- LLM 模型配置 ----
LLM_MODEL = os.getenv("LLM_MODEL", "openai/deepseek-v4-pro")
LLM_API_KEY = os.getenv("LLM_API_KEY", os.getenv("DEEPSEEK_API_KEY", ""))
LLM_API_BASE = os.getenv("LLM_API_BASE", "https://api.deepseek.com")

# ---- 生成参数 ----
TEMPERATURE_CREATIVE = 0.85   # 创意阶段（大纲、人设）
TEMPERATURE_STRUCTURED = 0.7  # 结构化阶段（分集切分）
TEMPERATURE_SCRIPT = 0.9      # 对白生成（需要多样化的语言表达）

MAX_TOKENS_OUTLINE = 4096     # 大纲输出上限
MAX_TOKENS_EPISODES = 8192    # 百集清单输出上限
MAX_TOKENS_SCRIPT = 4096      # 单批对白输出上限（分批调用）

# ---- 百集切分配置 ----
TOTAL_EPISODES = 100
EPISODES_PER_BATCH = 20       # 每批生成的集数（减轻 LLM 压力）

# ---- 剧本生成并发配置 ----
SCRIPT_CONCURRENCY = 5        # 同时生成的集数
