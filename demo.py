"""
streamlit_app.py — Giao diện Demo Lab 3: Chatbot vs ReAct Agent (Vinmec)

Nguyên tắc:
  - CHỈ import hàm từ src/app.py, KHÔNG sửa bất kỳ file gốc nào.
  - Mọi logic xử lý vẫn nằm hoàn toàn trong src/.

Chạy: streamlit run streamlit_app.py
"""

import json
import sys
from io import StringIO
from pathlib import Path

import streamlit as st

# ── sys.path ──────────────────────────────────────────────────────────────────
SRC_DIR = Path(__file__).parent / "src"
sys.path.insert(0, str(SRC_DIR))

# ── Import HÀM từ app.py (không đụng __main__) ────────────────────────────────
from app import load_test_cases, run_react_agent, save_waterfall_trace  # noqa: E402
from mcp_server import MCPVinmecServer                                    # noqa: E402
from prompts import CHATBOT_BASELINE_PROMPT                               # noqa: E402
from providers import get_llm_provider                                    # noqa: E402
from tools import DOCTOR_DATABASE, PATIENT_DATABASE, TOOLS_SCHEMA         # noqa: E402

# ══════════════════════════════════════════════════════════════════════════════
# PAGE CONFIG
# ══════════════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="Vinmec ReAct Agent · Lab 3",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ══════════════════════════════════════════════════════════════════════════════
# CSS
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
/* ── Google Font ── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

/* ── Ẩn watermark Streamlit ── */
#MainMenu, footer, header { visibility: hidden; }

/* ── Màu hệ thống ── */
:root {
    --green-700 : #005c3b;
    --green-600 : #007a50;
    --green-500 : #009966;
    --green-100 : #e6f5f0;
    --green-50  : #f0faf6;
    --blue-600  : #1558d6;
    --blue-100  : #dce8fd;
    --red-600   : #c5221f;
    --red-100   : #fce8e6;
    --orange-600: #b06000;
    --orange-100: #fef3cd;
    --gray-800  : #1a1a2e;
    --gray-600  : #5f6368;
    --gray-200  : #e8eaed;
    --gray-100  : #f8f9fa;
    --white     : #ffffff;
    --shadow-sm : 0 1px 3px rgba(0,0,0,.10), 0 1px 2px rgba(0,0,0,.06);
    --shadow-md : 0 4px 6px rgba(0,0,0,.07), 0 2px 4px rgba(0,0,0,.06);
    --radius-lg : 16px;
    --radius-md : 10px;
    --radius-sm : 6px;
}

