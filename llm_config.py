"""
LLM 配置管理器
==============
- 支持多模型配置（新增 / 切换 / 删除）
- JSON 持久化到 .claude/llm_configs.json
- 默认配置从 .env 文件 / 环境变量读取
"""

import json
import os
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

# ── 自动加载 .env ──
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_env_path)
    except ImportError:
        pass

CONFIG_FILE = os.path.join(os.path.dirname(__file__), ".claude", "llm_configs.json")

# 默认配置（来自 config.py 和环境变量）
DEFAULT_CONFIGS = [
    {
        "name": "DeepSeek V4 Pro（默认）",
        "model": os.getenv("LLM_MODEL", "openai/deepseek-v4-pro"),
        "api_key": os.getenv("LLM_API_KEY", os.getenv("DEEPSEEK_API_KEY", "")),
        "api_base": os.getenv("LLM_API_BASE", "https://api.deepseek.com"),
    },
]


def _ensure_dir():
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)


def load_configs() -> list[dict]:
    """加载所有 LLM 配置，合并默认配置。"""
    configs = list(DEFAULT_CONFIGS)  # 默认配置始终存在
    if os.path.isfile(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            # 合并保存的配置（去重：model 相同则跳过）
            existing_models = {c["model"] for c in configs}
            for cfg in saved:
                if cfg.get("model") not in existing_models:
                    configs.append(cfg)
                    existing_models.add(cfg["model"])
        except Exception:
            pass
    return configs


def save_configs(configs: list[dict]):
    """保存用户自定义配置（不包含默认配置）。"""
    _ensure_dir()
    default_models = {c["model"] for c in DEFAULT_CONFIGS}
    user_configs = [c for c in configs if c["model"] not in default_models]
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(user_configs, f, ensure_ascii=False, indent=2)


def add_config(name: str, model: str, api_key: str, api_base: str) -> list[dict]:
    """添加新配置并返回更新后的列表。"""
    configs = load_configs()
    # 去重
    configs = [c for c in configs if c["model"] != model]
    configs.append({
        "name": name,
        "model": model,
        "api_key": api_key,
        "api_base": api_base,
    })
    save_configs(configs)
    return configs


def delete_config(model: str) -> list[dict]:
    """删除指定 model 的配置（默认配置不可删除）。"""
    default_models = {c["model"] for c in DEFAULT_CONFIGS}
    if model in default_models:
        return load_configs()
    configs = load_configs()
    configs = [c for c in configs if c["model"] != model]
    save_configs(configs)
    return configs


def get_active_config(active_model: Optional[str] = None) -> dict:
    """获取当前激活的配置。"""
    configs = load_configs()
    if active_model:
        for cfg in configs:
            if cfg["model"] == active_model:
                return cfg
    # 返回第一个（默认）
    return configs[0] if configs else DEFAULT_CONFIGS[0]
