"""
生成历史记录管理 v2
====================
每个项目一个文件夹，以剧名+时间戳命名，内含各卡点文件：
  generations/
    <剧名>_<timestamp>/
      outline.txt       — 大纲（卡点一确认时保存）
      episodes.txt      — 分集清单（卡点二确认时保存）
      script.txt        — 完整剧本（生成完成时保存）
      metadata.json     — 元数据
"""

import json
import os
import re
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Optional


GENERATIONS_DIR = os.path.join(os.path.dirname(__file__), "generations")


def extract_title(topic: str, outline: str = "") -> str:
    """从大纲中提取剧名，fallback 到题材"""
    if outline:
        # 尝试从大纲第一段提取"题材类型"或"核心卖点"
        for pat in [r"题材类型[：:]\s*(.+?)(?:\n|$)", r"核心卖点[（(].+?[)）][：:]\s*(.+?)(?:\n|$)"]:
            m = re.search(pat, outline)
            if m:
                title = m.group(1).strip().rstrip("。，,.")
                if title and len(title) < 60:
                    return _sanitize_filename(title)
    # fallback: 用题材做标题
    return _sanitize_filename(topic[:40])


def _sanitize_filename(text: str) -> str:
    """清理文本为合法文件名"""
    text = re.sub(r'[\\/:*?"<>|]', '_', text)
    text = re.sub(r'\s+', '_', text)
    return text.strip("_")[:50] or "未命名"


def _get_or_create_folder(topic: str, outline: str = "") -> str:
    """获取或创建当前 session 的项目文件夹。返回文件夹路径。"""
    # 用 session 级变量跟踪当前项目文件夹
    import streamlit as st
    if "project_folder" not in st.session_state or not st.session_state.project_folder:
        title = extract_title(topic, outline)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        folder_name = f"{title}_{ts}"
        folder_path = os.path.join(GENERATIONS_DIR, folder_name)
        os.makedirs(folder_path, exist_ok=True)
        st.session_state.project_folder = folder_path
    return st.session_state.project_folder


def save_outline(topic: str, outline: str) -> str:
    """卡点一确认时保存大纲。返回文件夹路径。"""
    folder = _get_or_create_folder(topic, outline)
    path = os.path.join(folder, "outline.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(outline)
    return folder


def save_episodes(topic: str, outline: str, episode_list: str) -> str:
    """卡点二确认时保存分集清单。返回文件夹路径。"""
    folder = _get_or_create_folder(topic, outline)
    path = os.path.join(folder, "episodes.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(episode_list)
    return folder


def save_script(
    topic: str,
    outline: str,
    episode_list: str,
    script_content: str,
    total_input_tokens: int = 0,
    total_output_tokens: int = 0,
    total_elapsed: float = 0.0,
    model: str = "",
) -> str:
    """生成完成时保存剧本 + 元数据。返回文件夹路径。"""
    folder = _get_or_create_folder(topic, outline)

    # 保存剧本
    script_path = os.path.join(folder, "script.txt")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(script_content)

    # 保存元数据
    meta = {
        "topic": topic,
        "model": model,
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "total_elapsed_seconds": total_elapsed,
        "created_at": datetime.now().isoformat(),
    }
    meta_path = os.path.join(folder, "metadata.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    return folder


@dataclass
class GenRecord:
    """历史记录摘要"""
    id: str = ""
    folder: str = ""
    title: str = ""
    created_at: str = ""
    topic: str = ""
    script_file: str = ""


def list_generations(limit: int = 20) -> list[GenRecord]:
    """列出最近的生成记录（按时间倒序）。"""
    if not os.path.isdir(GENERATIONS_DIR):
        return []

    records = []
    for entry in sorted(os.listdir(GENERATIONS_DIR), reverse=True):
        folder = os.path.join(GENERATIONS_DIR, entry)
        if not os.path.isdir(folder):
            continue
        meta_file = os.path.join(folder, "metadata.json")
        script_file = os.path.join(folder, "script.txt")
        if os.path.isfile(meta_file):
            try:
                with open(meta_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                records.append(GenRecord(
                    id=entry,
                    folder=folder,
                    title=entry.rsplit("_", 2)[0] if "_" in entry else entry,
                    created_at=data.get("created_at", ""),
                    topic=data.get("topic", ""),
                    script_file=script_file if os.path.isfile(script_file) else "",
                ))
            except Exception:
                continue
        if len(records) >= limit:
            break

    return records


def get_generation_script(record_id: str) -> Optional[str]:
    """根据记录 ID（文件夹名）读取完整剧本。"""
    script_path = os.path.join(GENERATIONS_DIR, record_id, "script.txt")
    if os.path.isfile(script_path):
        with open(script_path, "r", encoding="utf-8") as f:
            return f.read()
    return None


def get_checkpoint_content(record_id: str, checkpoint: str) -> Optional[str]:
    """读取指定卡点的内容（outline/episodes/script）。"""
    folder = os.path.join(GENERATIONS_DIR, record_id)
    fname = f"{checkpoint}.txt"
    path = os.path.join(folder, fname)
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return None
