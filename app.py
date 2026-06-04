"""
鐭墽 Agent 鍒涗綔宸ヤ綔绔?鈥?Streamlit 鍓嶇
=========================================
缂栧墽鏃犻渶缁堢锛岀函缃戦〉绔畬鎴愶細棰樻潗杈撳叆 鈫?澶х翰瀹″畾 鈫?鍒嗛泦瀹″畾 鈫?娴佸紡鍑烘湰 鈫?涓€閿笅杞姐€?
宸ヤ綔娴佺姸鎬佹満锛?  input           鈥?绛夊緟缂栧墽杈撳叆棰樻潗
  planning        鈥?Agent 鐭╅樀姝ｅ湪鏋勬€濓紙鍓嶇杞/绛夊緟锛?  outline_review  鈥?鍗＄偣涓€锛氱櫨闆嗕富绾垮ぇ绾诧紝缂栧墽鍙慨鏀瑰苟纭
  episode_review  鈥?鍗＄偣浜岋細鍒嗛泦鎸傞挬鐐规竻鍗曪紝缂栧墽鍙慨鏀瑰苟纭
  generating      鈥?鍏ㄦ斁琛岋紝鍚庣娴佸紡鐢熸垚鍓ф湰
  done            鈥?鍓ф湰瀹屾垚锛屽彲涓嬭浇
"""

import streamlit as st
from datetime import datetime
from typing import Optional

from agents import Orchestrator

# ============================================================================
# 椤甸潰鍏ㄥ眬閰嶇疆
# ============================================================================

