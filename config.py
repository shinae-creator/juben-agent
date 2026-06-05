"""
LLM 配置中心
===========
通过环境变量注入模型和密钥，支持 LiteLLM 支持的所有模型提供商。
启动时自动从项目根目录 .env 文件加载配置。
"""

import os
from pathlib import Path

# ── 自动加载 .env 文件 ──
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_env_path)
    except ImportError:
        pass  # python-dotenv 未安装时静默跳过

# ---- LLM 模型配置 ----
LLM_MODEL = os.getenv("LLM_MODEL", "openai/deepseek-v4-pro")
LLM_API_KEY = os.getenv("LLM_API_KEY", os.getenv("DEEPSEEK_API_KEY", ""))
LLM_API_BASE = os.getenv("LLM_API_BASE", "https://api.deepseek.com")

# ---- 生成参数 ----
TEMPERATURE_CREATIVE = 0.85   # 创意阶段（大纲、人设）
TEMPERATURE_STRUCTURED = 0.7  # 结构化阶段（分集切分）
TEMPERATURE_SCRIPT = 0.9      # 对白生成（需要多样化的语言表达）

MAX_TOKENS_OUTLINE = 8192     # 大纲输出上限
MAX_TOKENS_EPISODES = 16384   # 百集清单输出上限（100集需要约12k tokens）
MAX_TOKENS_SCRIPT = 32768     # 单批对白输出上限（分镜头格式每集约 1500-3000 字，需充足空间）

# ---- 百集切分配置 ----
TOTAL_EPISODES = 20  # 默认 20 集精品短剧
EPISODES_PER_BATCH = 3        # 每批生成的集数（分镜头格式单集信息密度高，3集一批保完整）

# ---- 剧本生成并发配置 ----
SCRIPT_CONCURRENCY = 5        # 同时生成的集数

# ---- 流式输出配置 ----
STREAM_CHUNK_SIZE = 1         # 每 yield 的 token 数（1 = 逐字打字机）
