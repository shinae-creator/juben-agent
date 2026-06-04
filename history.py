"""
鐢熸垚鍘嗗彶璁板綍绠＄悊
================
姣忔鍓ф湰鐢熸垚鍚庤嚜鍔ㄤ繚瀛樺埌 generations/ 鐩綍锛?  generations/
    <timestamp>_<topic_slug>/
      metadata.json   鈥?棰樻潗銆佸ぇ绾层€佸垎闆嗐€乀oken 鐢ㄩ噺銆佽€楁椂
      script.txt      鈥?瀹屾暣鍓ф湰
"""

import json
import os
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Optional


GENERATIONS_DIR = os.path.join(os.path.dirname(__file__), "generations")


@dataclass
class GenRecord:
    """涓€娆″畬鏁寸殑鐢熸垚璁板綍"""
    id: str = ""                          # 鏃堕棿鎴?ID
    created_at: str = ""                  # ISO 鏃堕棿
    topic: str = ""                       # 棰樻潗
    outline: str = ""                     # 澶х翰锛堝畬鏁存枃鏈級
    episode_list: str = ""                # 鍒嗛泦娓呭崟
    script_preview: str = ""             # 鍓ф湰鍓?200 瀛楅瑙?    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_elapsed_seconds: float = 0.0
    script_file: str = ""                # 鍓ф湰 TXT 璺緞
    model: str = ""


def _slugify(text: str, max_len: int = 30) -> str:
    """灏嗛鏉愭枃鏈浆涓哄畨鍏ㄧ殑鏂囦欢鍚嶇墖娈?""
    import re
    slug = re.sub(r'[^\w涓€-榭縗-]', '_', text)[:max_len]
    return slug.strip("_") or "generation"


def save_generation(
    topic: str,
    outline: str,
    episode_list: str,
    script_content: str,
    total_input_tokens: int = 0,
    total_output_tokens: int = 0,
    total_elapsed: float = 0.0,
    model: str = "",
) -> GenRecord:
    """
    淇濆瓨涓€娆＄敓鎴愬埌纾佺洏銆?
    Returns:
        GenRecord 鈥?淇濆瓨鍚庣殑璁板綍瀵硅薄
    """
    os.makedirs(GENERATIONS_DIR, exist_ok=True)

    now = datetime.now()
    record_id = now.strftime("%Y%m%d_%H%M%S")
    folder_name = f"{record_id}_{_slugify(topic)}"
    folder_path = os.path.join(GENERATIONS_DIR, folder_name)
    os.makedirs(folder_path, exist_ok=True)

    # 淇濆瓨鍓ф湰 TXT
    script_path = os.path.join(folder_path, "script.txt")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(script_content)

    # 淇濆瓨鍏冩暟鎹?JSON
    record = GenRecord(
        id=record_id,
        created_at=now.isoformat(),
        topic=topic,
        outline=outline[:5000],        # 鎴柇瀛樺偍浠ラ槻杩囧ぇ
        episode_list=episode_list[:5000],
        script_preview=script_content[:200],
        total_input_tokens=total_input_tokens,
        total_output_tokens=total_output_tokens,
        total_elapsed_seconds=total_elapsed,
        script_file=script_path,
        model=model,
    )

    metadata_path = os.path.join(folder_path, "metadata.json")
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(asdict(record), f, ensure_ascii=False, indent=2)

    return record


def list_generations(limit: int = 20) -> list[GenRecord]:
    """鍒楀嚭鏈€杩戠殑鐢熸垚璁板綍锛堟寜鏃堕棿鍊掑簭锛夈€?""
    if not os.path.isdir(GENERATIONS_DIR):
        return []

    records = []
    for entry in sorted(os.listdir(GENERATIONS_DIR), reverse=True):
        folder = os.path.join(GENERATIONS_DIR, entry)
        if not os.path.isdir(folder):
            continue
        meta_file = os.path.join(folder, "metadata.json")
        if os.path.isfile(meta_file):
            try:
                with open(meta_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                records.append(GenRecord(**data))
            except Exception:
                continue
        if len(records) >= limit:
            break

    return records


def get_generation_script(record_id: str) -> Optional[str]:
    """鏍规嵁璁板綍 ID 璇诲彇瀹屾暣鍓ф湰銆?""
    for entry in os.listdir(GENERATIONS_DIR):
        if entry.startswith(record_id):
            script_path = os.path.join(GENERATIONS_DIR, entry, "script.txt")
            if os.path.isfile(script_path):
                with open(script_path, "r", encoding="utf-8") as f:
                    return f.read()
    return None
