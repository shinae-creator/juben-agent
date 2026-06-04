"""
短剧 Agent 创作工作站 — Streamlit 前端
=========================================
编剧无需终端，纯网页端完成：题材输入 → 大纲审定 → 分集审定 → 流式出本 → 一键下载。

工作流状态机：
  input           — 等待编剧输入题材
  planning        — Agent 矩阵正在构思（前端轮询/等待）
  outline_review  — 卡点一：百集主线大纲，编剧可修改并确认
  episode_review  — 卡点二：分集挂钩点清单，编剧可修改并确认
  generating      — 全放行，后端流式生成剧本
  done            — 剧本完成，可下载
"""

import streamlit as st
from datetime import datetime
from typing import Optional

from agents import Orchestrator

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
# 自定义 CSS 样式
# ============================================================================

CUSTOM_CSS = """
<style>
    /* ----- 全局字体与底色 ----- */
    html, body, [class*="css"] {
        font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
    }

    /* ----- 主标题 ----- */
    .main-title {
        font-size: 2rem;
        font-weight: 700;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin-bottom: 0.25rem;
    }
    .sub-title {
        color: #888;
        font-size: 0.9rem;
        margin-bottom: 1.5rem;
    }

    /* ----- 进度步骤条 ----- */
    .stepper-container {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 1rem 2rem;
        margin: 1rem 0 2rem 0;
        background: #f8f9fa;
        border-radius: 12px;
    }
    .step-item {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 0.3rem;
        flex: 1;
        position: relative;
    }
    .step-circle {
        width: 36px;
        height: 36px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1rem;
        font-weight: 700;
        transition: all 0.3s ease;
        border: 3px solid #ddd;
        background: #fff;
        color: #bbb;
    }
    .step-circle.active {
        border-color: #667eea;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: #fff;
        box-shadow: 0 0 12px rgba(102,126,234,0.4);
    }
    .step-circle.done {
        border-color: #28a745;
        background: #28a745;
        color: #fff;
    }
    .step-label {
        font-size: 0.75rem;
        color: #999;
        text-align: center;
    }
    .step-label.active {
        color: #667eea;
        font-weight: 600;
    }
    .step-label.done {
        color: #28a745;
    }
    .step-connector {
        flex: 0 0 40px;
        height: 3px;
        background: #ddd;
        margin: 0 -4px;
        margin-bottom: 1.2rem;
    }
    .step-connector.done {
        background: #28a745;
    }

    /* ----- 卡片容器 ----- */
    .checkpoint-card {
        background: #fff;
        border: 1px solid #e8e8e8;
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1.2rem;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        transition: box-shadow 0.2s ease;
    }
    .checkpoint-card:hover {
        box-shadow: 0 4px 16px rgba(0,0,0,0.08);
    }
    .checkpoint-card.locked {
        opacity: 0.55;
        pointer-events: none;
        filter: grayscale(40%);
    }
    .checkpoint-card.active {
        border-color: #667eea;
        box-shadow: 0 0 0 3px rgba(102,126,234,0.12);
    }

    .card-badge {
        display: inline-block;
        padding: 0.2rem 0.7rem;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        margin-bottom: 0.6rem;
    }
    .badge-checkpoint {
        background: #eef0ff;
        color: #667eea;
    }
    .badge-done {
        background: #e6f9ed;
        color: #28a745;
    }
    .badge-pending {
        background: #f5f5f5;
        color: #999;
    }

    /* ----- 右侧剧本画布 ----- */
    .script-canvas {
        background: #fcfcfc;
        border: 1px solid #e8e8e8;
        border-radius: 12px;
        padding: 1.5rem;
        min-height: 420px;
        max-height: 72vh;
        overflow-y: auto;
        font-family: "Source Code Pro", "SF Mono", "Consolas", monospace;
        font-size: 0.85rem;
        line-height: 1.8;
        white-space: pre-wrap;
        color: #333;
    }
    .script-canvas.placeholder {
        display: flex;
        align-items: center;
        justify-content: center;
        color: #ccc;
        font-family: "Segoe UI", "PingFang SC", sans-serif;
        font-size: 1rem;
    }

    /* ----- 侧边栏 ----- */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #fafbff 0%, #f0f2ff 100%);
    }
    .sidebar-header {
        font-size: 1.2rem;
        font-weight: 700;
        color: #667eea;
        margin-bottom: 1rem;
    }

    /* ----- 按钮 ----- */
    .stButton > button {
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.2s ease;
    }
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(102,126,234,0.3);
    }
</style>
"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ============================================================================
# Session State 初始化（防刷新丢失）
# ============================================================================

DEFAULTS = {
    # 编剧输入
    "topic": "",
    "topic_submitted": False,
    # 工作流阶段
    "workflow_stage": "input",  # input | planning | outline_review | episode_review | generating | done
    # 卡点一：大纲
    "outline": "",
    "outline_confirmed": False,
    # 卡点二：分集清单
    "episode_list": "",
    "episode_confirmed": False,
    # 剧本输出
    "script_content": "",
    "script_generating": False,
    # 日志
    "status_message": "",
}

for key, default in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = default


# ============================================================================
# Agent 自动调度钩子
# 在 UI 渲染前执行：根据当前阶段自动触发 Agent 矩阵调用。
# ============================================================================

# ---- 阶段 planning：自动调用爆款策划 Agent ----
if st.session_state.workflow_stage == "planning":
    orch = Orchestrator()
    with st.spinner("🧠 爆款策划 Agent 正在构思百集主线大纲…"):
        try:
            st.session_state.outline = orch.generate_outline(st.session_state.topic)
            st.session_state.workflow_stage = "outline_review"
            st.session_state.status_message = "大纲已生成！请在左侧卡片中审核修改，确认后进入分集审定。"
            st.rerun()
        except Exception as exc:
            st.session_state.status_message = f"❌ Agent 调用失败: {exc}"
            st.session_state.workflow_stage = "input"
            st.rerun()

# ---- 阶段 episode_review：自动调用分集架构师 Agent ----
if (
    st.session_state.workflow_stage == "episode_review"
    and not st.session_state.episode_list
):
    orch = Orchestrator()
    with st.spinner("📑 分集架构师 Agent 正在切分 100 集卡点清单…"):
        try:
            st.session_state.episode_list = orch.generate_episodes(
                st.session_state.outline
            )
            st.session_state.status_message = "百集卡点清单已生成！请在左侧卡片中审核修改，确认后开始生成剧本。"
            st.rerun()
        except Exception as exc:
            st.session_state.status_message = f"❌ 分集生成失败: {exc}"
            st.session_state.workflow_stage = "outline_review"
            st.rerun()

# ---- 阶段 generating：自动启动流式剧本生成 ----
if (
    st.session_state.workflow_stage == "generating"
    and not st.session_state.script_generating
):
    st.session_state.script_generating = True
    st.session_state.script_content = ""  # 清空旧内容
    st.rerun()


# ============================================================================
# 辅助函数
# ============================================================================

def reset_workflow():
    """重置整个工作流，回到初始输入状态。"""
    for key, default in DEFAULTS.items():
        st.session_state[key] = default


def get_stage_index(stage: str) -> int:
    """返回阶段在进度条中的索引。"""
    order = ["input", "planning", "outline_review", "episode_review", "generating", "done"]
    return order.index(stage) if stage in order else 0


# ============================================================================
# 渲染：顶部标题
# ============================================================================

st.markdown('<p class="main-title">🎬 短剧 Agent 创作工作站</p>', unsafe_allow_html=True)
st.markdown(
    f'<p class="sub-title">Agent 矩阵全自动构思 · 编剧网页控场 · 一键出本 '
    f'<span style="color:#667eea;">|</span> {datetime.now().strftime("%Y-%m-%d %H:%M")}</p>',
    unsafe_allow_html=True,
)

# ============================================================================
# 渲染：进度步骤条
# ============================================================================

STEPS = [
    ("input",           "📝", "输入题材"),
    ("planning",        "🧠", "AI 构思"),
    ("outline_review",  "📋", "大纲审定"),
    ("episode_review",  "📑", "分集审定"),
    ("generating",      "✍️", "生成剧本"),
    ("done",            "✅", "完成"),
]

current_idx = get_stage_index(st.session_state.workflow_stage)

stepper_html = '<div class="stepper-container">'
for i, (stage, icon, label) in enumerate(STEPS):
    if i > 0:
        conn_class = "done" if i <= current_idx else ""
        stepper_html += f'<div class="step-connector {conn_class}"></div>'

    if i < current_idx:
        circle_class = "done"
        label_class = "done"
        circle_content = "✓"
    elif i == current_idx:
        circle_class = "active"
        label_class = "active"
        circle_content = icon
    else:
        circle_class = ""
        label_class = ""
        circle_content = icon

    stepper_html += (
        f'<div class="step-item">'
        f'<div class="step-circle {circle_class}">{circle_content}</div>'
        f'<div class="step-label {label_class}">{label}</div>'
        f'</div>'
    )
stepper_html += '</div>'
st.markdown(stepper_html, unsafe_allow_html=True)

# ============================================================================
# 主布局：左栏（卡点卡片） + 右栏（剧本画布）
# ============================================================================

left_col, right_col = st.columns([2, 3], gap="medium")

# ========================================================================
# 左侧：卡点卡片区
# ========================================================================

with left_col:
    # ----- 状态提示 -----
    if st.session_state.status_message:
        st.info(st.session_state.status_message)

    # ============================================================
    # 卡片一：大纲审定 (卡点一)
    # ============================================================
    outline_locked = get_stage_index(st.session_state.workflow_stage) < get_stage_index("outline_review")
    outline_active = st.session_state.workflow_stage == "outline_review"
    outline_done = get_stage_index(st.session_state.workflow_stage) > get_stage_index("outline_review")

    card_class = "checkpoint-card"
    if outline_locked:
        card_class += " locked"
    elif outline_active:
        card_class += " active"

    st.markdown(f'<div class="{card_class}">', unsafe_allow_html=True)

    # 卡片标题行
    col_title, col_badge = st.columns([3, 1])
    with col_title:
        st.markdown("### 📋 卡点一 · 百集主线大纲")
    with col_badge:
        if outline_done:
            st.markdown('<span class="card-badge badge-done">✓ 已确认</span>', unsafe_allow_html=True)
        elif outline_active:
            st.markdown('<span class="card-badge badge-checkpoint">⏳ 待审定</span>', unsafe_allow_html=True)
        else:
            st.markdown('<span class="card-badge badge-pending">🔒 等待中</span>', unsafe_allow_html=True)

    # 大纲文本域（编剧可直接修改）
    if outline_done:
        st.text_area(
            "大纲内容（已确认）",
            value=st.session_state.outline,
            height=220,
            disabled=True,
            key="outline_display_done",
        )
    elif not outline_locked:
        st.session_state.outline = st.text_area(
            "AI 生成的大纲，您可以直接在下方编辑修改：",
            value=st.session_state.outline,
            height=220,
            placeholder="Agent 矩阵正在构思中，大纲将在此呈现…",
            key="outline_editor",
        )
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("✅ 确认大纲，进入下一步", use_container_width=True, key="btn_confirm_outline"):
                if st.session_state.outline.strip():
                    st.session_state.outline_confirmed = True
                    st.session_state.workflow_stage = "episode_review"
                    st.session_state.status_message = "大纲已确认！请审核分集挂钩点清单。"
                    st.rerun()
                else:
                    st.warning("大纲内容不能为空，请等待 AI 生成或手动输入。")
        with col_btn2:
            if st.button("🔄 让 AI 重新构思", use_container_width=True, key="btn_regenerate_outline"):
                st.session_state.workflow_stage = "planning"
                st.session_state.status_message = "Agent 矩阵正在重新构思…"
                st.rerun()
    else:
        st.text_area(
            "大纲内容",
            value="（请先在侧边栏提交题材，触发 AI 构思）",
            height=220,
            disabled=True,
            key="outline_placeholder",
        )

    st.markdown('</div>', unsafe_allow_html=True)

    # ============================================================
    # 卡片二：分集审定 (卡点二)
    # ============================================================
    episode_locked = get_stage_index(st.session_state.workflow_stage) < get_stage_index("episode_review")
    episode_active = st.session_state.workflow_stage == "episode_review"
    episode_done = get_stage_index(st.session_state.workflow_stage) > get_stage_index("episode_review")

    card_class2 = "checkpoint-card"
    if episode_locked:
        card_class2 += " locked"
    elif episode_active:
        card_class2 += " active"

    st.markdown(f'<div class="{card_class2}">', unsafe_allow_html=True)

    col_title2, col_badge2 = st.columns([3, 1])
    with col_title2:
        st.markdown("### 📑 卡点二 · 分集挂钩点清单")
    with col_badge2:
        if episode_done:
            st.markdown('<span class="card-badge badge-done">✓ 已确认</span>', unsafe_allow_html=True)
        elif episode_active:
            st.markdown('<span class="card-badge badge-checkpoint">⏳ 待审定</span>', unsafe_allow_html=True)
        else:
            st.markdown('<span class="card-badge badge-pending">🔒 等待中</span>', unsafe_allow_html=True)

    if episode_done:
        st.text_area(
            "分集清单（已确认）",
            value=st.session_state.episode_list,
            height=280,
            disabled=True,
            key="episode_display_done",
        )
    elif not episode_locked:
        st.session_state.episode_list = st.text_area(
            "100 集分集卡点清单（含每集核心冲突与结尾悬念），您可以直接编辑：",
            value=st.session_state.episode_list,
            height=280,
            placeholder="大纲确认后，AI 将自动切分 100 集卡点清单…",
            key="episode_editor",
        )
        col_btn3, col_btn4, col_btn5 = st.columns([1, 1, 1])
        with col_btn3:
            if st.button("✅ 确认分集，开始出本", use_container_width=True, key="btn_confirm_episode"):
                if st.session_state.episode_list.strip():
                    st.session_state.episode_confirmed = True
                    st.session_state.workflow_stage = "generating"
                    st.session_state.status_message = "分集已确认！Agent 矩阵正在并发生成剧本对白…"
                    st.rerun()
                else:
                    st.warning("分集清单不能为空。")
        with col_btn4:
            if st.button("🔄 重新切分", use_container_width=True, key="btn_regenerate_episode"):
                st.session_state.status_message = "分集架构师正在重新切分…"
                st.rerun()
        with col_btn5:
            if st.button("↩ 返回修改大纲", use_container_width=True, key="btn_back_to_outline"):
                st.session_state.workflow_stage = "outline_review"
                st.session_state.episode_confirmed = False
                st.session_state.status_message = "已返回大纲审定，请修改后重新确认。"
                st.rerun()
    else:
        st.text_area(
            "分集清单",
            value="（请先确认大纲后解锁此步骤）",
            height=280,
            disabled=True,
            key="episode_placeholder",
        )

    st.markdown('</div>', unsafe_allow_html=True)

    # ============================================================
    # 「开始生成 / 下载」操作区
    # ============================================================
    if st.session_state.workflow_stage == "generating":
        st.markdown('<div class="checkpoint-card active">', unsafe_allow_html=True)
        st.markdown("### ✍️ 剧本生成中…")
        if st.button("⏹ 停止生成", use_container_width=True, key="btn_stop_generate"):
            st.session_state.script_generating = False
            st.session_state.workflow_stage = "done"
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    if st.session_state.workflow_stage == "done" and st.session_state.script_content:
        st.markdown('<div class="checkpoint-card">', unsafe_allow_html=True)
        st.markdown("### 📦 剧本已完成")
        st.download_button(
            label="⬇️ 一键下载剧本（TXT）",
            data=st.session_state.script_content,
            file_name=f"短剧剧本_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            mime="text/plain",
            use_container_width=True,
            key="btn_download",
        )
        st.markdown('</div>', unsafe_allow_html=True)

# ========================================================================
# 右侧：剧本流式展示画布
# ========================================================================

with right_col:
    st.markdown("### 🎭 剧本实时预览")

    if st.session_state.script_content:
        st.markdown(
            f'<div class="script-canvas">{st.session_state.script_content}</div>',
            unsafe_allow_html=True,
        )
    elif st.session_state.workflow_stage == "generating" and st.session_state.script_generating:
        # ---- 流式生成 ----
        orch = Orchestrator()
        script_placeholder = st.empty()
        accumulated = ""

        try:
            stream = orch.generate_script_stream(
                topic=st.session_state.topic,
                episode_list=st.session_state.episode_list,
            )
            for chunk in stream:
                accumulated += chunk
                script_placeholder.markdown(
                    f'<div class="script-canvas">{accumulated}</div>',
                    unsafe_allow_html=True,
                )
            st.session_state.script_content = accumulated
            st.session_state.script_generating = False
            st.session_state.workflow_stage = "done"
            st.session_state.status_message = "✅ 剧本生成完毕！点击左侧按钮下载。"
            st.rerun()
        except Exception as exc:
            st.session_state.script_content = accumulated or "（生成中断）"
            st.session_state.script_generating = False
            st.session_state.workflow_stage = "done"
            st.session_state.status_message = f"⚠️ 生成中断: {exc}"
            st.rerun()
    else:
        placeholder_text = {
            "input": "编剧提交题材后，Agent 矩阵将自动构思…\n\n剧本将在此处以打字机效果流式呈现。",
            "planning": "🧠 Agent 矩阵正在构思中，请稍候…\n\n• 爆款策划 Agent：分析市场热点，定位题材方向\n• 分集架构师 Agent：拆解故事为 100 集结构",
            "outline_review": "📋 请在左侧审核并确认大纲，确认后将进入分集审定。",
            "episode_review": "📑 请在左侧审核分集清单，确认后即可开始生成完整剧本。",
            "done": "✅ 剧本已生成完毕，请点击左侧按钮下载。",
        }.get(st.session_state.workflow_stage, "等待编剧输入题材…")

        st.markdown(
            f'<div class="script-canvas placeholder">{placeholder_text}</div>',
            unsafe_allow_html=True,
        )

    # 状态栏
    if st.session_state.script_generating:
        st.caption("⏳ 流式生成进行中…")

# ============================================================================
# 侧边栏：题材输入 & 工作流控制
# ============================================================================

with st.sidebar:
    st.markdown('<p class="sidebar-header">⚙️ 创作控制台</p>', unsafe_allow_html=True)

    # ----- 题材输入区 -----
    st.markdown("#### 📝 第一步：输入题材")
    st.session_state.topic = st.text_input(
        "请输入短剧题材或一句话梗概：",
        value=st.session_state.topic,
        placeholder="例如：重生之都市神医、豪门千金逆袭、穿越古代做首富…",
        key="sidebar_topic_input",
        disabled=st.session_state.topic_submitted and st.session_state.workflow_stage != "input",
    )

    col_a, col_b = st.columns([1, 1])
    with col_a:
        if st.button("🚀 提交题材", use_container_width=True, key="btn_submit_topic"):
            if st.session_state.topic.strip():
                st.session_state.topic_submitted = True
                st.session_state.workflow_stage = "planning"
                st.session_state.status_message = f"题材「{st.session_state.topic}」已提交，Agent 矩阵正在构思…"
                st.rerun()
            else:
                st.warning("请输入题材或梗概。")
    with col_b:
        if st.button("🔄 重置", use_container_width=True, key="btn_reset"):
            reset_workflow()
            st.rerun()

    st.divider()

    # ----- 工作流阶段指示 -----
    st.markdown("#### 🎯 当前阶段")
    stage_labels = {
        "input": "⏸ 等待输入题材",
        "planning": "⏳ Agent 矩阵构思中…",
        "outline_review": "📋 卡点一：大纲审定",
        "episode_review": "📑 卡点二：分集审定",
        "generating": "✍️ 全自动生成剧本",
        "done": "✅ 剧本已完成",
    }
    st.info(stage_labels.get(st.session_state.workflow_stage, "未知"))

    # ----- 快捷跳转（调试用） -----
    with st.expander("🔧 调试面板"):
        new_stage = st.selectbox(
            "手动切换阶段：",
            options=["input", "planning", "outline_review", "episode_review", "generating", "done"],
            index=get_stage_index(st.session_state.workflow_stage),
            key="debug_stage_select",
        )
        if st.button("应用阶段切换", key="btn_debug_stage"):
            st.session_state.workflow_stage = new_stage
            st.rerun()

        st.caption("提示：调试面板仅开发阶段使用，上线后移除。")

    st.divider()

    # ----- 使用说明 -----
    with st.expander("📖 使用说明"):
        st.markdown("""
        1. **输入题材** — 在侧边栏输入短剧题材或一句话梗概。
        2. **提交题材** — 点击按钮，Agent 矩阵开始自动构思。
        3. **卡点一** — AI 生成百集主线大纲，编剧可直接修改并确认。
        4. **卡点二** — AI 切分 100 集分集挂钩点清单，编剧审核确认。
        5. **生成剧本** — 点击确认后，Agent 矩阵全自动输出对白剧本。
        6. **下载剧本** — 剧本完成后，一键下载为 TXT 文件。
        """)

# ============================================================================
# 底部状态栏
# ============================================================================

st.divider()
col_f1, col_f2, col_f3 = st.columns([2, 1, 1])
with col_f1:
    st.caption(f"当前阶段：{st.session_state.workflow_stage} | 题材：{st.session_state.topic or '（未输入）'}")
with col_f2:
    st.caption(f"大纲：{'✓' if st.session_state.outline_confirmed else '○'}")
with col_f3:
    st.caption(f"分集：{'✓' if st.session_state.episode_confirmed else '○'}")
