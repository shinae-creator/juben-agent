"""
短剧 Agent 创作工作站 v6 — Streamlit 前端
===========================================
v6 增强：
  - 前端 LLM 配置面板（多模型新增/切换/删除，持久化保存）
  - 可变集数选择（20/30/100/自定义）
  - 修复卡点2计时累加 bug
v5 增强：
  - 修复分集清单卡点内容丢失（版本化 widget key）
  - 测试模式（Mock 数据，不烧 Token，极速调试）
"""

import os
import re
import time
import math

import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime
from typing import Optional

from config import EPISODES_PER_BATCH as SCRIPT_BATCH_SIZE
from agents import Orchestrator
from agents.orchestrator import ProgressEvent, TokenUsage
from agents.mock import (
    generate_mock_outline_stream,
    generate_mock_episodes_stream,
    generate_mock_script_stream,
)
from history import (
    save_outline,
    save_episodes,
    save_script,
    list_generations,
    get_generation_script,
    get_checkpoint_content,
)
from llm_config import load_configs, add_config, delete_config, get_active_config

# ============================================================================
# 页面全局配置
# ============================================================================

st.set_page_config(
    page_title="短剧 Agent 创作工作站",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================================
# 自定义 CSS
# ============================================================================

st.markdown("""
<style>
    .main-title {
        font-size: 2rem; font-weight: 700;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        background-clip: text; margin-bottom: 0.25rem;
    }
    .sub-title { color: #888; font-size: 0.9rem; margin-bottom: 1.5rem; }
    .stepper-container {
        display: flex; justify-content: space-between; align-items: center;
        padding: 1rem 2rem; margin: 1rem 0 2rem 0;
        background: #f8f9fa; border-radius: 12px;
    }
    .step-item { display: flex; flex-direction: column; align-items: center; gap: 0.3rem; flex: 1; }
    .step-circle {
        width: 36px; height: 36px; border-radius: 50%;
        display: flex; align-items: center; justify-content: center;
        font-size: 1rem; font-weight: 700; border: 3px solid #ddd;
        background: #fff; color: #bbb;
    }
    .step-circle.active { border-color: #667eea; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: #fff; }
    .step-circle.done { border-color: #28a745; background: #28a745; color: #fff; }
    .step-label { font-size: 0.75rem; color: #999; text-align: center; }
    .step-label.active { color: #667eea; font-weight: 600; }
    .step-label.done { color: #28a745; }
    .step-connector { flex: 0 0 40px; height: 3px; background: #ddd; margin: 0 -4px; margin-bottom: 1.2rem; }
    .step-connector.done { background: #28a745; }
    .checkpoint-card {
        background: #fff; border: 1px solid #e8e8e8; border-radius: 12px;
        padding: 1.5rem; margin-bottom: 1.2rem;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
    }
    .checkpoint-card.locked { opacity: 0.55; pointer-events: none; filter: grayscale(40%); }
    .checkpoint-card.active { border-color: #667eea; box-shadow: 0 0 0 3px rgba(102,126,234,0.12); }
    .card-badge {
        display: inline-block; padding: 0.2rem 0.7rem; border-radius: 20px;
        font-size: 0.75rem; font-weight: 600; margin-bottom: 0.6rem;
    }
    .badge-checkpoint { background: #eef0ff; color: #667eea; }
    .badge-done { background: #e6f9ed; color: #28a745; }
    .badge-pending { background: #f5f5f5; color: #999; }
    .script-canvas {
        background: #fcfcfc; border: 1px solid #e8e8e8; border-radius: 12px;
        padding: 1.5rem; min-height: 420px; max-height: 55vh;
        overflow-y: auto; font-family: "Source Code Pro", Consolas, monospace;
        font-size: 0.85rem; line-height: 1.8; white-space: pre-wrap; color: #333;
    }
    .script-canvas.placeholder {
        display: flex; align-items: center; justify-content: center;
        color: #ccc; font-family: "Segoe UI", sans-serif; font-size: 1rem;
    }
    .log-box {
        background: #1e1e2e; color: #cdd6f4; border-radius: 8px;
        padding: 0.7rem 1rem; font-family: Consolas, monospace;
        font-size: 0.78rem; line-height: 1.6;
        max-height: 200px; overflow-y: auto; margin-top: 0.5rem;
    }
    .token-badge {
        display: inline-block; padding: 0.15rem 0.5rem; border-radius: 4px;
        font-size: 0.7rem; font-weight: 600; margin-right: 0.3rem;
        background: #e8f4fd; color: #0b5cad;
    }
    .stButton > button { border-radius: 8px; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# Session State
# ============================================================================

DEFAULTS = {
    "topic": "",
    "topic_submitted": False,
    "workflow_stage": "input",   # input|planning|outline_review|episode_review|generating|done
    "outline": "",
    "outline_confirmed": False,
    "episode_list": "",
    "episode_confirmed": False,
    "script_content": "",
    "script_generating": False,
    "_script_accumulated": "",       # 流式生成累积内容（防 rerun 丢失）
    "_script_streaming": False,      # 流式生成进行中标记（防 rerun 重建生成器）
    "status_message": "",
    # v2 新增
    "generation_log": [],        # [(timestamp, icon, message), ...]
    "total_token_usage": {"input": 0, "output": 0},
    "gen_elapsed": 0.0,
    "gen_start_time": 0.0,
    # v5: 测试模式 & widget 状态同步
    "test_mode": False,
    # v6: 集数选择 & LLM 配置
    "total_episodes": 20,     # 默认 20 集精品短剧
    "active_llm_model": "",   # 空 = 使用默认
    # v7: 按项目文件夹保存
    "project_folder": "",
    # v8: 结构化分集 + 可视化大盘
    "episode_cards": [],          # List[EpisodeCard] — 结构化分集数据
    "episode_json_raw": "",       # 原始 JSON 字符串（调试用）
    "episode_editor_mode": "visual",  # "visual" | "raw"
}

for key, default in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = default

# ── widget 版本号：内容变更时 +1 → 生成新 key → value= 生效 ──
# Streamlit 的 text_area 带 key 时，一旦渲染过，后续 rerun 中 value= 被忽略，
# 以 widget 内部状态为准。解决方案：每次外部更新内容时递增版本号，
# 用新 key（从未渲染过）承载 value=，Streamlit 就会把 value 当作初始值。
if "_outline_version" not in st.session_state:
    st.session_state._outline_version = 0
if "_episode_version" not in st.session_state:
    st.session_state._episode_version = 0


# ============================================================================
# 进度事件回调
# ============================================================================

def make_event_handler():
    """创建一个将 ProgressEvent 写入 session_state 日志的回调"""
    def handler(event: ProgressEvent):
        icon = {"stage": "🔹", "step": "  ⚙️", "token": "  📊", "done": "✅", "error": "❌"}.get(event.type, "")
        st.session_state.generation_log.append((time.time(), icon, event.message))
    return handler


# ============================================================================
# Agent 自动调度钩子（v4：仅标记，不阻塞 — 流式在 UI 区执行）
# ============================================================================

# ---- planning → 准备大纲流式生成 ----
if st.session_state.workflow_stage == "planning" and not st.session_state.get("_outline_streaming"):
    st.session_state._outline_streaming = True
    st.session_state.generation_log = []
    st.session_state.gen_start_time = time.time()

# ---- episode_review → 准备分集流式生成 ----
if (
    st.session_state.workflow_stage == "episode_review"
    and not st.session_state.episode_list
    and not st.session_state.get("_episode_streaming")
):
    st.session_state._episode_streaming = True
    st.session_state.gen_start_time = time.time()  # ← 重置计时，避免累加大纲耗时

# ---- generating → 准备剧本流式生成 ----
if (
    st.session_state.workflow_stage == "generating"
    and not st.session_state.script_generating
):
    st.session_state.script_generating = True
    st.session_state.script_content = ""
    st.session_state.gen_start_time = time.time()


# ============================================================================
# 辅助函数
# ============================================================================

def _bump_outline_version():
    st.session_state._outline_version += 1

def _bump_episode_version():
    st.session_state._episode_version += 1

def reset_workflow():
    for key, default in DEFAULTS.items():
        st.session_state[key] = default
    # 清理流式标记
    for flag in ["_outline_streaming", "_episode_streaming"]:
        if flag in st.session_state:
            del st.session_state[flag]
    # 清理版本化 widget key（旧版本残留）
    for key in list(st.session_state.keys()):
        if key.startswith("outline_editor_v") or key.startswith("episode_editor_v"):
            del st.session_state[key]
    # 重置版本号
    st.session_state._outline_version = 0
    st.session_state._episode_version = 0
    # 重置项目文件夹
    st.session_state.project_folder = ""

def get_stage_index(stage: str) -> int:
    order = ["input", "planning", "outline_review", "episode_review", "generating", "done"]
    return order.index(stage) if stage in order else 0

def get_llm_params() -> dict:
    """根据当前 session state 获取 LLM 配置参数"""
    active_model = st.session_state.get("active_llm_model", "")
    cfg = get_active_config(active_model)
    return {
        "model": cfg["model"],
        "api_key": cfg.get("api_key", ""),
        "api_base": cfg.get("api_base", ""),
    }


# ============================================================================
# 标题 & 进度条
# ============================================================================

st.markdown('<p class="main-title">🎬 短剧 Agent 创作工作站</p>', unsafe_allow_html=True)
st.markdown(
    f'<p class="sub-title">Agent 矩阵全自动构思 · 编剧网页控场 · 一键出本 '
    f'| {datetime.now().strftime("%Y-%m-%d %H:%M")}</p>',
    unsafe_allow_html=True,
)

STEPS = [
    ("input", "📝", "输入题材"),
    ("planning", "🧠", "AI 构思"),
    ("outline_review", "📋", "大纲审定"),
    ("episode_review", "📑", "分集审定"),
    ("generating", "✍️", "生成剧本"),
    ("done", "✅", "完成"),
]
current_idx = get_stage_index(st.session_state.workflow_stage)

stepper_html = '<div class="stepper-container">'
for i, (stage, icon, label) in enumerate(STEPS):
    if i > 0:
        stepper_html += f'<div class="step-connector{" done" if i <= current_idx else ""}"></div>'
    if i < current_idx:
        cls, lbl_cls, cont = "done", "done", "✓"
    elif i == current_idx:
        cls, lbl_cls, cont = "active", "active", icon
    else:
        cls, lbl_cls, cont = "", "", icon
    stepper_html += (
        f'<div class="step-item">'
        f'<div class="step-circle {cls}">{cont}</div>'
        f'<div class="step-label {lbl_cls}">{label}</div>'
        f'</div>'
    )
stepper_html += '</div>'
st.markdown(stepper_html, unsafe_allow_html=True)


# ============================================================================
# 左栏：卡点卡片
# ============================================================================

left_col, right_col = st.columns([2, 3], gap="medium")

with left_col:
    if st.session_state.status_message:
        st.info(st.session_state.status_message)

    # ── Token 用量面板（Claude Code 风格动态累加） ──
    tu = st.session_state.total_token_usage
    if tu["input"] > 0 or tu["output"] > 0:
        total_t = tu["input"] + tu["output"]
        elapsed = st.session_state.gen_elapsed or (time.time() - st.session_state.gen_start_time if st.session_state.gen_start_time else 0)
        st.markdown(
            f"""<div style="background:#f0f4ff;border:1px solid #c8d6ff;border-radius:8px;padding:0.6rem 1rem;margin-bottom:0.8rem;font-family:Consolas,monospace;font-size:0.82rem;">
            📥 输入 <b>{tu['input']:,}</b> &nbsp;|&nbsp;
            📤 输出 <b>{tu['output']:,}</b> &nbsp;|&nbsp;
            🔥 合计 <b style="color:#667eea;">{total_t:,}</b> tokens &nbsp;|&nbsp;
            ⏱ <b>{elapsed:.0f}s</b>
            </div>""",
            unsafe_allow_html=True,
        )

    # ============================
    # 卡点一：大纲
    # ============================
    outline_locked = get_stage_index(st.session_state.workflow_stage) < get_stage_index("outline_review")
    outline_active = st.session_state.workflow_stage == "outline_review"
    outline_done = get_stage_index(st.session_state.workflow_stage) > get_stage_index("outline_review")

    card_cls = "checkpoint-card"
    if outline_locked: card_cls += " locked"
    elif outline_active: card_cls += " active"

    st.markdown(f'<div class="{card_cls}">', unsafe_allow_html=True)
    c1, c2 = st.columns([3, 1])
    with c1: st.markdown("### 📋 卡点一 · 百集主线大纲")
    with c2:
        if outline_done: st.markdown('<span class="card-badge badge-done">✓ 已确认</span>', unsafe_allow_html=True)
        elif outline_active: st.markdown('<span class="card-badge badge-checkpoint">⏳ 待审定</span>', unsafe_allow_html=True)
        else: st.markdown('<span class="card-badge badge-pending">🔒 等待中</span>', unsafe_allow_html=True)

    if outline_done:
        st.text_area("大纲（已确认）", value=st.session_state.outline, height=220, disabled=True, key=f"outline_done_v{st.session_state._outline_version}")
    elif not outline_locked:
        # 版本化 key：每次外部更新（AI 生成 / 导入）会递增版本号，
        # 生成一个从未渲染过的新 key，Streamlit 会把 value= 当作初始值。
        editor_key = f"outline_editor_v{st.session_state._outline_version}"
        edited = st.text_area(
            "AI 生成的大纲，可直接编辑：", value=st.session_state.outline, height=220,
            placeholder="Agent 矩阵正在构思…", key=editor_key,
        )
        st.session_state.outline = edited
        b1, b2 = st.columns(2)
        with b1:
            if st.button("✅ 确认大纲", use_container_width=True, key="btn_confirm_outline"):
                if st.session_state.outline.strip():
                    st.session_state.outline_confirmed = True
                    st.session_state.workflow_stage = "episode_review"
                    # ── 保存大纲 ──
                    try:
                        save_outline(st.session_state.topic, st.session_state.outline)
                    except Exception:
                        pass
                    st.session_state.status_message = "大纲已确认并保存！正在生成分集清单…"
                    st.rerun()
                else: st.warning("大纲不能为空")
        with b2:
            if st.button("🔄 AI 重构思", use_container_width=True, key="btn_regenerate_outline"):
                st.session_state.workflow_stage = "planning"
                st.session_state.outline = ""
                _bump_outline_version()              # 清空大纲 widget
                st.session_state.status_message = "Agent 矩阵重新构思中…"
                st.rerun()
    else:
        st.text_area("大纲", value="（请先提交题材）", height=220, disabled=True, key="outline_placeholder")
    st.markdown('</div>', unsafe_allow_html=True)

    # ============================
    # 卡点二：分集（V2: 可视化大盘 + 原始文本双模式）
    # ============================
    episode_locked = get_stage_index(st.session_state.workflow_stage) < get_stage_index("episode_review")
    episode_active = st.session_state.workflow_stage == "episode_review"
    episode_done = get_stage_index(st.session_state.workflow_stage) > get_stage_index("episode_review")

    card_cls2 = "checkpoint-card"
    if episode_locked: card_cls2 += " locked"
    elif episode_active: card_cls2 += " active"

    st.markdown(f'<div class="{card_cls2}">', unsafe_allow_html=True)
    c3, c4 = st.columns([3, 1])
    with c3: st.markdown("### 📑 卡点二 · 分集挂钩点清单")
    with c4:
        if episode_done: st.markdown('<span class="card-badge badge-done">✓ 已确认</span>', unsafe_allow_html=True)
        elif episode_active: st.markdown('<span class="card-badge badge-checkpoint">⏳ 待审定</span>', unsafe_allow_html=True)
        else: st.markdown('<span class="card-badge badge-pending">🔒 等待中</span>', unsafe_allow_html=True)

    # ── 评分颜色方案 ──
    SCORE_COLORS = {
        "conflict_intensity": "#e74c3c",
        "pleasure_index": "#f39c12",
        "hook_strength": "#9b59b6",
        "emotional_resonance": "#3498db",
    }
    SCORE_LABELS = {
        "conflict_intensity": "冲突",
        "pleasure_index": "爽感",
        "hook_strength": "悬念",
        "emotional_resonance": "情感",
    }

    def _score_bar_html(value: int, dim_key: str) -> str:
        """单条评分进度条 HTML"""
        color = SCORE_COLORS.get(dim_key, "#888")
        label = SCORE_LABELS.get(dim_key, dim_key)
        pct = value * 10
        return (
            f'<div style="flex:1;min-width:50px;text-align:center;margin:0 2px;">'
            f'<div style="font-size:0.55rem;color:#999;margin-bottom:1px;">{label}</div>'
            f'<div style="background:#eee;height:5px;border-radius:3px;width:100%;">'
            f'<div style="background:{color};height:5px;border-radius:3px;width:{pct}%;"></div>'
            f'</div>'
            f'<div style="font-size:0.65rem;font-weight:700;color:{color};margin-top:1px;">{value}</div>'
            f'</div>'
        )

    def _avg_color(avg: float) -> str:
        if avg >= 8: return "#28a745"
        elif avg >= 6: return "#f39c12"
        elif avg >= 4: return "#e67e22"
        else: return "#e74c3c"

    if episode_done:
        st.text_area("分集清单（已确认）", value=st.session_state.episode_list, height=280, disabled=True, key=f"ep_done_v{st.session_state._episode_version}")
    elif not episode_locked:
        # ── 编辑模式切换 ──
        cards = st.session_state.get("episode_cards", [])
        has_cards = bool(cards and len(cards) > 0)
        mode_options = ["📊 可视化大盘", "📝 原始文本"]
        default_mode_idx = 0 if (has_cards and st.session_state.get("episode_editor_mode") == "visual") else 1
        if not has_cards:
            default_mode_idx = 1  # 无结构化数据时强制原始文本
        edit_mode = st.radio(
            "编辑模式", mode_options, horizontal=True,
            key="ep_edit_mode_radio",
            index=default_mode_idx,
            label_visibility="collapsed",
        )
        st.session_state.episode_editor_mode = "visual" if "可视化" in edit_mode else "raw"

        if "可视化" in edit_mode and has_cards:
            # ═══════════════ 可视化大盘 ═══════════════
            # 数据概览
            all_scores = [(c.avg_score, c) for c in cards]
            if all_scores:
                best = max(all_scores, key=lambda x: x[0])
                worst = min(all_scores, key=lambda x: x[0])
                avg_all = sum(s for s, _ in all_scores) / len(all_scores)
                cols_kpi = st.columns(4)
                cols_kpi[0].metric("📊 均分", f"{avg_all:.1f}")
                cols_kpi[1].metric("🏆 最强集", f"第{best[1].episode_num}集 {best[0]:.1f}")
                cols_kpi[2].metric("⚠️ 弱集", f"第{worst[1].episode_num}集 {worst[0]:.1f}")
                cols_kpi[3].metric("📋 总集数", len(cards))

            # 数据大盘表格（带进度条）
            df_data = []
            for card in cards:
                df_data.append({
                    "集": card.episode_num,
                    "标题": card.title,
                    "🔥 冲突": card.conflict_intensity * 10,
                    "⚡ 爽感": card.pleasure_index * 10,
                    "🪝 悬念": card.hook_strength * 10,
                    "💙 情感": card.emotional_resonance * 10,
                    "均分": f"{card.avg_score:.1f}",
                })
            st.dataframe(
                df_data,
                column_config={
                    "集": st.column_config.NumberColumn("集", width="small"),
                    "标题": st.column_config.TextColumn("标题", width="medium"),
                    "🔥 冲突": st.column_config.ProgressColumn("冲突烈度", min_value=0, max_value=100, format="%d/10", width="small"),
                    "⚡ 爽感": st.column_config.ProgressColumn("爽感爆发度", min_value=0, max_value=100, format="%d/10", width="small"),
                    "🪝 悬念": st.column_config.ProgressColumn("悬念钩子度", min_value=0, max_value=100, format="%d/10", width="small"),
                    "💙 情感": st.column_config.ProgressColumn("情感共鸣度", min_value=0, max_value=100, format="%d/10", width="small"),
                    "均分": st.column_config.TextColumn("均分", width="small"),
                },
                hide_index=True,
                use_container_width=True,
                height=min(35 * len(cards) + 38, 500),
            )

            # ── 单集微调表单 ──
            st.markdown("---")
            st.markdown("#### ✏️ 单集微调")
            ep_nums = [c.episode_num for c in cards]
            selected_ep = st.selectbox(
                "选择要编辑的集数：", ep_nums,
                format_func=lambda n: f"第{n}集 · {cards[n-1].title if n <= len(cards) else ''}",
                key="ep_detail_select",
            )
            if selected_ep and selected_ep <= len(cards):
                card = cards[selected_ep - 1]
                with st.form(key=f"ep_edit_form_{selected_ep}"):
                    fc1, fc2 = st.columns([3, 1])
                    with fc1:
                        new_title = st.text_input("标题", value=card.title, key=f"et_{selected_ep}")
                        new_summary = st.text_area("核心剧情概要", value=card.summary, height=68, key=f"es_{selected_ep}")
                    with fc2:
                        # 评分雷达预览
                        bars_html = "".join([
                            _score_bar_html(getattr(card, f), f)
                            for f in ["conflict_intensity", "pleasure_index", "hook_strength", "emotional_resonance"]
                        ])
                        st.markdown(
                            f'<div style="display:flex;gap:4px;margin-top:4px;">{bars_html}</div>'
                            f'<div style="text-align:center;font-size:0.8rem;color:#888;margin-top:4px;">均分 {card.avg_score:.1f}</div>',
                            unsafe_allow_html=True,
                        )
                    new_cliffhanger = st.text_area("结尾钩子", value=card.cliffhanger, height=56, key=f"ec_{selected_ep}")
                    sc1, sc2, sc3, sc4 = st.columns(4)
                    with sc1:
                        new_conflict = st.slider("🔥 冲突烈度", 0, 10, card.conflict_intensity, key=f"scr_{selected_ep}")
                    with sc2:
                        new_pleasure = st.slider("⚡ 爽感爆发度", 0, 10, card.pleasure_index, key=f"spl_{selected_ep}")
                    with sc3:
                        new_hook = st.slider("🪝 悬念钩子度", 0, 10, card.hook_strength, key=f"shk_{selected_ep}")
                    with sc4:
                        new_emotion = st.slider("💙 情感共鸣度", 0, 10, card.emotional_resonance, key=f"sem_{selected_ep}")

                    if st.form_submit_button("💾 保存修改", use_container_width=True):
                        card.title = new_title
                        card.summary = new_summary
                        card.cliffhanger = new_cliffhanger
                        card.conflict_intensity = new_conflict
                        card.pleasure_index = new_pleasure
                        card.hook_strength = new_hook
                        card.emotional_resonance = new_emotion
                        # 同步回 episode_list
                        try:
                            from agents.episode_parser import serialize_to_markdown
                            st.session_state.episode_list = serialize_to_markdown(st.session_state.episode_cards)
                        except Exception:
                            pass
                        _bump_episode_version()
                        st.session_state.status_message = f"第{selected_ep}集已更新！"
                        st.rerun()

            # ── 如果解析可能不完整，给出提示 ──
            if not any(c.conflict_intensity != 5 for c in cards):
                st.caption("⚠️ AI 未输出结构化评分，显示为默认值 5。您可手动调整评分。")

        else:
            # ═══════════════ 原始文本模式（兼容旧版） ═══════════════
            editor_key = f"episode_editor_v{st.session_state._episode_version}"
            edited = st.text_area(
                f"{st.session_state.total_episodes}集分集卡点，可直接编辑：",
                value=st.session_state.episode_list, height=280,
                placeholder="大纲确认后自动生成…", key=editor_key,
            )
            st.session_state.episode_list = edited
            # 原始文本编辑后尝试重新解析结构化数据
            if edited.strip() and not has_cards:
                try:
                    from agents.episode_parser import parse_episodes
                    st.session_state.episode_cards = parse_episodes(edited, st.session_state.total_episodes)
                except Exception:
                    st.session_state.episode_cards = []

        # ── 操作按钮（两种模式共用） ──
        b3, b4, b5 = st.columns([1, 1, 1])
        with b3:
            if st.button("✅ 确认并出本", use_container_width=True, key="btn_confirm_ep"):
                if st.session_state.episode_list.strip():
                    st.session_state.episode_confirmed = True
                    st.session_state.workflow_stage = "generating"
                    # ── 保存分集清单（JSON 或旧格式均可）──
                    try:
                        save_episodes(st.session_state.topic, st.session_state.outline, st.session_state.episode_list)
                    except Exception:
                        pass
                    st.session_state.status_message = "分集已确认并保存！正在生成剧本…"
                    st.rerun()
                else: st.warning("分集清单不能为空")
        with b4:
            if st.button("🔄 重新切分", use_container_width=True, key="btn_regen_ep"):
                st.session_state.episode_list = ""
                st.session_state.episode_cards = []
                _bump_episode_version()
                st.session_state.status_message = "分集架构师重新切分中…"
                st.rerun()
        with b5:
            if st.button("↩ 返回改大纲", use_container_width=True, key="btn_back_ol"):
                st.session_state.workflow_stage = "outline_review"
                st.session_state.episode_confirmed = False
                st.session_state.episode_list = ""
                st.session_state.episode_cards = []
                _bump_episode_version()
                st.rerun()
    else:
        st.text_area("分集清单", value="（请先确认大纲）", height=280, disabled=True, key="ep_placeholder")
    st.markdown('</div>', unsafe_allow_html=True)

    # ── 下载按钮 ──
    if st.session_state.workflow_stage == "done" and st.session_state.script_content:
        st.download_button(
            label="⬇️ 下载剧本 TXT",
            data=st.session_state.script_content,
            file_name=f"短剧_{st.session_state.topic[:20]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            mime="text/plain",
            use_container_width=True,
        )


# ============================================================================
# 右栏：剧本画布 + 进度日志
# ============================================================================

with right_col:
    # ── 进度日志 ──
    with st.expander("📡 Agent 运行日志", expanded=bool(st.session_state.generation_log)):
        if st.session_state.generation_log:
            # 去重：相同消息只保留最新时间戳
            seen_msgs = set()
            unique_log = []
            for ts, icon, msg in st.session_state.generation_log:
                if msg not in seen_msgs:
                    seen_msgs.add(msg)
                    unique_log.append((ts, icon, msg))
            log_lines = [f"{icon} {msg}" for _, icon, msg in unique_log]
            st.markdown(
                f'<div class="log-box">' + "<br>".join(log_lines) + '</div>',
                unsafe_allow_html=True,
            )
        else:
            st.caption("暂无日志，提交题材后自动显示。")

    # ── 实时流式生成区（卡点1/2/3 共用）──
    streaming_active = False
    stream_title = ""
    stream_accumulated = ""

    # 卡点一：大纲流式生成
    if (st.session_state.get("_outline_streaming")
            and not st.session_state.outline
            and st.session_state.workflow_stage == "planning"):
        streaming_active = True
        test_mode = st.session_state.test_mode
        total_ep = st.session_state.total_episodes
        stream_title = f"🧠 爆款策划 Agent 正在构思 {total_ep} 集大纲…" if not test_mode else f"🧠 [测试模式] Mock {total_ep} 集大纲生成中…"
        if test_mode:
            stream_gen = generate_mock_outline_stream(st.session_state.topic, total_episodes=total_ep)
            st.session_state.generation_log.append((time.time(), "🧪", f"测试模式：生成 {total_ep} 集 Mock 大纲"))
        else:
            llm = get_llm_params()
            orch = Orchestrator(on_event=make_event_handler(), total_episodes=total_ep, **llm)
            stream_gen = orch.generate_outline_stream(st.session_state.topic)
        content_ph = st.empty()
        token_ph = st.empty()
        accumulated = ""
        try:
            for chunk, batch_usage in stream_gen:
                accumulated += chunk
                if batch_usage:
                    st.session_state.total_token_usage["input"] += batch_usage.input_tokens
                    st.session_state.total_token_usage["output"] += batch_usage.output_tokens
                elapsed = time.time() - st.session_state.gen_start_time
                tu = st.session_state.total_token_usage
                token_ph.caption(
                    f"⏱ {elapsed:.0f}s | 📥 输入 {tu['input']:,} | 📤 输出 {tu['output']:,} | 🔥 合计 {tu['input']+tu['output']:,} tokens"
                )
                content_ph.markdown(
                    f'<div class="script-canvas">{accumulated}</div>',
                    unsafe_allow_html=True,
                )
            st.session_state.outline = accumulated
            _bump_outline_version()          # ← 触发新 widget key
            st.session_state._outline_streaming = False
            st.session_state.gen_elapsed = time.time() - st.session_state.gen_start_time
            st.session_state.workflow_stage = "outline_review"
            st.session_state.status_message = "大纲已生成！请在左侧审核修改后确认。"
            st.rerun()
        except Exception as exc:
            st.session_state.status_message = f"❌ 大纲生成失败: {exc}"
            st.session_state._outline_streaming = False
            st.session_state.workflow_stage = "input"
            st.rerun()

    # 卡点二：分集流式生成
    if (st.session_state.get("_episode_streaming")
            and not st.session_state.episode_list
            and st.session_state.workflow_stage == "episode_review"):
        streaming_active = True
        test_mode = st.session_state.test_mode
        total_ep = st.session_state.total_episodes
        stream_title = f"📑 分集架构师正在切分 {total_ep} 集卡点…" if not test_mode else f"📑 [测试模式] Mock 分集生成中（{total_ep} 集）…"
        if test_mode:
            stream_gen = generate_mock_episodes_stream(st.session_state.outline, total_episodes=total_ep)
            st.session_state.generation_log.append((time.time(), "🧪", f"测试模式：生成 {total_ep} 集 Mock 数据"))
        else:
            llm = get_llm_params()
            orch = Orchestrator(on_event=make_event_handler(), total_episodes=total_ep, **llm)
            stream_gen = orch.generate_episodes_stream(st.session_state.outline)
        content_ph = st.empty()
        token_ph = st.empty()
        accumulated = ""
        try:
            for chunk, batch_usage in stream_gen:
                accumulated += chunk
                if batch_usage:
                    st.session_state.total_token_usage["input"] += batch_usage.input_tokens
                    st.session_state.total_token_usage["output"] += batch_usage.output_tokens
                elapsed = time.time() - st.session_state.gen_start_time
                tu = st.session_state.total_token_usage
                token_ph.caption(
                    f"⏱ {elapsed:.0f}s | 📥 输入 {tu['input']:,} | 📤 输出 {tu['output']:,} | 🔥 合计 {tu['input']+tu['output']:,} tokens"
                )
                content_ph.markdown(
                    f'<div class="script-canvas">{accumulated}</div>',
                    unsafe_allow_html=True,
                )
            # 统计集数 + 结构化解析
            st.session_state.episode_list = accumulated
            try:
                from agents.episode_parser import parse_episodes
                st.session_state.episode_cards = parse_episodes(accumulated, total_ep)
                if st.session_state.episode_cards:
                    st.session_state.episode_json_raw = accumulated
                    st.session_state.episode_editor_mode = "visual"
            except Exception:
                st.session_state.episode_cards = []
                st.session_state.episode_editor_mode = "raw"
            ep_count = len(st.session_state.episode_cards) or len(re.findall(r"第\s*\d+\s*集", accumulated))
            _bump_episode_version()          # ← 触发新 widget key
            st.session_state._episode_streaming = False
            st.session_state.gen_elapsed = time.time() - st.session_state.gen_start_time
            has_scores = any(c.conflict_intensity != 5 for c in st.session_state.episode_cards) if st.session_state.episode_cards else False
            score_note = "（含 AI 量化评分）" if has_scores else ""
            st.session_state.status_message = f"分集清单已生成 {score_note}（检测到 {ep_count} 集）！请在左侧审核修改后确认。"
            st.rerun()
        except Exception as exc:
            st.session_state.status_message = f"❌ 分集生成失败: {exc}"
            st.session_state._episode_streaming = False
            st.session_state.workflow_stage = "outline_review"
            st.rerun()

    # ── 流式标题 ──
    if streaming_active:
        st.markdown(f"### {stream_title}")
    else:
        st.markdown("### 🎭 剧本实时预览")

    # ── 卡点三：剧本流式生成 / 静态展示 ──
    if streaming_active:
        pass  # 已在上面渲染
    elif st.session_state.script_content:
        st.markdown(
            f'<div class="script-canvas">{st.session_state.script_content}</div>',
            unsafe_allow_html=True,
        )
    elif st.session_state.workflow_stage == "generating" and st.session_state.script_generating:
        # ---- 流式生成（逐 token 打字机） ----
        total_ep = st.session_state.total_episodes
        total_batches_script = max((total_ep + SCRIPT_BATCH_SIZE - 1) // SCRIPT_BATCH_SIZE, 1)

        def _detect_completed_episodes(text: str) -> set[int]:
            """从剧本文本中检测已生成完整的集数。
            匹配单集标题「第 N 集：」或「第 N 集\n」，排除批次头「第 X~Y 集」。
            """
            completed = set()
            # 匹配「第 N 集」后面跟中文冒号、英文冒号或换行（不是 ~ 或 ～）
            for m in re.finditer(r'第\s*(\d+)\s*集(?!\s*[~～\d])', text):
                completed.add(int(m.group(1)))
            return completed

        def _ep_status_html(completed: set[int], total: int) -> str:
            """生成可折叠的集数完成度 HTML。"""
            done = len(completed)
            chips = []
            for ep in range(1, total + 1):
                if ep in completed:
                    chips.append(
                        f'<span style="display:inline-block;background:#d4edda;color:#155724;'
                        f'padding:2px 7px;border-radius:3px;font-size:0.75rem;margin:1px;">✓ {ep}</span>'
                    )
                else:
                    chips.append(
                        f'<span style="display:inline-block;background:#e2e3e5;color:#6c757d;'
                        f'padding:2px 7px;border-radius:3px;font-size:0.75rem;margin:1px;">· {ep}</span>'
                    )
            return (
                f'<details style="margin-bottom:10px;">'
                f'<summary style="cursor:pointer;font-size:0.85rem;font-weight:600;">'
                f'📋 各集输出进度（{done}/{total} 集）</summary>'
                f'<div style="margin-top:6px;line-height:1.8;">{"".join(chips)}</div>'
                f'</details>'
            )

        # 防 rerun 重启：如果正在流式中，只展示已累积内容，不重建生成器
        if st.session_state.get("_script_streaming", False):
            script_placeholder = st.empty()
            token_placeholder = st.empty()
            elapsed = time.time() - st.session_state.gen_start_time
            tu = st.session_state.total_token_usage
            token_placeholder.caption(
                f"⏱ {elapsed:.0f}s | "
                f"📥 输入 {tu['input']:,} | 📤 输出 {tu['output']:,} | "
                f"🔥 合计 {tu['input'] + tu['output']:,} tokens"
            )
            script_placeholder.markdown(
                f'<div class="script-canvas">{st.session_state._script_accumulated}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.session_state._script_streaming = True
            st.session_state._script_accumulated = ""
            batch_count = 0
            test_mode = st.session_state.test_mode

            # ── 进度条 ──
            progress_bar = st.progress(0, text=f"⏳ 准备生成... 0/{total_batches_script} 批")
            # ── 集数完成度面板 ──
            ep_status_placeholder = st.empty()

            if test_mode:
                stream = generate_mock_script_stream(
                    topic=st.session_state.topic,
                    episode_list=st.session_state.episode_list,
                    total_episodes=total_ep,
                    end_ep=total_ep,
                )
                st.session_state.generation_log.append((time.time(), "🧪", f"测试模式：生成 {total_ep} 集 Mock 剧本"))
            else:
                llm = get_llm_params()
                orch = Orchestrator(
                    on_event=make_event_handler(),
                    total_episodes=total_ep,
                    **llm,
                )
                stream = orch.generate_script_stream(
                    topic=st.session_state.topic,
                    episode_list=st.session_state.episode_list,
                    end_ep=total_ep,
                )
            script_placeholder = st.empty()
            token_placeholder = st.empty()

            def _auto_scroll():
                """注入 JS 将页面滚到底部，让用户始终看到最新输出。"""
                components.html("""
<script>
(function() {
    try {
        var el = parent.document.querySelector('[data-testid="stAppViewContainer"]');
        if (el) el.scrollTop = el.scrollHeight;
    } catch(e) {}
    try {
        parent.scrollTo(0, parent.document.body.scrollHeight);
    } catch(e) {}
})();
</script>
""", height=0)

            try:
                last_rendered_len = 0  # 增量渲染追踪：上次渲染时的字符数
                for chunk, batch_usage in stream:
                    st.session_state._script_accumulated += chunk
                    if batch_usage:
                        batch_count += 1
                        st.session_state.total_token_usage["input"] += batch_usage.input_tokens
                        st.session_state.total_token_usage["output"] += batch_usage.output_tokens

                    cur_len = len(st.session_state._script_accumulated)
                    # 增量渲染策略：
                    # 1. 批次完成时（batch_usage 有值）→ 必定渲染（含进度条/集数面板/token 统计）
                    # 2. 内容增长超过 INCREMENTAL_RENDER_CHARS → 渲染画布（让用户看到实时输出）
                    INCREMENTAL_RENDER_CHARS = 400
                    is_batch_done = batch_usage is not None
                    should_render_incremental = (cur_len - last_rendered_len) >= INCREMENTAL_RENDER_CHARS

                    if is_batch_done or should_render_incremental:
                        if is_batch_done:
                            # 进度条
                            pct = batch_count / total_batches_script
                            progress_bar.progress(pct, text=f"⏳ 生成中... {batch_count}/{total_batches_script} 批")
                            # 集数完成度
                            completed = _detect_completed_episodes(st.session_state._script_accumulated)
                            ep_status_placeholder.markdown(
                                _ep_status_html(completed, total_ep),
                                unsafe_allow_html=True,
                            )
                            # Token 信息
                            elapsed = time.time() - st.session_state.gen_start_time
                            tu = st.session_state.total_token_usage
                            token_placeholder.caption(
                                f"⏱ {elapsed:.0f}s | "
                                f"📥 输入 {tu['input']:,} | 📤 输出 {tu['output']:,} | "
                                f"🔥 合计 {tu['input'] + tu['output']:,} tokens"
                            )
                        # 剧本画布（批次完成 + 增量都渲染）
                        script_placeholder.markdown(
                            f'<div class="script-canvas">{st.session_state._script_accumulated}</div>',
                            unsafe_allow_html=True,
                        )
                        # 自动滚屏到底部
                        _auto_scroll()
                        last_rendered_len = cur_len

                # 完成：最终更新进度条和集数面板
                completed = _detect_completed_episodes(st.session_state._script_accumulated)
                progress_bar.progress(1.0, text="✅ 生成完毕！")
                ep_status_placeholder.markdown(
                    _ep_status_html(completed, total_ep),
                    unsafe_allow_html=True,
                )
                st.session_state.script_content = st.session_state._script_accumulated
                st.session_state.script_generating = False
                st.session_state._script_streaming = False
                st.session_state.gen_elapsed = time.time() - st.session_state.gen_start_time
                st.session_state.workflow_stage = "done"
                st.session_state.status_message = "✅ 剧本生成完毕！可下载或回看。"

                # ---- 自动保存 ----
                try:
                    active_cfg = get_active_config(st.session_state.get("active_llm_model", ""))
                    saved = save_script(
                        topic=st.session_state.topic,
                        outline=st.session_state.outline,
                        episode_list=st.session_state.episode_list,
                        script_content=st.session_state._script_accumulated,
                        total_input_tokens=st.session_state.total_token_usage["input"],
                        total_output_tokens=st.session_state.total_token_usage["output"],
                        total_elapsed=st.session_state.gen_elapsed,
                        model=active_cfg.get("model", "unknown"),
                    )
                    st.session_state.status_message += f" 📁 已保存到 `{os.path.basename(saved)}`"
                except Exception as save_err:
                    st.session_state.status_message += f" ⚠️ 保存失败: {save_err}"

                st.rerun()
            except Exception as exc:
                st.session_state.script_content = st.session_state._script_accumulated or "（生成中断）"
                st.session_state.script_generating = False
                st.session_state._script_streaming = False
                st.session_state.workflow_stage = "done"
                st.session_state.status_message = f"⚠️ 生成中断: {exc}"
                st.rerun()
    else:
        placeholder_text = {
            "input": "编剧提交题材后，Agent 矩阵将自动构思…\n\n剧本将在此处以打字机效果流式呈现。",
            "planning": "🧠 Agent 矩阵正在构思中，请稍候…",
            "outline_review": "📋 请在左侧审核并确认大纲。",
            "episode_review": "📑 请在左侧审核分集清单，确认后开始生成剧本。",
            "done": "✅ 剧本已生成完毕，点击左侧下载。",
        }.get(st.session_state.workflow_stage, "等待编剧输入题材…")
        st.markdown(f'<div class="script-canvas placeholder">{placeholder_text}</div>', unsafe_allow_html=True)

    # ── 流式进度 ──
    if st.session_state.script_generating:
        st.caption("⏳ 流式生成进行中…")


# ============================================================================
# 侧边栏
# ============================================================================

with st.sidebar:
    st.markdown("## ⚙️ 创作控制台")

    # ── 题材输入 ──
    st.markdown("#### 📝 输入题材")
    st.session_state.topic = st.text_input(
        "短剧题材或一句话梗概：",
        value=st.session_state.topic,
        placeholder="重生之都市神医、豪门千金逆袭…",
        key="sidebar_topic",
        disabled=st.session_state.topic_submitted and st.session_state.workflow_stage != "input",
    )
    ca, cb = st.columns(2)
    with ca:
        if st.button("🚀 提交题材", use_container_width=True, key="btn_submit"):
            if st.session_state.topic.strip():
                st.session_state.topic_submitted = True
                st.session_state.workflow_stage = "planning"
                st.session_state.status_message = f"「{st.session_state.topic}」已提交，Agent 矩阵构思中…"
                st.rerun()
            else: st.warning("请输入题材")
    with cb:
        if st.button("🔄 重置", use_container_width=True, key="btn_reset"):
            reset_workflow()
            st.rerun()

    # ── 集数选择 ──
    st.markdown("#### 🎬 剧本集数")
    ep_option = st.selectbox(
        "选择总集数：",
        options=["20 集（短篇）", "30 集（精简）", "100 集（标准）", "自定义"],
        index=0,
        key="ep_select",
        disabled=st.session_state.topic_submitted and st.session_state.workflow_stage != "input",
    )
    if ep_option == "自定义":
        custom_ep = st.number_input(
            "自定义集数", min_value=5, max_value=200, value=st.session_state.total_episodes,
            step=5, key="ep_custom",
            disabled=st.session_state.topic_submitted and st.session_state.workflow_stage != "input",
        )
        st.session_state.total_episodes = custom_ep
    else:
        st.session_state.total_episodes = int(ep_option.split(" ")[0])
    st.caption(f"当前设置：**{st.session_state.total_episodes} 集**")

    st.divider()

    # ── 测试模式 ──
    st.session_state.test_mode = st.checkbox(
        "🧪 测试模式（Mock 数据，不烧 Token）",
        value=st.session_state.test_mode,
        help="开启后所有 AI 生成使用本地假数据，用于快速调试验证 UI 流程，不消耗 API 额度。",
    )
    if st.session_state.test_mode:
        st.caption("⚠️ 测试模式已开启 — 不会调用真实 LLM")

    st.divider()

    # ── LLM 配置 ──
    with st.expander("🔌 LLM 模型配置", expanded=False):
        configs = load_configs()
        active_model = st.session_state.get("active_llm_model", "")
        if not active_model and configs:
            active_model = configs[0]["model"]

        # 当前激活的模型
        model_options = [f"{c['name']} ({c['model']})" for c in configs]
        model_map = {f"{c['name']} ({c['model']})": c["model"] for c in configs}
        current_label = next((l for l, m in model_map.items() if m == active_model), model_options[0] if model_options else "")

        selected_label = st.selectbox(
            "当前模型：", options=model_options,
            index=model_options.index(current_label) if current_label in model_options else 0,
            key="llm_selector",
        )
        if selected_label and model_map.get(selected_label):
            st.session_state.active_llm_model = model_map[selected_label]

        active_cfg = get_active_config(st.session_state.active_llm_model)
        st.caption(f"📍 API Base: `{active_cfg.get('api_base', 'N/A')}`")

        st.divider()

        # 新增配置
        st.markdown("##### ➕ 新增模型")
        with st.form("llm_add_form", clear_on_submit=True):
            new_name = st.text_input("配置名称", placeholder="如：我的 GPT-5", key="llm_name")
            new_model = st.text_input("模型 ID", placeholder="如：openai/gpt-5", key="llm_model")
            new_key = st.text_input("API Key", type="password", placeholder="sk-…", key="llm_key")
            new_base = st.text_input("API Base URL", placeholder="https://api.openai.com/v1", key="llm_base")
            if st.form_submit_button("💾 保存配置", use_container_width=True):
                if new_name and new_model and new_key and new_base:
                    add_config(new_name, new_model, new_key, new_base)
                    st.session_state.active_llm_model = new_model
                    st.rerun()
                else:
                    st.warning("所有字段均为必填")

        # 删除自定义配置（默认配置不可删）
        default_models = {"openai/deepseek-v4-pro"}
        user_configs = [c for c in configs if c["model"] not in default_models]
        if user_configs:
            st.markdown("##### 🗑 删除配置")
            del_options = [f"{c['name']} ({c['model']})" for c in user_configs]
            del_map = {f"{c['name']} ({c['model']})": c["model"] for c in user_configs}
            del_choice = st.selectbox("选择要删除的配置：", options=del_options, key="llm_del")
            if st.button("🗑 确认删除", use_container_width=True, key="btn_del_llm"):
                if del_choice and del_map.get(del_choice):
                    delete_config(del_map[del_choice])
                    if st.session_state.active_llm_model == del_map[del_choice]:
                        st.session_state.active_llm_model = ""
                    st.rerun()

    st.divider()

    # ── 快速导入 ──
    with st.expander("📥 快速导入（跳过 AI）", expanded=False):
        imported_ol = st.text_area("粘贴大纲：", height=120, placeholder="已有大纲…", key="imp_ol")
        if st.button("📋 导入大纲", use_container_width=True, key="btn_imp_ol"):
            if imported_ol.strip():
                st.session_state.topic = "（导入大纲）"
                st.session_state.topic_submitted = True
                st.session_state.outline = imported_ol.strip()
                _bump_outline_version()              # 触发新 widget key
                st.session_state.episode_list = ""
                _bump_episode_version()              # 清空分集 widget
                st.session_state.workflow_stage = "outline_review"
                st.session_state.status_message = "大纲已导入，请审核后确认。"
                st.rerun()
            else: st.warning("请粘贴大纲")

        imported_ep = st.text_area("粘贴分集清单：", height=120, placeholder="已有分集清单…", key="imp_ep")
        ci1, ci2 = st.columns(2)
        with ci1:
            if st.button("📑 导入分集", use_container_width=True, key="btn_imp_ep"):
                if imported_ep.strip():
                    st.session_state.episode_list = imported_ep.strip()
                    # 尝试结构化解析
                    try:
                        from agents.episode_parser import parse_episodes
                        st.session_state.episode_cards = parse_episodes(imported_ep.strip(), st.session_state.total_episodes)
                        st.session_state.episode_editor_mode = "visual" if st.session_state.episode_cards else "raw"
                    except Exception:
                        st.session_state.episode_cards = []
                    _bump_episode_version()              # 触发新 widget key
                    st.session_state.workflow_stage = "episode_review"
                    st.session_state.status_message = "分集已导入，请审核后确认。"
                    st.rerun()
                else: st.warning("请粘贴分集清单")
        with ci2:
            if st.button("🚀 直通出本", use_container_width=True, key="btn_imp_all"):
                if imported_ol.strip() and imported_ep.strip():
                    st.session_state.topic = "（导入）"
                    st.session_state.topic_submitted = True
                    st.session_state.outline = imported_ol.strip()
                    _bump_outline_version()              # 触发新 widget key
                    st.session_state.outline_confirmed = True
                    st.session_state.episode_list = imported_ep.strip()
                    # 尝试结构化解析
                    try:
                        from agents.episode_parser import parse_episodes
                        st.session_state.episode_cards = parse_episodes(imported_ep.strip(), st.session_state.total_episodes)
                    except Exception:
                        st.session_state.episode_cards = []
                    _bump_episode_version()              # 触发新 widget key
                    st.session_state.episode_confirmed = True
                    st.session_state.workflow_stage = "generating"
                    st.rerun()
                else: st.warning("请同时粘贴大纲和分集清单")

    st.divider()

    # ── 当前阶段 ──
    st.caption(f"当前阶段：{st.session_state.workflow_stage}")

    # ── 历史记录 ──
    st.divider()
    st.markdown("#### 📚 生成历史")
    records = list_generations(limit=10)
    if records:
        for rec in records:
            # 显示文件夹名（剧名+时间戳）
            label = f"📁 {rec.title[:30]}"
            if st.button(label, key=f"hist_{rec.id}", use_container_width=True):
                script = get_generation_script(rec.id)
                if script:
                    st.session_state.script_content = script
                    st.session_state.workflow_stage = "done"
                    st.session_state.status_message = f"已加载：{rec.title}"
                else:
                    # 尝试加载大纲或分集
                    ep = get_checkpoint_content(rec.id, "episodes")
                    ol = get_checkpoint_content(rec.id, "outline")
                    if ep:
                        st.session_state.episode_list = ep
                        # 尝试结构化解析历史数据
                        try:
                            from agents.episode_parser import parse_episodes
                            st.session_state.episode_cards = parse_episodes(ep, st.session_state.total_episodes)
                            st.session_state.episode_editor_mode = "visual" if st.session_state.episode_cards else "raw"
                        except Exception:
                            st.session_state.episode_cards = []
                        _bump_episode_version()
                    if ol:
                        st.session_state.outline = ol
                        _bump_outline_version()
                        st.session_state.topic = rec.topic
                        st.session_state.topic_submitted = True
                        st.session_state.outline_confirmed = True
                    st.session_state.status_message = f"已加载项目：{rec.title}（剧本未完成）"
                st.rerun()
    else:
        st.caption("暂无生成记录。")
    st.caption(f"💾 保存路径：`generations/`")

    st.divider()

    with st.expander("📖 使用说明"):
        st.markdown("""
        1. 输入题材 → 提交
        2. 审核 AI 生成的大纲 → 确认
        3. 审核百集分集清单 → 确认
        4. 等待流式剧本生成 → 下载
        5. 也可用「快速导入」跳过 AI 构思
        """)

    with st.expander("🔧 调试"):
        new_stage = st.selectbox("切换阶段", options=["input","planning","outline_review","episode_review","generating","done"], index=get_stage_index(st.session_state.workflow_stage))
        if st.button("应用", key="debug_apply"):
            st.session_state.workflow_stage = new_stage
            st.rerun()
