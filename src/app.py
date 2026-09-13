"""
app.py — Ứng dụng chính: Chạy Chatbot Baseline và ReAct Agent cho Vinmec

Hỗ trợ 3 chế độ chạy qua command-line argument:
  python src/app.py --all         → Chạy toàn bộ 5 Test Cases, xuất Waterfall Trace Log
  python src/app.py --interactive → Chat trực tiếp với ReAct Agent
  python src/app.py               → Demo 1 Test Case mẫu

Luồng chính của ReAct Agent (hàm run_react_agent):
  User Query → LLM Thought → [Tool Call → MCP Server → Observation]* → Final Answer
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Thêm thư mục src vào sys.path để import module ngang hàng
sys.path.append(str(Path(__file__).parent))

# Đảm bảo terminal Windows hiển thị đúng tiếng Việt
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from mcp_server import MCPVinmecServer
from prompts import CHATBOT_BASELINE_PROMPT, REACT_AGENT_SYSTEM_PROMPT, MAX_ITERATIONS
from providers import BaseLLMProvider, get_llm_provider

load_dotenv()

# Đường dẫn gốc của project (một cấp trên thư mục src/)
PROJECT_ROOT = Path(__file__).parent.parent


# ═══════════════════════════════════════════════════════════════════════════════
# I/O HELPERS — Đọc cấu hình và ghi kết quả ra file
# ═══════════════════════════════════════════════════════════════════════════════

def load_test_cases() -> list[dict]:
    """
    Tải danh sách Test Cases từ config/test_cases.json.
    Nếu file chưa tồn tại, tự động dùng file mẫu test_cases.example.json.

    Returns:
        Danh sách dict, mỗi phần tử là một test case.
    """
    primary_path = PROJECT_ROOT / "config" / "test_cases.json"
    fallback_path = PROJECT_ROOT / "config" / "test_cases.example.json"

    if primary_path.exists():
        config_path = primary_path
    elif fallback_path.exists():
        print("⚠️  Chưa thấy 'config/test_cases.json' — đang dùng file mẫu.")
        print("👉  Chạy: copy config/test_cases.example.json config/test_cases.json\n")
        config_path = fallback_path
    else:
        raise FileNotFoundError("Không tìm thấy file test_cases.json hoặc test_cases.example.json.")

    with open(config_path, encoding="utf-8") as f:
        return json.load(f)


def save_waterfall_trace(trace_events: list[dict]) -> None:
    """
    Lưu danh sách sự kiện trace (Waterfall Log) ra file docs/trace_waterfall.json.
    Tự động tạo thư mục docs/ nếu chưa tồn tại.

    Args:
        trace_events: Danh sách các sự kiện trace được thu thập trong quá trình chạy.
    """
    output_path = PROJECT_ROOT / "docs" / "trace_waterfall.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(trace_events, f, ensure_ascii=False, indent=2)

    print(f"📊 Đã lưu {len(trace_events)} sự kiện Waterfall Trace → '{output_path}'")


# ═══════════════════════════════════════════════════════════════════════════════
# CHATBOT BASELINE (Cấp 2) — LLM thuần, không có Tool
# ═══════════════════════════════════════════════════════════════════════════════

def run_baseline_chatbot(user_query: str, provider: BaseLLMProvider) -> None:
    """
    Chạy Chatbot Baseline: gửi câu hỏi trực tiếp đến LLM, không có Tool Calling.
    Dùng để so sánh với ReAct Agent (Cấp 3).

    Args:
        user_query: Câu hỏi của bệnh nhân/người dùng.
        provider  : LLM Provider đã được khởi tạo.
    """
    print(f"\n💬 [CHATBOT BASELINE] {user_query}")
    response = provider.generate(user_query, system_prompt=CHATBOT_BASELINE_PROMPT)
    print(f"🤖 Phản hồi: {response}")


# ═══════════════════════════════════════════════════════════════════════════════
# REACT AGENT (Cấp 3) — Vòng lặp Thought → Action → Observation
# ═══════════════════════════════════════════════════════════════════════════════

def _build_final_answer_from_observation(tool_name: str, obs_data: dict) -> str:
    """
    Chuyển đổi dữ liệu Observation từ MCP Server thành câu trả lời thân thiện.

    Tách riêng hàm này giúp run_react_agent() gọn hơn và dễ mở rộng
    khi thêm Tool mới — chỉ cần thêm nhánh elif tại đây.

    Args:
        tool_name: Tên Tool vừa được thực thi ('doctor_query' hoặc 'book_appointment').
        obs_data : Dict kết quả từ MCP Server.

    Returns:
        Chuỗi văn bản phản hồi cuối cùng gửi đến người dùng.
    """
    status = obs_data.get("status")

    # ── Trường hợp không tìm thấy / không còn lịch trống ──────────────────
    if status in ("NOT_FOUND", "NO_AVAILABILITY"):
        return obs_data.get("message", "Không tìm thấy thông tin yêu cầu.")

    # ── Trường hợp thành công ──────────────────────────────────────────────
    if status == "SUCCESS":

        if tool_name == "doctor_query":
            specialty    = obs_data.get("specialty", "")
            date_filter  = obs_data.get("date_filter", "")
            doctors      = obs_data.get("doctors", [])

            if not doctors:
                return f"Không có bác sĩ chuyên khoa {specialty} khả dụng trong thời gian yêu cầu."

            # Định dạng từng dòng bác sĩ: tên · chức danh · kinh nghiệm · lịch trống
            doctor_lines = [
                f"  • {d['name']} ({d.get('title', '')}) — {d.get('experience', '')} "
                f"| Lịch trống: {', '.join(d.get('available_slots', [])[:3])}"
                for d in doctors
            ]
            return (
                f"Chuyên khoa {specialty} ({date_filter}) — {len(doctors)} bác sĩ:\n"
                + "\n".join(doctor_lines)
            )

        if tool_name == "book_appointment":
            return obs_data.get("message", "Đặt lịch thành công tại Vinmec.")

    # ── Trường hợp phản hồi không xác định ────────────────────────────────
    return f"Phản hồi từ MCP Server: {json.dumps(obs_data, ensure_ascii=False)}"


def run_react_agent(
    user_query: str,
    provider: BaseLLMProvider,
    mcp_server: MCPVinmecServer,
) -> list[dict[str, Any]]:
    """
    Thực thi vòng lặp ReAct (Thought → Action → Observation) cho một câu hỏi.

    Vòng lặp sẽ dừng khi:
      • LLM trả về câu trả lời cuối cùng (type == "text"), hoặc
      • Sau khi nhận Observation từ Tool và tổng hợp Final Answer, hoặc
      • Đạt đến giới hạn MAX_ITERATIONS.

    Args:
        user_query : Câu hỏi của bệnh nhân.
        provider   : LLM Provider (Gemini / OpenAI / Mock).
        mcp_server : MCP Server cung cấp danh sách Tool và thực thi Tool.

    Returns:
        Danh sách trace event theo thứ tự thực thi, dùng để xuất Waterfall Log.
    """
    print(f"\n{'─' * 55}")
    print(f"🤖 [REACT AGENT] {user_query}")

    trace_events: list[dict[str, Any]] = []
    available_tools = mcp_server.list_tools()
    step = 0

    while step < MAX_ITERATIONS:
        step += 1
        print(f"\n  ── Bước {step}/{MAX_ITERATIONS}: Gọi LLM ──")

        # ── THOUGHT + ACTION: LLM quyết định làm gì tiếp theo ──────────────
        t0 = time.time()
        llm_response = provider.generate_with_tools(
            user_query,
            available_tools,
            system_prompt=REACT_AGENT_SYSTEM_PROMPT,
        )
        latency_ms = round((time.time() - t0) * 1000, 2)

        thought      = llm_response.get("thought", "Đang suy luận...")
        response_type = llm_response.get("type")

        print(f"  🧠 Thought : {thought}")

        # ── Nhánh A: LLM trả lời trực tiếp (không cần Tool) ────────────────
        if response_type == "text":
            final_answer = llm_response.get("content", "")
            print(f"  🏁 Final Answer: {final_answer}")

            trace_events.append({
                "step":        step,
                "query":       user_query,
                "action_type": "FINAL_ANSWER",
                "thought":     thought,
                "output":      final_answer,
                "latency_ms":  latency_ms,
            })
            break

        # ── Nhánh B: LLM đề xuất gọi Tool ──────────────────────────────────
        if response_type == "tool_call":
            tool_name = llm_response.get("tool_name", "")
            arguments = llm_response.get("arguments", {})

            print(f"  🛠️  Action  : {tool_name}({arguments})")

            # OBSERVATION: Thực thi Tool qua MCP Server
            mcp_response = mcp_server.call_tool(tool_name, arguments)
            obs_data     = mcp_response.get("result", {})

            if not obs_data:
                # MCP Server trả về rỗng — TODO 2.1 chưa hoàn thiện
                print("  👁️  Observation: (rỗng — kiểm tra TODO 2.1 trong mcp_server.py)")
                final_answer = "Chưa nhận được dữ liệu từ MCP Server."
            else:
                obs_preview = json.dumps(obs_data, ensure_ascii=False)
                print(f"  👁️  Observation: {obs_preview}")
                final_answer = _build_final_answer_from_observation(tool_name, obs_data)

            # Ghi trace: Tool Execution
            trace_events.append({
                "step":        step,
                "query":       user_query,
                "action_type": "TOOL_EXECUTION",
                "tool_name":   tool_name,
                "arguments":   arguments,
                "observation": obs_data,
                "latency_ms":  latency_ms,
            })

            print(f"  🧠 Thought : Đã có Observation — tổng hợp câu trả lời.")
            print(f"  🏁 Final Answer: {final_answer}")

            # Ghi trace: Final Answer
            trace_events.append({
                "step":        step + 1,
                "query":       user_query,
                "action_type": "FINAL_ANSWER",
                "thought":     "Tổng hợp kết quả từ MCP Server thành công.",
                "output":      final_answer,
                "latency_ms":  10.0,
            })
            break

    return trace_events


# ═══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT — Xử lý 3 chế độ chạy: --all | --interactive | (default demo)
# ═══════════════════════════════════════════════════════════════════════════════

def _run_all_test_cases(
    tests: list[dict],
    provider: BaseLLMProvider,
    mcp_server: MCPVinmecServer,
) -> None:
    """Chạy tuần tự 5 Test Cases, thu thập trace và lưu Waterfall Log."""
    print("🚀 [TEST SUITE] Chạy toàn bộ 5 Test Cases\n")
    all_traces: list[dict] = []
    passed = 0
    skipped = 0

    for tc in tests:
        print(f"\n{'═' * 55}")
        print(f"🧪 [{tc['id']}] {tc['type']}  (Độ phức tạp: {tc['complexity']})")
        print(f"📌 Kỳ vọng: {tc['expected_behavior']}")

        question = tc["question"].strip()

        if question.startswith("TODO"):
            print("  ⏸️  Câu hỏi chưa được điền — bỏ qua.")
            print(f"     '{question}'")
            skipped += 1
            continue

        trace = run_react_agent(question, provider, mcp_server)
        all_traces.extend(trace)
        passed += 1

    print(f"\n{'═' * 55}")
    print(f"📊 Kết quả: {passed}/{len(tests)} test đã chạy | {skipped} bỏ qua (TODO)")

    if all_traces:
        save_waterfall_trace(all_traces)

    print("💡 Chat trực tiếp: python src/app.py --interactive")


def _run_interactive_mode(provider: BaseLLMProvider, mcp_server: MCPVinmecServer) -> None:
    """Mở phiên chat trực tiếp với ReAct Agent — gõ 'exit' để thoát."""
    print("🎮 [INTERACTIVE] Chat trực tiếp với Vinmec ReAct Agent")
    print("─" * 55)
    print("💡 Gợi ý:")
    print("   • 'Vinmec có những chuyên khoa nào?'")
    print("   • 'Tra cứu bác sĩ Tim mạch ngày 20/09/2026'")
    print("   • 'Đặt lịch với BS. Nguyễn Thị Lan, Nhi, 9h ngày 20/09, mã BN2026042'")
    print("   • Gõ 'exit' hoặc 'quit' để thoát.\n")

    while True:
        try:
            user_input = input("👤 Bệnh nhân: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n👋 Đã thoát.")
            break

        if not user_input:
            continue

        if user_input.lower() in ("exit", "quit"):
            print("👋 Tạm biệt! Chúc bạn sức khỏe.")
            break

        trace = run_react_agent(user_input, provider, mcp_server)
        save_waterfall_trace(trace)


def _run_default_demo(tests: list[dict], provider: BaseLLMProvider, mcp_server: MCPVinmecServer) -> None:
    """Chạy demo 1 Test Case mẫu khi không có argument nào được truyền vào."""
    print("ℹ️  HƯỚNG DẪN:")
    print("   python src/app.py --all         → chạy 5 Test Cases")
    print("   python src/app.py --interactive → chat trực tiếp\n")

    sample_question = tests[1]["question"]  # TC02: tra cứu bác sĩ
    print("─" * 55)
    print("🎬 DEMO: TC02 — Tra cứu bác sĩ Tim mạch")

    trace = run_react_agent(sample_question, provider, mcp_server)
    save_waterfall_trace(trace)
    print("\n💡 Hãy thử: python src/app.py --interactive")


if __name__ == "__main__":
    print("=" * 55)
    print("🏥 VINMEC HEALTHCARE — CHATBOT vs REACT AGENT (Day 03)")
    print("=" * 55)

    # Khởi tạo Provider và MCP Server
    provider   = get_llm_provider()
    mcp_server = MCPVinmecServer()

    print(f"🔌 LLM Provider : {provider.__class__.__name__} ({provider.model_name})")
    print(f"🌐 MCP Server   : {mcp_server.server_name} v{mcp_server.version}\n")

    # Tải Test Cases
    tests = load_test_cases()
    print(f"✅ Đã tải {len(tests)} Test Cases.\n")

    # Điều phối chế độ chạy theo argument
    args = sys.argv[1:]

    if "--all" in args:
        _run_all_test_cases(tests, provider, mcp_server)
    elif "--interactive" in args:
        _run_interactive_mode(provider, mcp_server)
    else:
        _run_default_demo(tests, provider, mcp_server)
