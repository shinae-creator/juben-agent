"""
鐭墽 Agent 鍒涗綔宸ヤ綔绔?v2 鈥?Streamlit 鍓嶇
===========================================
v2 澧炲己锛?  - 瀹炴椂杩涘害鏃ュ織闈㈡澘锛堝彸渚э級
  - Token 鐢ㄩ噺缁熻鏄剧ず
  - 鐢熸垚鍘嗗彶璁板綍锛堜晶杈规爮锛夛紝鏀寔涓€閿洖鐪?  - 鑷姩淇濆瓨鍓ф湰鍒?generations/ 鐩綍
"""

import streamlit as st
import time
from datetime import datetime
from typing import Optional

from agents import Orchestrator
from agents.orchestrator import ProgressEvent, TokenUsage
from history import save_generation, list_generations, get_generation_script

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
# 鑷畾涔?CSS
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
    "status_message": "",
    # v2 鏂板
    "generation_log": [],        # [(timestamp, icon, message), ...]
    "total_token_usage": {"input": 0, "output": 0},
    "gen_elapsed": 0.0,
    "gen_start_time": 0.0,
}

for key, default in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = default


# ============================================================================
# 杩涘害浜嬩欢鍥炶皟
# ============================================================================

def make_event_handler():
    """鍒涘缓涓€涓皢 ProgressEvent 鍐欏叆 session_state 鏃ュ織鐨勫洖璋?""
    def handler(event: ProgressEvent):
        icon = {"stage": "馃敼", "step": "  鈿欙笍", "token": "  馃搳", "done": "鉁?, "error": "鉂?}.get(event.type, "")
        st.session_state.generation_log.append((time.time(), icon, event.message))
    return handler


# ============================================================================
# Agent 鑷姩璋冨害閽╁瓙
# ============================================================================

# ---- planning 鈫?璋冪垎娆剧瓥鍒?Agent ----
if st.session_state.workflow_stage == "planning":
    st.session_state.generation_log = []
    st.session_state.gen_start_time = time.time()

    orch = Orchestrator(on_event=make_event_handler())
    try:
        result = orch.generate_outline(st.session_state.topic)
        st.session_state.outline = result.content
        st.session_state.total_token_usage["input"] += result.usage.input_tokens
        st.session_state.total_token_usage["output"] += result.usage.output_tokens
        st.session_state.gen_elapsed += result.elapsed_seconds
        st.session_state.workflow_stage = "outline_review"
        st.session_state.status_message = "澶х翰宸茬敓鎴愶紒璇峰湪宸︿晶瀹℃牳淇敼鍚庣‘璁ゃ€?
        st.rerun()
    except Exception as exc:
        st.session_state.status_message = f"鉂?Agent 璋冪敤澶辫触: {exc}"
        st.session_state.workflow_stage = "input"
        st.rerun()

# ---- episode_review 鈫?璋冨垎闆嗘灦鏋勫笀 Agent ----
if (
    st.session_state.workflow_stage == "episode_review"
    and not st.session_state.episode_list
):
    orch = Orchestrator(on_event=make_event_handler())
    try:
        result = orch.generate_episodes(st.session_state.outline)
        st.session_state.episode_list = result.content
        st.session_state.total_token_usage["input"] += result.usage.input_tokens
        st.session_state.total_token_usage["output"] += result.usage.output_tokens
        st.session_state.gen_elapsed += result.elapsed_seconds
        st.session_state.status_message = "鐧鹃泦鍗＄偣娓呭崟宸茬敓鎴愶紒璇峰湪宸︿晶瀹℃牳淇敼鍚庣‘璁ゃ€?
        st.rerun()
    except Exception as exc:
        st.session_state.status_message = f"鉂?鍒嗛泦鐢熸垚澶辫触: {exc}"
        st.session_state.workflow_stage = "outline_review"
        st.rerun()

# ---- generating 鈫?鍚姩娴佸紡鐢熸垚鏍囪 ----
if (
    st.session_state.workflow_stage == "generating"
    and not st.session_state.script_generating
):
    st.session_state.script_generating = True
    st.session_state.script_content = ""
    st.session_state.gen_start_time = time.time()
    st.rerun()


# ============================================================================
# 杈呭姪鍑芥暟
# ============================================================================

def reset_workflow():
    for key, default in DEFAULTS.items():
        st.session_state[key] = default

def get_stage_index(stage: str) -> int:
    order = ["input", "planning", "outline_review", "episode_review", "generating", "done"]
    return order.index(stage) if stage in order else 0


# ============================================================================
# 鏍囬 & 杩涘害鏉?# ============================================================================

st.markdown('<p class="main-title">馃幀 鐭墽 Agent 鍒涗綔宸ヤ綔绔?/p>', unsafe_allow_html=True)
st.markdown(
    f'<p class="sub-title">Agent 鐭╅樀鍏ㄨ嚜鍔ㄦ瀯鎬?路 缂栧墽缃戦〉鎺у満 路 涓€閿嚭鏈?'
    f'| {datetime.now().strftime("%Y-%m-%d %H:%M")}</p>',
    unsafe_allow_html=True,
)

STEPS = [
    ("input", "馃摑", "杈撳叆棰樻潗"),
    ("planning", "馃", "AI 鏋勬€?),
    ("outline_review", "馃搵", "澶х翰瀹″畾"),
    ("episode_review", "馃搼", "鍒嗛泦瀹″畾"),
    ("generating", "鉁嶏笍", "鐢熸垚鍓ф湰"),
    ("done", "鉁?, "瀹屾垚"),
]
current_idx = get_stage_index(st.session_state.workflow_stage)

stepper_html = '<div class="stepper-container">'
for i, (stage, icon, label) in enumerate(STEPS):
    if i > 0:
        stepper_html += f'<div class="step-connector{" done" if i <= current_idx else ""}"></div>'
    if i < current_idx:
        cls, lbl_cls, cont = "done", "done", "鉁?
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
# 宸︽爮锛氬崱鐐瑰崱鐗?# ============================================================================

left_col, right_col = st.columns([2, 3], gap="medium")

with left_col:
    if st.session_state.status_message:
        st.info(st.session_state.status_message)

    # 鈹€鈹€ Token 鐢ㄩ噺闈㈡澘锛圕laude Code 椋庢牸鍔ㄦ€佺疮鍔狅級 鈹€鈹€
    tu = st.session_state.total_token_usage
    if tu["input"] > 0 or tu["output"] > 0:
        total_t = tu["input"] + tu["output"]
        elapsed = st.session_state.gen_elapsed or (time.time() - st.session_state.gen_start_time if st.session_state.gen_start_time else 0)
        st.markdown(
            f"""<div style="background:#f0f4ff;border:1px solid #c8d6ff;border-radius:8px;padding:0.6rem 1rem;margin-bottom:0.8rem;font-family:Consolas,monospace;font-size:0.82rem;">
            馃摜 杈撳叆 <b>{tu['input']:,}</b> &nbsp;|&nbsp;
            馃摛 杈撳嚭 <b>{tu['output']:,}</b> &nbsp;|&nbsp;
            馃敟 鍚堣 <b style="color:#667eea;">{total_t:,}</b> tokens &nbsp;|&nbsp;
            鈴?<b>{elapsed:.0f}s</b>
            </div>""",
            unsafe_allow_html=True,
        )

    # ============================
    # 鍗＄偣涓€锛氬ぇ绾?    # ============================
    outline_locked = get_stage_index(st.session_state.workflow_stage) < get_stage_index("outline_review")
    outline_active = st.session_state.workflow_stage == "outline_review"
    outline_done = get_stage_index(st.session_state.workflow_stage) > get_stage_index("outline_review")

    card_cls = "checkpoint-card"
    if outline_locked: card_cls += " locked"
    elif outline_active: card_cls += " active"

    st.markdown(f'<div class="{card_cls}">', unsafe_allow_html=True)
    c1, c2 = st.columns([3, 1])
    with c1: st.markdown("### 馃搵 鍗＄偣涓€ 路 鐧鹃泦涓荤嚎澶х翰")
    with c2:
        if outline_done: st.markdown('<span class="card-badge badge-done">鉁?宸茬‘璁?/span>', unsafe_allow_html=True)
        elif outline_active: st.markdown('<span class="card-badge badge-checkpoint">鈴?寰呭瀹?/span>', unsafe_allow_html=True)
        else: st.markdown('<span class="card-badge badge-pending">馃敀 绛夊緟涓?/span>', unsafe_allow_html=True)

    if outline_done:
        st.text_area("澶х翰锛堝凡纭锛?, value=st.session_state.outline, height=220, disabled=True, key="outline_done")
    elif not outline_locked:
        st.session_state.outline = st.text_area(
            "AI 鐢熸垚鐨勫ぇ绾诧紝鍙洿鎺ョ紪杈戯細", value=st.session_state.outline, height=220,
            placeholder="Agent 鐭╅樀姝ｅ湪鏋勬€濃€?, key="outline_editor",
        )
        b1, b2 = st.columns(2)
        with b1:
            if st.button("鉁?纭澶х翰", use_container_width=True, key="btn_confirm_outline"):
                if st.session_state.outline.strip():
                    st.session_state.outline_confirmed = True
                    st.session_state.workflow_stage = "episode_review"
                    st.session_state.status_message = "澶х翰宸茬‘璁わ紒姝ｅ湪鐢熸垚鍒嗛泦娓呭崟鈥?
                    st.rerun()
                else: st.warning("澶х翰涓嶈兘涓虹┖")
        with b2:
            if st.button("馃攧 AI 閲嶆瀯鎬?, use_container_width=True, key="btn_regenerate_outline"):
                st.session_state.workflow_stage = "planning"
                st.session_state.status_message = "Agent 鐭╅樀閲嶆柊鏋勬€濅腑鈥?
                st.rerun()
    else:
        st.text_area("澶х翰", value="锛堣鍏堟彁浜ら鏉愶級", height=220, disabled=True, key="outline_placeholder")
    st.markdown('</div>', unsafe_allow_html=True)

    # ============================
    # 鍗＄偣浜岋細鍒嗛泦
    # ============================
    episode_locked = get_stage_index(st.session_state.workflow_stage) < get_stage_index("episode_review")
    episode_active = st.session_state.workflow_stage == "episode_review"
    episode_done = get_stage_index(st.session_state.workflow_stage) > get_stage_index("episode_review")

    card_cls2 = "checkpoint-card"
    if episode_locked: card_cls2 += " locked"
    elif episode_active: card_cls2 += " active"

    st.markdown(f'<div class="{card_cls2}">', unsafe_allow_html=True)
    c3, c4 = st.columns([3, 1])
    with c3: st.markdown("### 馃搼 鍗＄偣浜?路 鍒嗛泦鎸傞挬鐐规竻鍗?)
    with c4:
        if episode_done: st.markdown('<span class="card-badge badge-done">鉁?宸茬‘璁?/span>', unsafe_allow_html=True)
        elif episode_active: st.markdown('<span class="card-badge badge-checkpoint">鈴?寰呭瀹?/span>', unsafe_allow_html=True)
        else: st.markdown('<span class="card-badge badge-pending">馃敀 绛夊緟涓?/span>', unsafe_allow_html=True)

    if episode_done:
        st.text_area("鍒嗛泦娓呭崟锛堝凡纭锛?, value=st.session_state.episode_list, height=280, disabled=True, key="ep_done")
    elif not episode_locked:
        st.session_state.episode_list = st.text_area(
            "100闆嗗垎闆嗗崱鐐癸紝鍙洿鎺ョ紪杈戯細", value=st.session_state.episode_list, height=280,
            placeholder="澶х翰纭鍚庤嚜鍔ㄧ敓鎴愨€?, key="episode_editor",
        )
        b3, b4, b5 = st.columns([1, 1, 1])
        with b3:
            if st.button("鉁?纭骞跺嚭鏈?, use_container_width=True, key="btn_confirm_ep"):
                if st.session_state.episode_list.strip():
                    st.session_state.episode_confirmed = True
                    st.session_state.workflow_stage = "generating"
                    st.session_state.status_message = "鍒嗛泦宸茬‘璁わ紒姝ｅ湪鐢熸垚鍓ф湰鈥?
                    st.rerun()
                else: st.warning("鍒嗛泦娓呭崟涓嶈兘涓虹┖")
        with b4:
            if st.button("馃攧 閲嶆柊鍒囧垎", use_container_width=True, key="btn_regen_ep"):
                st.session_state.episode_list = ""
                st.session_state.status_message = "鍒嗛泦鏋舵瀯甯堥噸鏂板垏鍒嗕腑鈥?
                st.rerun()
        with b5:
            if st.button("鈫?杩斿洖鏀瑰ぇ绾?, use_container_width=True, key="btn_back_ol"):
                st.session_state.workflow_stage = "outline_review"
                st.session_state.episode_confirmed = False
                st.rerun()
    else:
        st.text_area("鍒嗛泦娓呭崟", value="锛堣鍏堢‘璁ゅぇ绾诧級", height=280, disabled=True, key="ep_placeholder")
    st.markdown('</div>', unsafe_allow_html=True)

    # 鈹€鈹€ 涓嬭浇鎸夐挳 鈹€鈹€
    if st.session_state.workflow_stage == "done" and st.session_state.script_content:
        st.download_button(
            label="猬囷笍 涓嬭浇鍓ф湰 TXT",
            data=st.session_state.script_content,
            file_name=f"鐭墽_{st.session_state.topic[:20]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            mime="text/plain",
            use_container_width=True,
        )


# ============================================================================
# 鍙虫爮锛氬墽鏈敾甯?+ 杩涘害鏃ュ織
# ============================================================================

with right_col:
    # 鈹€鈹€ 杩涘害鏃ュ織 鈹€鈹€
    with st.expander("馃摗 Agent 杩愯鏃ュ織", expanded=bool(st.session_state.generation_log)):
        if st.session_state.generation_log:
            # 鍘婚噸锛氱浉鍚屾秷鎭彧淇濈暀鏈€鏂版椂闂存埑
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
            st.caption("鏆傛棤鏃ュ織锛屾彁浜ら鏉愬悗鑷姩鏄剧ず銆?)

    # 鈹€鈹€ 鍓ф湰鐢诲竷 鈹€鈹€
    st.markdown("### 馃幁 鍓ф湰瀹炴椂棰勮")

    if st.session_state.script_content:
        st.markdown(
            f'<div class="script-canvas">{st.session_state.script_content}</div>',
            unsafe_allow_html=True,
        )
    elif st.session_state.workflow_stage == "generating" and st.session_state.script_generating:
        # ---- 娴佸紡鐢熸垚锛堥€?token 鎵撳瓧鏈猴級 ----
        orch = Orchestrator(on_event=make_event_handler())
        script_placeholder = st.empty()
        token_placeholder = st.empty()
        accumulated = ""

        try:
            stream = orch.generate_script_stream(
                topic=st.session_state.topic,
                episode_list=st.session_state.episode_list,
            )
            for chunk, batch_usage in stream:
                accumulated += chunk
                if batch_usage:
                    st.session_state.total_token_usage["input"] += batch_usage.input_tokens
                    st.session_state.total_token_usage["output"] += batch_usage.output_tokens

                # 瀹炴椂 Token 鍔ㄦ€佺疮鍔犳樉绀猴紙绫?Claude Code 鏁堟灉锛?                elapsed = time.time() - st.session_state.gen_start_time
                tu = st.session_state.total_token_usage
                token_placeholder.caption(
                    f"鈴?{elapsed:.0f}s | "
                    f"馃摜 杈撳叆 {tu['input']:,} | 馃摛 杈撳嚭 {tu['output']:,} | "
                    f"馃敟 鍚堣 {tu['input'] + tu['output']:,} tokens"
                )
                # 鎵撳瓧鏈虹敾甯?                script_placeholder.markdown(
                    f'<div class="script-canvas">{accumulated}</div>',
                    unsafe_allow_html=True,
                )

            st.session_state.script_content = accumulated
            st.session_state.script_generating = False
            st.session_state.gen_elapsed = time.time() - st.session_state.gen_start_time
            st.session_state.workflow_stage = "done"
            st.session_state.status_message = "鉁?鍓ф湰鐢熸垚瀹屾瘯锛佸彲涓嬭浇鎴栧洖鐪嬨€?

            # ---- 鑷姩淇濆瓨 ----
            try:
                from config import LLM_MODEL
                save_generation(
                    topic=st.session_state.topic,
                    outline=st.session_state.outline,
                    episode_list=st.session_state.episode_list,
                    script_content=accumulated,
                    total_input_tokens=st.session_state.total_token_usage["input"],
                    total_output_tokens=st.session_state.total_token_usage["output"],
                    total_elapsed=st.session_state.gen_elapsed,
                    model=LLM_MODEL,
                )
                st.session_state.status_message += " 馃搧 宸茶嚜鍔ㄤ繚瀛樸€?
            except Exception as save_err:
                st.session_state.status_message += f" 鈿狅笍 淇濆瓨澶辫触: {save_err}"

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
            "planning": "馃 Agent 鐭╅樀姝ｅ湪鏋勬€濅腑锛岃绋嶅€欌€?,
            "outline_review": "馃搵 璇峰湪宸︿晶瀹℃牳骞剁‘璁ゅぇ绾层€?,
            "episode_review": "馃搼 璇峰湪宸︿晶瀹℃牳鍒嗛泦娓呭崟锛岀‘璁ゅ悗寮€濮嬬敓鎴愬墽鏈€?,
            "done": "鉁?鍓ф湰宸茬敓鎴愬畬姣曪紝鐐瑰嚮宸︿晶涓嬭浇銆?,
        }.get(st.session_state.workflow_stage, "绛夊緟缂栧墽杈撳叆棰樻潗鈥?)
        st.markdown(f'<div class="script-canvas placeholder">{placeholder_text}</div>', unsafe_allow_html=True)

    # 鈹€鈹€ 娴佸紡杩涘害 鈹€鈹€
    if st.session_state.script_generating:
        st.caption("鈴?娴佸紡鐢熸垚杩涜涓€?)


# ============================================================================
# 渚ц竟鏍?# ============================================================================

with st.sidebar:
    st.markdown("## 鈿欙笍 鍒涗綔鎺у埗鍙?)

    # 鈹€鈹€ 棰樻潗杈撳叆 鈹€鈹€
    st.markdown("#### 馃摑 杈撳叆棰樻潗")
    st.session_state.topic = st.text_input(
        "鐭墽棰樻潗鎴栦竴鍙ヨ瘽姊楁锛?,
        value=st.session_state.topic,
        placeholder="閲嶇敓涔嬮兘甯傜鍖汇€佽豹闂ㄥ崈閲戦€嗚鈥?,
        key="sidebar_topic",
        disabled=st.session_state.topic_submitted and st.session_state.workflow_stage != "input",
    )
    ca, cb = st.columns(2)
    with ca:
        if st.button("馃殌 鎻愪氦棰樻潗", use_container_width=True, key="btn_submit"):
            if st.session_state.topic.strip():
                st.session_state.topic_submitted = True
                st.session_state.workflow_stage = "planning"
                st.session_state.status_message = f"銆寋st.session_state.topic}銆嶅凡鎻愪氦锛孉gent 鐭╅樀鏋勬€濅腑鈥?
                st.rerun()
            else: st.warning("璇疯緭鍏ラ鏉?)
    with cb:
        if st.button("馃攧 閲嶇疆", use_container_width=True, key="btn_reset"):
            reset_workflow()
            st.rerun()

    st.divider()

    # 鈹€鈹€ 蹇€熷鍏?鈹€鈹€
    with st.expander("馃摜 蹇€熷鍏ワ紙璺宠繃 AI锛?, expanded=False):
        imported_ol = st.text_area("绮樿创澶х翰锛?, height=120, placeholder="宸叉湁澶х翰鈥?, key="imp_ol")
        if st.button("馃搵 瀵煎叆澶х翰", use_container_width=True, key="btn_imp_ol"):
            if imported_ol.strip():
                st.session_state.topic = "锛堝鍏ュぇ绾诧級"
                st.session_state.topic_submitted = True
                st.session_state.outline = imported_ol.strip()
                st.session_state.episode_list = ""
                st.session_state.workflow_stage = "outline_review"
                st.session_state.status_message = "澶х翰宸插鍏ワ紝璇峰鏍稿悗纭銆?
                st.rerun()
            else: st.warning("璇风矘璐村ぇ绾?)

        imported_ep = st.text_area("绮樿创鍒嗛泦娓呭崟锛?, height=120, placeholder="宸叉湁鍒嗛泦娓呭崟鈥?, key="imp_ep")
        ci1, ci2 = st.columns(2)
        with ci1:
            if st.button("馃搼 瀵煎叆鍒嗛泦", use_container_width=True, key="btn_imp_ep"):
                if imported_ep.strip():
                    st.session_state.episode_list = imported_ep.strip()
                    st.session_state.workflow_stage = "episode_review"
                    st.session_state.status_message = "鍒嗛泦宸插鍏ワ紝璇峰鏍稿悗纭銆?
                    st.rerun()
                else: st.warning("璇风矘璐村垎闆嗘竻鍗?)
        with ci2:
            if st.button("馃殌 鐩撮€氬嚭鏈?, use_container_width=True, key="btn_imp_all"):
                if imported_ol.strip() and imported_ep.strip():
                    st.session_state.topic = "锛堝鍏ワ級"
                    st.session_state.topic_submitted = True
                    st.session_state.outline = imported_ol.strip()
                    st.session_state.outline_confirmed = True
                    st.session_state.episode_list = imported_ep.strip()
                    st.session_state.episode_confirmed = True
                    st.session_state.workflow_stage = "generating"
                    st.rerun()
                else: st.warning("璇峰悓鏃剁矘璐村ぇ绾插拰鍒嗛泦娓呭崟")

    st.divider()

    # 鈹€鈹€ 褰撳墠闃舵 鈹€鈹€
    st.caption(f"褰撳墠闃舵锛歿st.session_state.workflow_stage}")

    # 鈹€鈹€ 鍘嗗彶璁板綍 鈹€鈹€
    st.divider()
    st.markdown("#### 馃摎 鐢熸垚鍘嗗彶")
    records = list_generations(limit=10)
    if records:
        for rec in records:
            preview = rec.topic[:18] if rec.topic else "鏃犳爣棰?
            label = f"{rec.id} 鈥?{preview}"
            if st.button(label, key=f"hist_{rec.id}", use_container_width=True):
                script = get_generation_script(rec.id)
                if script:
                    st.session_state.script_content = script
                    st.session_state.workflow_stage = "done"
                    st.session_state.status_message = f"宸插姞杞藉巻鍙茶褰曪細{rec.id}"
                    st.rerun()
    else:
        st.caption("鏆傛棤鐢熸垚璁板綍銆?)
    st.caption(f"馃捑 鑷姩淇濆瓨璺緞锛歚generations/`")

    st.divider()

    with st.expander("馃摉 浣跨敤璇存槑"):
        st.markdown("""
        1. 杈撳叆棰樻潗 鈫?鎻愪氦
        2. 瀹℃牳 AI 鐢熸垚鐨勫ぇ绾?鈫?纭
        3. 瀹℃牳鐧鹃泦鍒嗛泦娓呭崟 鈫?纭
        4. 绛夊緟娴佸紡鍓ф湰鐢熸垚 鈫?涓嬭浇
        5. 涔熷彲鐢ㄣ€屽揩閫熷鍏ャ€嶈烦杩?AI 鏋勬€?        """)

    with st.expander("馃敡 璋冭瘯"):
        new_stage = st.selectbox("鍒囨崲闃舵", options=["input","planning","outline_review","episode_review","generating","done"], index=get_stage_index(st.session_state.workflow_stage))
        if st.button("搴旂敤", key="debug_apply"):
            st.session_state.workflow_stage = new_stage
            st.rerun()