/* ── Sidebar ── */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, var(--green-700) 0%, var(--green-600) 100%);
}
section[data-testid="stSidebar"] * { color: #fff !important; }
section[data-testid="stSidebar"] .stRadio label { color: #e0f5ee !important; }
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { color: #c8f0e2 !important; }
section[data-testid="stSidebar"] hr { border-color: rgba(255,255,255,.2) !important; }
section[data-testid="stSidebar"] .stButton button {
    background: rgba(255,255,255,.12) !important;
    border: 1px solid rgba(255,255,255,.25) !important;
    color: white !important;
    border-radius: var(--radius-sm) !important;
}
section[data-testid="stSidebar"] .stButton button:hover {
    background: rgba(255,255,255,.22) !important;
}

/* ── Header banner ── */
.app-header {
    background: linear-gradient(135deg, var(--green-700) 0%, var(--green-500) 100%);
    padding: 1.75rem 2rem 1.5rem;
    border-radius: var(--radius-lg);
    margin-bottom: 1.5rem;
    color: white;
    box-shadow: var(--shadow-md);
    display: flex;
    align-items: center;
    gap: 1.25rem;
}
.app-header .icon { font-size: 2.8rem; line-height: 1; }
.app-header h1   { margin: 0; font-size: 1.65rem; font-weight: 700; letter-spacing: -.02em; }
.app-header p    { margin: .3rem 0 0; opacity: .82; font-size: .9rem; }

/* ── Chip / suggestion button ── */
.chip-row { display: flex; flex-wrap: wrap; gap: .5rem; margin: .75rem 0 1rem; }
.chip {
    display: inline-flex;
    align-items: center;
    gap: .35rem;
    padding: .45rem 1rem;
    border-radius: 9999px;
    border: 1.5px solid var(--green-500);
    background: var(--green-50);
    color: var(--green-700);
    font-size: .82rem;
    font-weight: 500;
    cursor: pointer;
    transition: all .15s ease;
    white-space: nowrap;
}
.chip:hover { background: var(--green-500); color: white; box-shadow: var(--shadow-sm); }

/* ── Chat bubbles ── */
.chat-row         { display: flex; align-items: flex-end; gap: .6rem; margin: .7rem 0; }
.chat-row.user    { flex-direction: row-reverse; }
.avatar {
    width: 36px; height: 36px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 1.1rem; flex-shrink: 0;
    box-shadow: var(--shadow-sm);
}
.avatar-user  { background: var(--blue-600); }
.avatar-agent { background: var(--green-600); }
.avatar-bot   { background: var(--red-600); }
.bubble {
    max-width: 78%;
    padding: .75rem 1.1rem;
    border-radius: var(--radius-md);
    font-size: .92rem;
    line-height: 1.55;
    box-shadow: var(--shadow-sm);
}
.bubble-user  { background: var(--blue-100); color: #0d2361; border-radius: var(--radius-md) var(--radius-md) var(--radius-sm) var(--radius-md); }
.bubble-agent { background: var(--green-100); color: #014532; border-radius: var(--radius-md) var(--radius-md) var(--radius-md) var(--radius-sm); }
.bubble-bot   { background: var(--red-100);   color: #4a0e0c; border-radius: var(--radius-md) var(--radius-md) var(--radius-md) var(--radius-sm); }
.bubble-name  { font-size: .72rem; font-weight: 600; margin-bottom: .3rem; opacity: .65; text-transform: uppercase; letter-spacing: .04em; }

/* ── Trace timeline ── */
.timeline { position: relative; padding-left: 1.8rem; }
.timeline::before {
    content: '';
    position: absolute; left: .55rem; top: .5rem; bottom: .5rem;
    width: 2px; background: var(--gray-200); border-radius: 1px;
}
.tl-item { position: relative; margin-bottom: 1rem; }
.tl-dot {
    position: absolute; left: -1.4rem; top: .4rem;
    width: 12px; height: 12px; border-radius: 50%;
    border: 2px solid white; box-shadow: var(--shadow-sm);
}
.tl-dot-tool  { background: var(--blue-600); }
.tl-dot-final { background: var(--green-500); }
.tl-card {
    border-radius: var(--radius-md);
    padding: .85rem 1.1rem;
    box-shadow: var(--shadow-sm);
    border-left: 3.5px solid transparent;
}
.tl-card-tool  { background: var(--blue-100);  border-left-color: var(--blue-600); }
.tl-card-final { background: var(--green-100); border-left-color: var(--green-500); }
.tl-tag {
    display: inline-block;
    font-size: .68rem; font-weight: 700; letter-spacing: .07em;
    text-transform: uppercase; padding: .15rem .55rem; border-radius: 9999px;
    margin-bottom: .45rem;
}
.tl-tag-tool  { background: var(--blue-600);  color: white; }
.tl-tag-final { background: var(--green-500); color: white; }
.tl-title { font-weight: 600; font-size: .9rem; margin-bottom: .3rem; color: var(--gray-800); }
.tl-body  { font-size: .87rem; color: #3c4043; line-height: 1.5; }
.tl-meta  { font-size: .75rem; color: var(--gray-600); margin-top: .4rem; }

/* ── Badge ── */
.badge {
    display: inline-block; padding: .2rem .65rem; border-radius: 9999px;
    font-size: .73rem; font-weight: 700;
}
.badge-green  { background: #c6efce; color: #276221; }
.badge-blue   { background: var(--blue-100); color: #1a237e; }
.badge-orange { background: var(--orange-100); color: var(--orange-600); }
.badge-red    { background: var(--red-100); color: var(--red-600); }

/* ── Stat card ── */
.stat-card {
    background: rgba(255,255,255,.12);
    border: 1px solid rgba(255,255,255,.2);
    border-radius: var(--radius-sm);
    padding: .6rem .9rem;
    text-align: center;
    margin-bottom: .5rem;
}
.stat-card .num  { font-size: 1.6rem; font-weight: 700; color: white !important; }
.stat-card .lbl  { font-size: .72rem; opacity: .75; color: #c8f0e2 !important; }

/* ── Misc ── */
.section-title {
    font-size: 1rem; font-weight: 600; color: var(--gray-800);
    margin: 1.2rem 0 .6rem; padding-bottom: .4rem;
    border-bottom: 2px solid var(--green-100);
}
.empty-hint {
    text-align: center; color: var(--gray-600);
    padding: 2.5rem 1rem; font-size: .9rem;
}
.info-box {
    background: var(--green-50); border: 1px solid var(--green-100);
    border-radius: var(--radius-md); padding: .8rem 1.1rem;
    font-size: .87rem; color: var(--green-700); margin-bottom: 1rem;
}
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# SESSION STATE
# ══════════════════════════════════════════════════════════════════════════════
defaults = {
    "chat_history"  : [],   # [{role, content, traces}]
    "all_traces"    : [],   # tất cả trace events từ đầu session
    "test_results"  : [],   # kết quả Test Suite
    "preset_query"  : "",   # suggestion được click → điền vào text_input
    "compare_result": None, # kết quả so sánh chatbot vs agent
}
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val

# ══════════════════════════════════════════════════════════════════════════════
# CACHED RESOURCES
# ══════════════════════════════════════════════════════════════════════════════
@st.cache_resource
def _get_provider():
    return get_llm_provider()

@st.cache_resource
def _get_mcp():
    return MCPVinmecServer()

@st.cache_data
def _get_tests():
    return load_test_cases()

provider   = _get_provider()
mcp_server = _get_mcp()
test_cases = _get_tests()

# ══════════════════════════════════════════════════════════════════════════════
# HELPER: gọi hàm từ app.py, capture stdout
# ══════════════════════════════════════════════════════════════════════════════

def call_react_agent(query: str) -> tuple[str, list[dict]]:
    """Gọi run_react_agent() từ app.py, trả về (final_answer, traces)."""
    old, sys.stdout = sys.stdout, StringIO()
    try:
        traces = run_react_agent(query, provider, mcp_server)
    finally:
        sys.stdout = old
    final = next(
        (e["output"] for e in reversed(traces) if e.get("action_type") == "FINAL_ANSWER"),
        "(Không có kết quả)"
    )
    return final, traces


def call_chatbot(query: str) -> str:
    """Gọi provider.generate() với CHATBOT_BASELINE_PROMPT (giống run_baseline_chatbot)."""
    return provider.generate(query, system_prompt=CHATBOT_BASELINE_PROMPT)


# ══════════════════════════════════════════════════════════════════════════════
# HELPER: render components
# ══════════════════════════════════════════════════════════════════════════════

def render_trace(traces: list[dict]) -> None:
    """Hiển thị Waterfall Trace dạng timeline dọc đẹp."""
    if not traces:
        st.markdown('<p class="empty-hint">Chưa có trace.</p>', unsafe_allow_html=True)
        return

    st.markdown('<div class="timeline">', unsafe_allow_html=True)
    for ev in traces:
        action = ev.get("action_type", "")
        step   = ev.get("step", "?")
        lat    = ev.get("latency_ms", 0)

        if action == "TOOL_EXECUTION":
            tool = ev.get("tool_name", "")
            args = ev.get("arguments", {})
            obs  = ev.get("observation", {})
            status = obs.get("status", "")
            args_str = ", ".join(f"<code>{k}=<b>{v}</b></code>" for k, v in args.items())
            badge_cls = "badge-green" if status == "SUCCESS" else "badge-red"

            st.markdown(f"""
<div class="tl-item">
  <div class="tl-dot tl-dot-tool"></div>
  <div class="tl-card tl-card-tool">
    <span class="tl-tag tl-tag-tool">🛠 Bước {step} · Tool Call</span>
    <div class="tl-title">{tool}({args_str})</div>
    <div class="tl-body">
      Kết quả: <span class="badge {badge_cls}">{status}</span>
      {' · ' + obs.get('message','')[:120] if status != 'SUCCESS' else ''}
    </div>
    <div class="tl-meta">⏱ {lat} ms</div>
  </div>
</div>""", unsafe_allow_html=True)

            if status == "SUCCESS":
                with st.expander(f"📦 Xem Observation JSON — Bước {step}", expanded=False):
                    st.json(obs)

        elif action == "FINAL_ANSWER":
            thought = ev.get("thought", "")
            output  = ev.get("output", "")
            st.markdown(f"""
<div class="tl-item">
  <div class="tl-dot tl-dot-final"></div>
  <div class="tl-card tl-card-final">
    <span class="tl-tag tl-tag-final">🏁 Bước {step} · Final Answer</span>
    <div class="tl-body" style="font-style:italic;color:#555;font-size:.82rem;margin-bottom:.4rem">{thought}</div>
    <div class="tl-body">{output}</div>
    <div class="tl-meta">⏱ {lat} ms</div>
  </div>
</div>""", unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)


def badge_html(text: str, color: str = "green") -> str:
    return f'<span class="badge badge-{color}">{text}</span>'


# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("""
<div style="padding:.5rem 0 1rem">
  <div style="font-size:2rem;text-align:center">🏥</div>
  <div style="text-align:center;font-size:1.1rem;font-weight:700;margin-top:.3rem">Vinmec Agent</div>
  <div style="text-align:center;font-size:.78rem;opacity:.7;margin-top:.2rem">Lab 3 · Day 03 Demo</div>
</div>
""", unsafe_allow_html=True)

    st.divider()

    page = st.radio(
        "Điều hướng",
        options=[
            "💬 Chat với ReAct Agent",
            "🔄 So sánh Chatbot vs Agent",
            "🧪 Test Suite",
            "📊 Waterfall Trace Log",
            "🗄️ Xem Database & Schema",
        ],
        label_visibility="collapsed",
    )

    st.divider()

    # System info
    st.markdown('<p style="font-size:.75rem;font-weight:700;opacity:.6;letter-spacing:.06em">HỆ THỐNG</p>',
                unsafe_allow_html=True)
    provider_name = provider.__class__.__name__
    model_name    = getattr(provider, "model_name", "—")
    st.markdown(f"""
<div style="font-size:.82rem;line-height:2">
  🔌 <b>Provider</b>: {provider_name}<br>
  🤖 <b>Model</b>: {model_name}<br>
  🌐 <b>MCP</b>: {mcp_server.server_name}<br>
  🛠 <b>Tools</b>: {len(mcp_server.list_tools())} công cụ
</div>
""", unsafe_allow_html=True)

    # Session stats
    if st.session_state.all_traces:
        st.divider()
        st.markdown('<p style="font-size:.75rem;font-weight:700;opacity:.6;letter-spacing:.06em">SESSION</p>',
                    unsafe_allow_html=True)
        tool_calls = sum(1 for e in st.session_state.all_traces if e.get("action_type") == "TOOL_EXECUTION")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f'<div class="stat-card"><div class="num">{len(st.session_state.all_traces)}</div><div class="lbl">Events</div></div>',
                        unsafe_allow_html=True)
        with c2:
            st.markdown(f'<div class="stat-card"><div class="num">{tool_calls}</div><div class="lbl">Tool calls</div></div>',
                        unsafe_allow_html=True)

    st.divider()
    if st.button("🗑 Xoá session", use_container_width=True):
        for key in defaults:
            st.session_state[key] = defaults[key]
        st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# HEADER BANNER
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<div class="app-header">
  <div class="icon">🏥</div>
  <div>
    <h1>Vinmec Healthcare — ReAct Agent Demo</h1>
    <p>Lab 3: Chatbot vs ReAct Agent · MCP Enhanced · Trần Ngọc Khuyên – 2A202602682</p>
  </div>
</div>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 1 — CHAT
# ══════════════════════════════════════════════════════════════════════════════
SUGGESTIONS = [
    ("💬", "Vinmec có những chuyên khoa nào?"),
    ("🔍", "Tra cứu bác sĩ Tim mạch ngày 2026-09-20"),
    ("🔍", "Tra cứu bác sĩ Da liễu"),
    ("📅", "Đặt lịch với BS. Nguyễn Thị Lan, Nhi, lúc 2026-09-20 09:00, mã BN2026042"),
    ("📅", "Đặt lịch cho BN2026099 với PGS.TS. Trần Minh Khoa, Tim mạch, 2026-09-20 08:00"),
    ("⚠️", "Tra cứu bệnh nhân mã BN9999999"),
]

if page == "💬 Chat với ReAct Agent":

    # ── Gợi ý câu hỏi (nằm NGOÀI form → chỉ điền input, không submit) ──────
    st.markdown('<div class="section-title">💡 Gợi ý câu hỏi nhanh</div>', unsafe_allow_html=True)
    st.caption("Click vào gợi ý để điền vào ô nhập bên dưới, sau đó nhấn **Gửi** để thực hiện.")

    cols = st.columns(3)
    for idx, (icon, text) in enumerate(SUGGESTIONS):
        with cols[idx % 3]:
            # Key riêng biệt cho mỗi button; click chỉ set session_state
            if st.button(f"{icon} {text}", key=f"chip_{idx}", use_container_width=True):
                st.session_state.preset_query = text
                st.rerun()   # rerun để text_input cập nhật giá trị mới

    st.divider()

    # ── Lịch sử chat ─────────────────────────────────────────────────────────
    chat_box = st.container(height=400)
    with chat_box:
        if not st.session_state.chat_history:
            st.markdown(
                '<div class="empty-hint">🤖 Gõ câu hỏi hoặc click gợi ý bên trên để bắt đầu trò chuyện.</div>',
                unsafe_allow_html=True,
            )
        for msg in st.session_state.chat_history:
            if msg["role"] == "user":
                st.markdown(f"""
<div class="chat-row user">
  <div class="avatar avatar-user">👤</div>
  <div class="bubble bubble-user">
    <div class="bubble-name">Bệnh nhân</div>
    {msg["content"]}
  </div>
</div>""", unsafe_allow_html=True)
            else:
                st.markdown(f"""
<div class="chat-row">
  <div class="avatar avatar-agent">🤖</div>
  <div class="bubble bubble-agent">
    <div class="bubble-name">Vinmec Agent</div>
    {msg["content"]}
  </div>
</div>""", unsafe_allow_html=True)
                if msg.get("traces"):
                    with st.expander(f"🔍 Xem ReAct Trace ({len(msg['traces'])} bước)", expanded=False):
                        render_trace(msg["traces"])

    # ── Form nhập liệu (submit chỉ khi bấm nút Gửi) ─────────────────────────
    with st.form("chat_form", clear_on_submit=True):
        col_in, col_btn = st.columns([5, 1])
        with col_in:
            # Dùng preset_query từ session_state làm giá trị mặc định
            user_input = st.text_input(
                "Câu hỏi",
                value=st.session_state.preset_query,
                placeholder="Nhập câu hỏi cho Vinmec Agent...",
                label_visibility="collapsed",
            )
        with col_btn:
            send = st.form_submit_button("Gửi ➤", type="primary", use_container_width=True)

    # Sau khi submit: xử lý và reset preset
    if send and user_input.strip():
        st.session_state.preset_query = ""   # xoá preset
        query = user_input.strip()
        st.session_state.chat_history.append({"role": "user", "content": query})

        with st.spinner("🤖 Agent đang suy luận..."):
            answer, traces = call_react_agent(query)

        st.session_state.all_traces.extend(traces)
        save_waterfall_trace(st.session_state.all_traces)
        st.session_state.chat_history.append({
            "role": "agent", "content": answer, "traces": traces,
        })
        st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 2 — SO SÁNH
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🔄 So sánh Chatbot vs Agent":
    st.markdown('<div class="section-title">🔄 So sánh Chatbot Baseline (Cấp 2) vs ReAct Agent (Cấp 3)</div>',
                unsafe_allow_html=True)

    st.markdown("""
<div class="info-box">
  <b>Cấp 2 — Chatbot Baseline:</b> LLM thuần túy, trả lời dựa trên kiến thức tĩnh, <b>không thể gọi Tool</b>.<br>
  <b>Cấp 3 — ReAct Agent:</b> Suy luận theo chu kỳ <code>Thought → Action → Observation</code>,
  gọi Tool qua MCP Server để lấy dữ liệu thực.
</div>
""", unsafe_allow_html=True)

    # Gợi ý (ngoài form)
    st.caption("💡 Click gợi ý để điền nhanh:")
    compare_suggestions = [
        "Tra cứu bác sĩ Tim mạch ngày 2026-09-20",
        "Đặt lịch với BS. Nguyễn Thị Lan, Nhi, lúc 2026-09-20 09:00, mã BN2026042",
        "Tra cứu bệnh nhân mã BN9999999",
    ]
    for idx, sug in enumerate(compare_suggestions):
        if st.button(sug, key=f"cmp_sug_{idx}"):
            st.session_state["compare_preset"] = sug
            st.rerun()

    # Form so sánh
    with st.form("compare_form"):
        query_cmp = st.text_input(
            "Câu hỏi để so sánh:",
            value=st.session_state.get("compare_preset", "Tra cứu bác sĩ Tim mạch ngày 2026-09-20"),
            label_visibility="visible",
        )
        run_cmp = st.form_submit_button("▶️ Chạy so sánh", type="primary")

    if run_cmp and query_cmp.strip():
        st.session_state["compare_preset"] = ""
        with st.spinner("Đang chạy cả 2 hệ thống..."):
            chatbot_resp          = call_chatbot(query_cmp)
            agent_answer, traces  = call_react_agent(query_cmp)
        st.session_state.all_traces.extend(traces)
        save_waterfall_trace(st.session_state.all_traces)
        st.session_state["compare_result"] = {
            "query":   query_cmp,
            "chatbot": chatbot_resp,
            "agent":   agent_answer,
            "traces":  traces,
        }

    if st.session_state.get("compare_result"):
        res = st.session_state["compare_result"]
        st.divider()
        st.markdown(f'**Câu hỏi:** _{res["query"]}_')
        st.markdown("")

        col_left, col_right = st.columns(2, gap="large")

        with col_left:
            st.markdown("""
<div style="background:#fce8e6;border-radius:10px;padding:.6rem 1rem;margin-bottom:.8rem">
  <b style="color:#c5221f">❌ Cấp 2 — Chatbot Baseline</b><br>
  <span style="font-size:.8rem;color:#7f2b2b">Không có Tool · Kiến thức tĩnh</span>
</div>""", unsafe_allow_html=True)
            st.markdown(f"""
<div class="chat-row">
  <div class="avatar avatar-bot">🤖</div>
  <div class="bubble bubble-bot">
    <div class="bubble-name">Chatbot</div>
    {res["chatbot"]}
  </div>
</div>""", unsafe_allow_html=True)

        with col_right:
            st.markdown("""
<div style="background:#e6f5f0;border-radius:10px;padding:.6rem 1rem;margin-bottom:.8rem">
  <b style="color:#005c3b">✅ Cấp 3 — ReAct Agent</b><br>
  <span style="font-size:.8rem;color:#006644">Tool Calling · MCP Server · Dữ liệu thực</span>
</div>""", unsafe_allow_html=True)
            st.markdown(f"""
<div class="chat-row">
  <div class="avatar avatar-agent">🤖</div>
  <div class="bubble bubble-agent">
    <div class="bubble-name">Vinmec Agent</div>
    {res["agent"]}
  </div>
</div>""", unsafe_allow_html=True)

            st.markdown("")
            st.markdown("**🔍 ReAct Trace:**")
            render_trace(res["traces"])

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 3 — TEST SUITE
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🧪 Test Suite":
    st.markdown('<div class="section-title">🧪 Test Suite — 5 Test Cases</div>', unsafe_allow_html=True)

    COMPLEXITY_COLOR = {"Low": "green", "Medium": "orange", "High": "red"}

    # Tổng quan
    for tc in test_cases:
        is_todo = tc["question"].strip().startswith("TODO")
        icon    = "⏸️" if is_todo else "✅"
        color   = COMPLEXITY_COLOR.get(tc.get("complexity", "Low"), "green")

        with st.expander(f"{icon} [{tc['id']}] {tc['type']}", expanded=False):
            c1, c2 = st.columns([1, 2])
            with c1:
                st.markdown(f"**Độ phức tạp:** {badge_html(tc.get('complexity',''), color)}",
                            unsafe_allow_html=True)
                st.markdown(f"**Loại:** `{tc['type']}`")
            with c2:
                st.markdown(f"**Câu hỏi:**")
                st.info(tc["question"])
                st.markdown(f"**Kỳ vọng:** _{tc['expected_behavior']}_")

    st.divider()

    if st.button("🚀 Chạy tất cả 5 Test Cases", type="primary", use_container_width=True):
        bar     = st.progress(0, text="Chuẩn bị...")
        results = []
        new_traces: list[dict] = []

        for i, tc in enumerate(test_cases):
            bar.progress((i + 1) / len(test_cases), text=f"Đang chạy {tc['id']}...")
            if tc["question"].strip().startswith("TODO"):
                results.append({"tc": tc, "status": "skipped", "answer": "", "traces": []})
                continue
            with st.spinner(f"Chạy {tc['id']}..."):
                ans, traces = call_react_agent(tc["question"])
            new_traces.extend(traces)
            results.append({"tc": tc, "status": "done", "answer": ans, "traces": traces})

        bar.progress(1.0, text="✅ Hoàn tất!")
        st.session_state.all_traces.extend(new_traces)
        st.session_state.test_results = results
        save_waterfall_trace(st.session_state.all_traces)

    if st.session_state.test_results:
        st.divider()
        passed  = sum(1 for r in st.session_state.test_results if r["status"] == "done")
        skipped = sum(1 for r in st.session_state.test_results if r["status"] == "skipped")

        m1, m2, m3 = st.columns(3)
        m1.metric("✅ Đã chạy",    passed)
        m2.metric("⏸️ Bỏ qua",    skipped)
        m3.metric("📦 Trace events", sum(len(r["traces"]) for r in st.session_state.test_results))

        for res in st.session_state.test_results:
            tc   = res["tc"]
            icon = "✅" if res["status"] == "done" else "⏸️"
            color = COMPLEXITY_COLOR.get(tc.get("complexity",""), "green")

            with st.expander(f"{icon} [{tc['id']}] {tc['type']} — {badge_html(tc.get('complexity',''), color)}",
                             expanded=res["status"] == "done"):
                st.markdown(f"**Câu hỏi:** _{tc['question']}_")
                if res["answer"]:
                    st.markdown(f"""
<div class="chat-row">
  <div class="avatar avatar-agent">🤖</div>
  <div class="bubble bubble-agent">
    <div class="bubble-name">Kết quả</div>
    {res["answer"]}
  </div>
</div>""", unsafe_allow_html=True)
                if res["traces"]:
                    with st.expander("🔍 Xem ReAct Trace", expanded=False):
                        render_trace(res["traces"])

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 4 — WATERFALL TRACE LOG
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📊 Waterfall Trace Log":
    st.markdown('<div class="section-title">📊 Waterfall Trace Log</div>', unsafe_allow_html=True)

    trace_file = Path(__file__).parent / "docs" / "trace_waterfall.json"
    tab_live, tab_file = st.tabs(["🟢 Session hiện tại", "💾 File trace_waterfall.json"])

    with tab_live:
        traces = st.session_state.all_traces
        if not traces:
            st.markdown('<div class="empty-hint">Chưa có trace. Hãy chat hoặc chạy Test Suite trước.</div>',
                        unsafe_allow_html=True)
        else:
            tool_evs  = [e for e in traces if e.get("action_type") == "TOOL_EXECUTION"]
            final_evs = [e for e in traces if e.get("action_type") == "FINAL_ANSWER"]
            avg_lat   = sum(e.get("latency_ms", 0) for e in tool_evs) / max(len(tool_evs), 1)

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Tổng events",   len(traces))
            c2.metric("Tool calls",    len(tool_evs))
            c3.metric("Final answers", len(final_evs))
            c4.metric("Avg latency",   f"{avg_lat:.0f} ms")

            st.divider()

            ftype = st.multiselect(
                "Lọc theo loại bước:",
                ["TOOL_EXECUTION", "FINAL_ANSWER"],
                default=["TOOL_EXECUTION", "FINAL_ANSWER"],
            )
            render_trace([e for e in traces if e.get("action_type") in ftype])

            st.divider()
            st.download_button(
                "⬇️ Tải trace_waterfall.json",
                data=json.dumps(traces, ensure_ascii=False, indent=2),
                file_name="trace_waterfall.json",
                mime="application/json",
            )

    with tab_file:
        if trace_file.exists():
            with open(trace_file, encoding="utf-8") as f:
                file_data = json.load(f)
            st.caption(f"File: `{trace_file}` — {len(file_data)} events")
            st.json(file_data, expanded=False)
        else:
            st.warning("Chưa có file `docs/trace_waterfall.json`. Hãy chạy Agent để tạo file.")

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 5 — DATABASE & SCHEMA
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🗄️ Xem Database & Schema":
    st.markdown('<div class="section-title">🗄️ Mock Database & Tool Schemas</div>', unsafe_allow_html=True)

    tab_doc, tab_pat, tab_schema = st.tabs(["👨‍⚕️ Bác sĩ", "🧑‍💼 Bệnh nhân", "📐 Tool Schemas"])

    with tab_doc:
        st.caption("Nguồn: `DOCTOR_DATABASE` trong `src/tools.py`")
        for specialty, doctors in DOCTOR_DATABASE.items():
            st.markdown(f"#### 🩺 Chuyên khoa: {specialty}")
            for doc in doctors:
                with st.container(border=True):
                    c1, c2 = st.columns([2, 3])
                    with c1:
                        st.markdown(f"**{doc['name']}**")
                        st.caption(doc["title"])
                        st.markdown(f"🎓 _{doc['experience']}_")
                    with c2:
                        st.markdown("**📅 Lịch trống:**")
                        for slot in doc["available_slots"]:
                            st.markdown(f"- `{slot}`")

    with tab_pat:
        st.caption("Nguồn: `PATIENT_DATABASE` trong `src/tools.py`")
        rows = [
            {"Mã BN": pid, "Họ tên": d["name"], "Ngày sinh": d["dob"], "SĐT": d["phone"]}
            for pid, d in PATIENT_DATABASE.items()
        ]
        st.dataframe(rows, use_container_width=True, hide_index=True)
        st.caption("⚠️ Mã không có trong bảng này → book_appointment trả về NOT_FOUND.")

    with tab_schema:
        st.caption("Nguồn: `TOOLS_SCHEMA` trong `src/tools.py`")
        for tool in TOOLS_SCHEMA:
            with st.expander(f"🛠️ Tool: `{tool['name']}`", expanded=True):
                st.markdown(f"> {tool['description']}")
                props    = tool.get("parameters", {}).get("properties", {})
                required = tool.get("parameters", {}).get("required", [])
                rows = [
                    {
                        "Tham số":  k,
                        "Kiểu":     v.get("type", "string"),
                        "Bắt buộc": "✅" if k in required else "—",
                        "Mô tả":    v.get("description", ""),
                    }
                    for k, v in props.items()
                ]
                st.dataframe(rows, use_container_width=True, hide_index=True)