st.set_page_config(
    page_title="鐭墽 Agent 鍒涗綔宸ヤ綔绔?,
    page_icon="馃幀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================================
# 鑷畾涔?CSS 鏍峰紡
# ============================================================================

CUSTOM_CSS = """
<style>
    /* ----- 鍏ㄥ眬瀛椾綋涓庡簳鑹?----- */
    html, body, [class*="css"] {
        font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
    }

    /* ----- 涓绘爣棰?----- */
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

    /* ----- 杩涘害姝ラ鏉?----- */
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

    /* ----- 鍗＄墖瀹瑰櫒 ----- */
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

    /* ----- 鍙充晶鍓ф湰鐢诲竷 ----- */
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

    /* ----- 渚ц竟鏍?----- */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #fafbff 0%, #f0f2ff 100%);
    }
    .sidebar-header {
        font-size: 1.2rem;
        font-weight: 700;
        color: #667eea;
        margin-bottom: 1rem;
    }

    /* ----- 鎸夐挳 ----- */
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
# Session State 鍒濆鍖栵紙闃插埛鏂颁涪澶憋級
# ============================================================================

DEFAULTS = {
    # 缂栧墽杈撳叆
    "topic": "",
    "topic_submitted": False,
    # 宸ヤ綔娴侀樁娈?    "workflow_stage": "input",  # input | planning | outline_review | episode_review | generating | done
    # 鍗＄偣涓€锛氬ぇ绾?    "outline": "",
    "outline_confirmed": False,
    # 鍗＄偣浜岋細鍒嗛泦娓呭崟
    "episode_list": "",
    "episode_confirmed": False,
    # 鍓ф湰杈撳嚭
    "script_content": "",
    "script_generating": False,
    # 鏃ュ織
    "status_message": "",
}

for key, default in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = default


# ============================================================================
# Agent 鑷姩璋冨害閽╁瓙
# 鍦?UI 娓叉煋鍓嶆墽琛岋細鏍规嵁褰撳墠闃舵鑷姩瑙﹀彂 Agent 鐭╅樀璋冪敤銆?# ============================================================================

# ---- 闃舵 planning锛氳嚜鍔ㄨ皟鐢ㄧ垎娆剧瓥鍒?Agent ----
if st.session_state.workflow_stage == "planning":
    orch = Orchestrator()
    with st.spinner("馃 鐖嗘绛栧垝 Agent 姝ｅ湪鏋勬€濈櫨闆嗕富绾垮ぇ绾测€?):
        try:
            st.session_state.outline = orch.generate_outline(st.session_state.topic)
            st.session_state.workflow_stage = "outline_review"
            st.session_state.status_message = "澶х翰宸茬敓鎴愶紒璇峰湪宸︿晶鍗＄墖涓鏍镐慨鏀癸紝纭鍚庤繘鍏ュ垎闆嗗瀹氥€?
            st.rerun()
        except Exception as exc:
            st.session_state.status_message = f"鉂?Agent 璋冪敤澶辫触: {exc}"
            st.session_state.workflow_stage = "input"
            st.rerun()

# ---- 闃舵 episode_review锛氳嚜鍔ㄨ皟鐢ㄥ垎闆嗘灦鏋勫笀 Agent ----
if (
    st.session_state.workflow_stage == "episode_review"
    and not st.session_state.episode_list
):
    orch = Orchestrator()
    with st.spinner("馃搼 鍒嗛泦鏋舵瀯甯?Agent 姝ｅ湪鍒囧垎 100 闆嗗崱鐐规竻鍗曗€?):
        try:
            st.session_state.episode_list = orch.generate_episodes(
                st.session_state.outline
            )
            st.session_state.status_message = "鐧鹃泦鍗＄偣娓呭崟宸茬敓鎴愶紒璇峰湪宸︿晶鍗＄墖涓鏍镐慨鏀癸紝纭鍚庡紑濮嬬敓鎴愬墽鏈€?
            st.rerun()
        except Exception as exc:
            st.session_state.status_message = f"鉂?鍒嗛泦鐢熸垚澶辫触: {exc}"
            st.session_state.workflow_stage = "outline_review"
            st.rerun()

# ---- 闃舵 generating锛氳嚜鍔ㄥ惎鍔ㄦ祦寮忓墽鏈敓鎴?----
if (
    st.session_state.workflow_stage == "generating"
    and not st.session_state.script_generating
):
    st.session_state.script_generating = True
    st.session_state.script_content = ""  # 娓呯┖鏃у唴瀹?    st.rerun()


# ============================================================================
# 杈呭姪鍑芥暟
# ============================================================================

def reset_workflow():
    """閲嶇疆鏁翠釜宸ヤ綔娴侊紝鍥炲埌鍒濆杈撳叆鐘舵€併€?""
    for key, default in DEFAULTS.items():
        st.session_state[key] = default


def get_stage_index(stage: str) -> int:
    """杩斿洖闃舵鍦ㄨ繘搴︽潯涓殑绱㈠紩銆?""
    order = ["input", "planning", "outline_review", "episode_review", "generating", "done"]
    return order.index(stage) if stage in order else 0


# ============================================================================
# 娓叉煋锛氶《閮ㄦ爣棰?# ============================================================================

st.markdown('<p class="main-title">馃幀 鐭墽 Agent 鍒涗綔宸ヤ綔绔?/p>', unsafe_allow_html=True)
st.markdown(
    f'<p class="sub-title">Agent 鐭╅樀鍏ㄨ嚜鍔ㄦ瀯鎬?路 缂栧墽缃戦〉鎺у満 路 涓€閿嚭鏈?'
    f'<span style="color:#667eea;">|</span> {datetime.now().strftime("%Y-%m-%d %H:%M")}</p>',
    unsafe_allow_html=True,
)

# ============================================================================
# 娓叉煋锛氳繘搴︽楠ゆ潯
# ============================================================================

STEPS = [
    ("input",           "馃摑", "杈撳叆棰樻潗"),
    ("planning",        "馃", "AI 鏋勬€?),
    ("outline_review",  "馃搵", "澶х翰瀹″畾"),
    ("episode_review",  "馃搼", "鍒嗛泦瀹″畾"),
    ("generating",      "鉁嶏笍", "鐢熸垚鍓ф湰"),
    ("done",            "鉁?, "瀹屾垚"),
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
        circle_content = "鉁?
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
# 涓诲竷灞€锛氬乏鏍忥紙鍗＄偣鍗＄墖锛?+ 鍙虫爮锛堝墽鏈敾甯冿級
# ============================================================================

left_col, right_col = st.columns([2, 3], gap="medium")

# ========================================================================
# 宸︿晶锛氬崱鐐瑰崱鐗囧尯
# ========================================================================

with left_col:
    # ----- 鐘舵€佹彁绀?-----
    if st.session_state.status_message:
        st.info(st.session_state.status_message)

    # ============================================================
    # 鍗＄墖涓€锛氬ぇ绾插瀹?(鍗＄偣涓€)
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

    # 鍗＄墖鏍囬琛?    col_title, col_badge = st.columns([3, 1])
    with col_title:
        st.markdown("### 馃搵 鍗＄偣涓€ 路 鐧鹃泦涓荤嚎澶х翰")
    with col_badge:
        if outline_done:
            st.markdown('<span class="card-badge badge-done">鉁?宸茬‘璁?/span>', unsafe_allow_html=True)
        elif outline_active:
            st.markdown('<span class="card-badge badge-checkpoint">鈴?寰呭瀹?/span>', unsafe_allow_html=True)
        else:
            st.markdown('<span class="card-badge badge-pending">馃敀 绛夊緟涓?/span>', unsafe_allow_html=True)

    # 澶х翰鏂囨湰鍩燂紙缂栧墽鍙洿鎺ヤ慨鏀癸級
    if outline_done:
        st.text_area(
            "澶х翰鍐呭锛堝凡纭锛?,
            value=st.session_state.outline,
            height=220,
            disabled=True,
            key="outline_display_done",
        )
    elif not outline_locked:
        st.session_state.outline = st.text_area(
            "AI 鐢熸垚鐨勫ぇ绾诧紝鎮ㄥ彲浠ョ洿鎺ュ湪涓嬫柟缂栬緫淇敼锛?,
            value=st.session_state.outline,
            height=220,
            placeholder="Agent 鐭╅樀姝ｅ湪鏋勬€濅腑锛屽ぇ绾插皢鍦ㄦ鍛堢幇鈥?,
            key="outline_editor",
        )
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("鉁?纭澶х翰锛岃繘鍏ヤ笅涓€姝?, use_container_width=True, key="btn_confirm_outline"):
                if st.session_state.outline.strip():
                    st.session_state.outline_confirmed = True
                    st.session_state.workflow_stage = "episode_review"
                    st.session_state.status_message = "澶х翰宸茬‘璁わ紒璇峰鏍稿垎闆嗘寕閽╃偣娓呭崟銆?
                    st.rerun()
                else:
                    st.warning("澶х翰鍐呭涓嶈兘涓虹┖锛岃绛夊緟 AI 鐢熸垚鎴栨墜鍔ㄨ緭鍏ャ€?)
        with col_btn2:
            if st.button("馃攧 璁?AI 閲嶆柊鏋勬€?, use_container_width=True, key="btn_regenerate_outline"):
                st.session_state.workflow_stage = "planning"
                st.session_state.status_message = "Agent 鐭╅樀姝ｅ湪閲嶆柊鏋勬€濃€?
                st.rerun()
    else:
        st.text_area(
            "澶х翰鍐呭",
            value="锛堣鍏堝湪渚ц竟鏍忔彁浜ら鏉愶紝瑙﹀彂 AI 鏋勬€濓級",
            height=220,
            disabled=True,
            key="outline_placeholder",
        )

    st.markdown('</div>', unsafe_allow_html=True)

    # ============================================================
    # 鍗＄墖浜岋細鍒嗛泦瀹″畾 (鍗＄偣浜?
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
        st.markdown("### 馃搼 鍗＄偣浜?路 鍒嗛泦鎸傞挬鐐规竻鍗?)
    with col_badge2:
        if episode_done:
            st.markdown('<span class="card-badge badge-done">鉁?宸茬‘璁?/span>', unsafe_allow_html=True)
        elif episode_active:
            st.markdown('<span class="card-badge badge-checkpoint">鈴?寰呭瀹?/span>', unsafe_allow_html=True)
        else:
            st.markdown('<span class="card-badge badge-pending">馃敀 绛夊緟涓?/span>', unsafe_allow_html=True)

    if episode_done:
        st.text_area(
            "鍒嗛泦娓呭崟锛堝凡纭锛?,
            value=st.session_state.episode_list,
            height=280,
            disabled=True,
            key="episode_display_done",
        )
    elif not episode_locked:
        st.session_state.episode_list = st.text_area(
            "100 闆嗗垎闆嗗崱鐐规竻鍗曪紙鍚瘡闆嗘牳蹇冨啿绐佷笌缁撳熬鎮康锛夛紝鎮ㄥ彲浠ョ洿鎺ョ紪杈戯細",
            value=st.session_state.episode_list,
            height=280,
            placeholder="澶х翰纭鍚庯紝AI 灏嗚嚜鍔ㄥ垏鍒?100 闆嗗崱鐐规竻鍗曗€?,
            key="episode_editor",
        )
        col_btn3, col_btn4, col_btn5 = st.columns([1, 1, 1])
        with col_btn3:
            if st.button("鉁?纭鍒嗛泦锛屽紑濮嬪嚭鏈?, use_container_width=True, key="btn_confirm_episode"):
                if st.session_state.episode_list.strip():
                    st.session_state.episode_confirmed = True
                    st.session_state.workflow_stage = "generating"
                    st.session_state.status_message = "鍒嗛泦宸茬‘璁わ紒Agent 鐭╅樀姝ｅ湪骞跺彂鐢熸垚鍓ф湰瀵圭櫧鈥?
                    st.rerun()
                else:
                    st.warning("鍒嗛泦娓呭崟涓嶈兘涓虹┖銆?)
        with col_btn4:
            if st.button("馃攧 閲嶆柊鍒囧垎", use_container_width=True, key="btn_regenerate_episode"):
                st.session_state.status_message = "鍒嗛泦鏋舵瀯甯堟鍦ㄩ噸鏂板垏鍒嗏€?
                st.rerun()
        with col_btn5:
            if st.button("鈫?杩斿洖淇敼澶х翰", use_container_width=True, key="btn_back_to_outline"):
                st.session_state.workflow_stage = "outline_review"
                st.session_state.episode_confirmed = False
                st.session_state.status_message = "宸茶繑鍥炲ぇ绾插瀹氾紝璇蜂慨鏀瑰悗閲嶆柊纭銆?
                st.rerun()
    else:
        st.text_area(
            "鍒嗛泦娓呭崟",
            value="锛堣鍏堢‘璁ゅぇ绾插悗瑙ｉ攣姝ゆ楠わ級",
            height=280,
            disabled=True,
            key="episode_placeholder",
        )

    st.markdown('</div>', unsafe_allow_html=True)

    # ============================================================
    # 銆屽紑濮嬬敓鎴?/ 涓嬭浇銆嶆搷浣滃尯
    # ============================================================
    if st.session_state.workflow_stage == "generating":
        st.markdown('<div class="checkpoint-card active">', unsafe_allow_html=True)
        st.markdown("### 鉁嶏笍 鍓ф湰鐢熸垚涓€?)
        if st.button("鈴?鍋滄鐢熸垚", use_container_width=True, key="btn_stop_generate"):
            st.session_state.script_generating = False
            st.session_state.workflow_stage = "done"
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    if st.session_state.workflow_stage == "done" and st.session_state.script_content:
        st.markdown('<div class="checkpoint-card">', unsafe_allow_html=True)
        st.markdown("### 馃摝 鍓ф湰宸插畬鎴?)
        st.download_button(
            label="猬囷笍 涓€閿笅杞藉墽鏈紙TXT锛?,
            data=st.session_state.script_content,
            file_name=f"鐭墽鍓ф湰_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            mime="text/plain",
            use_container_width=True,
            key="btn_download",
        )
        st.markdown('</div>', unsafe_allow_html=True)

# ========================================================================
# 鍙充晶锛氬墽鏈祦寮忓睍绀虹敾甯?# ========================================================================

with right_col:
    st.markdown("### 馃幁 鍓ф湰瀹炴椂棰勮")

    if st.session_state.script_content:
        st.markdown(
            f'<div class="script-canvas">{st.session_state.script_content}</div>',
            unsafe_allow_html=True,
        )
    elif st.session_state.workflow_stage == "generating" and st.session_state.script_generating:
        # ---- 娴佸紡鐢熸垚 ----
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
            st.session_state.status_message = "鉁?鍓ф湰鐢熸垚瀹屾瘯锛佺偣鍑诲乏渚ф寜閽笅杞姐€?
            st.rerun()
        except Exception as exc:
            st.session_state.script_content = accumulated or "锛堢敓鎴愪腑鏂級"
            st.session_state.script_generating = False
            st.session_state.workflow_stage = "done"
            st.session_state.status_message = f"鈿狅笍 鐢熸垚涓柇: {exc}"
            st.rerun()
    else:
        placeholder_text = {
            "input": "缂栧墽鎻愪氦棰樻潗鍚庯紝Agent 鐭╅樀灏嗚嚜鍔ㄦ瀯鎬濃€n\n鍓ф湰灏嗗湪姝ゅ浠ユ墦瀛楁満鏁堟灉娴佸紡鍛堢幇銆?,
            "planning": "馃 Agent 鐭╅樀姝ｅ湪鏋勬€濅腑锛岃绋嶅€欌€n\n鈥?鐖嗘绛栧垝 Agent锛氬垎鏋愬競鍦虹儹鐐癸紝瀹氫綅棰樻潗鏂瑰悜\n鈥?鍒嗛泦鏋舵瀯甯?Agent锛氭媶瑙ｆ晠浜嬩负 100 闆嗙粨鏋?,
            "outline_review": "馃搵 璇峰湪宸︿晶瀹℃牳骞剁‘璁ゅぇ绾诧紝纭鍚庡皢杩涘叆鍒嗛泦瀹″畾銆?,
            "episode_review": "馃搼 璇峰湪宸︿晶瀹℃牳鍒嗛泦娓呭崟锛岀‘璁ゅ悗鍗冲彲寮€濮嬬敓鎴愬畬鏁村墽鏈€?,
            "done": "鉁?鍓ф湰宸茬敓鎴愬畬姣曪紝璇风偣鍑诲乏渚ф寜閽笅杞姐€?,
        }.get(st.session_state.workflow_stage, "绛夊緟缂栧墽杈撳叆棰樻潗鈥?)

        st.markdown(
            f'<div class="script-canvas placeholder">{placeholder_text}</div>',
            unsafe_allow_html=True,
        )

    # 鐘舵€佹爮
    if st.session_state.script_generating:
        st.caption("鈴?娴佸紡鐢熸垚杩涜涓€?)

# ============================================================================
# 渚ц竟鏍忥細棰樻潗杈撳叆 & 宸ヤ綔娴佹帶鍒?# ============================================================================

with st.sidebar:
    st.markdown('<p class="sidebar-header">鈿欙笍 鍒涗綔鎺у埗鍙?/p>', unsafe_allow_html=True)

    # ----- 棰樻潗杈撳叆鍖?-----
    st.markdown("#### 馃摑 绗竴姝ワ細杈撳叆棰樻潗")
    st.session_state.topic = st.text_input(
        "璇疯緭鍏ョ煭鍓ч鏉愭垨涓€鍙ヨ瘽姊楁锛?,
        value=st.session_state.topic,
        placeholder="渚嬪锛氶噸鐢熶箣閮藉競绁炲尰銆佽豹闂ㄥ崈閲戦€嗚銆佺┛瓒婂彜浠ｅ仛棣栧瘜鈥?,
        key="sidebar_topic_input",
        disabled=st.session_state.topic_submitted and st.session_state.workflow_stage != "input",
    )

    col_a, col_b = st.columns([1, 1])
    with col_a:
        if st.button("馃殌 鎻愪氦棰樻潗", use_container_width=True, key="btn_submit_topic"):
            if st.session_state.topic.strip():
                st.session_state.topic_submitted = True
                st.session_state.workflow_stage = "planning"
                st.session_state.status_message = f"棰樻潗銆寋st.session_state.topic}銆嶅凡鎻愪氦锛孉gent 鐭╅樀姝ｅ湪鏋勬€濃€?
                st.rerun()
            else:
                st.warning("璇疯緭鍏ラ鏉愭垨姊楁銆?)
    with col_b:
        if st.button("馃攧 閲嶇疆", use_container_width=True, key="btn_reset"):
            reset_workflow()
            st.rerun()

    st.divider()

    # ----- 宸ヤ綔娴侀樁娈垫寚绀?-----
    st.markdown("#### 馃幆 褰撳墠闃舵")
    stage_labels = {
        "input": "鈴?绛夊緟杈撳叆棰樻潗",
        "planning": "鈴?Agent 鐭╅樀鏋勬€濅腑鈥?,
        "outline_review": "馃搵 鍗＄偣涓€锛氬ぇ绾插瀹?,
        "episode_review": "馃搼 鍗＄偣浜岋細鍒嗛泦瀹″畾",
        "generating": "鉁嶏笍 鍏ㄨ嚜鍔ㄧ敓鎴愬墽鏈?,
        "done": "鉁?鍓ф湰宸插畬鎴?,
    }
    st.info(stage_labels.get(st.session_state.workflow_stage, "鏈煡"))

    # ----- 蹇嵎璺宠浆锛堣皟璇曠敤锛?-----
    with st.expander("馃敡 璋冭瘯闈㈡澘"):
        new_stage = st.selectbox(
            "鎵嬪姩鍒囨崲闃舵锛?,
            options=["input", "planning", "outline_review", "episode_review", "generating", "done"],
            index=get_stage_index(st.session_state.workflow_stage),
            key="debug_stage_select",
        )
        if st.button("搴旂敤闃舵鍒囨崲", key="btn_debug_stage"):
            st.session_state.workflow_stage = new_stage
            st.rerun()

        st.caption("鎻愮ず锛氳皟璇曢潰鏉夸粎寮€鍙戦樁娈典娇鐢紝涓婄嚎鍚庣Щ闄ゃ€?)

    st.divider()

    # ----- 浣跨敤璇存槑 -----
    with st.expander("馃摉 浣跨敤璇存槑"):
        st.markdown("""
        1. **杈撳叆棰樻潗** 鈥?鍦ㄤ晶杈规爮杈撳叆鐭墽棰樻潗鎴栦竴鍙ヨ瘽姊楁銆?        2. **鎻愪氦棰樻潗** 鈥?鐐瑰嚮鎸夐挳锛孉gent 鐭╅樀寮€濮嬭嚜鍔ㄦ瀯鎬濄€?        3. **鍗＄偣涓€** 鈥?AI 鐢熸垚鐧鹃泦涓荤嚎澶х翰锛岀紪鍓у彲鐩存帴淇敼骞剁‘璁ゃ€?        4. **鍗＄偣浜?* 鈥?AI 鍒囧垎 100 闆嗗垎闆嗘寕閽╃偣娓呭崟锛岀紪鍓у鏍哥‘璁ゃ€?        5. **鐢熸垚鍓ф湰** 鈥?鐐瑰嚮纭鍚庯紝Agent 鐭╅樀鍏ㄨ嚜鍔ㄨ緭鍑哄鐧藉墽鏈€?        6. **涓嬭浇鍓ф湰** 鈥?鍓ф湰瀹屾垚鍚庯紝涓€閿笅杞戒负 TXT 鏂囦欢銆?        """)

# ============================================================================
# 搴曢儴鐘舵€佹爮
# ============================================================================

st.divider()
col_f1, col_f2, col_f3 = st.columns([2, 1, 1])
with col_f1:
    st.caption(f"褰撳墠闃舵锛歿st.session_state.workflow_stage} | 棰樻潗锛歿st.session_state.topic or '锛堟湭杈撳叆锛?}")
with col_f2:
    st.caption(f"澶х翰锛歿'鉁? if st.session_state.outline_confirmed else '鈼?}")
with col_f3:
    st.caption(f"鍒嗛泦锛歿'鉁? if st.session_state.episode_confirmed else '鈼?}")
