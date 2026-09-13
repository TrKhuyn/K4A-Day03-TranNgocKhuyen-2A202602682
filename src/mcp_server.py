"""
mcp_server.py — Model Context Protocol (MCP) Server cho Vinmec Healthcare

Vai trò: Là lớp trung gian giữa ReAct Agent và các Tool thực thi.
  - Agent gọi  : mcp_server.call_tool(tool_name, arguments)
  - MCP Server : chuyển tiếp sang dispatch_tool_call() trong tools.py
  - Trả về     : phản hồi đóng gói theo chuẩn JSON-RPC 2.0

Lý do tách biệt MCP Server với tools.py:
  Theo kiến trúc MCP, Agent không gọi trực tiếp Tool —
  tất cả phải đi qua MCP Server để đảm bảo chuẩn hóa, logging, và bảo mật.
"""

import json
import sys
from typing import Any

from tools import TOOLS_SCHEMA, dispatch_tool_call

# Đảm bảo terminal Windows hiển thị đúng tiếng Việt
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════════════
# MCP SERVER CLASS
# ═══════════════════════════════════════════════════════════════════════════════

class MCPVinmecServer:
    """
    Giả lập MCP Server tuân thủ chuẩn Model Context Protocol.

    Cung cấp 2 phương thức chính mà Agent sử dụng:
      • list_tools() : Liệt kê tất cả Tool có sẵn (dạng JSON Schema).
      • call_tool()  : Gọi thực thi một Tool cụ thể, trả về JSON-RPC response.
    """

    def __init__(self, server_name: str = "vinmec-healthcare-mcp-server") -> None:
        self.server_name = server_name
        self.version = "2026.1.0"

    def list_tools(self) -> list[dict]:
        """
        Trả về danh sách JSON Schema của tất cả Tool đã đăng ký.
        Agent dùng danh sách này để biết có thể gọi những Tool nào.
        """
        return TOOLS_SCHEMA

    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """
        Thực thi một Tool theo chuẩn MCP JSON-RPC 2.0.

        Luồng xử lý:
          1. Gọi dispatch_tool_call() → nhận chuỗi JSON thô từ Tool.
          2. Parse chuỗi JSON → Python dict.
          3. Đóng gói vào chuẩn JSON-RPC 2.0 rồi trả về.

        Args:
            tool_name : Tên Tool cần gọi (ví dụ: 'doctor_query').
            arguments : Tham số đầu vào cho Tool (ví dụ: {'specialty': 'Tim mạch'}).

        Returns:
            Dict theo chuẩn JSON-RPC 2.0:
            {
                "jsonrpc": "2.0",
                "server" : <tên server>,
                "tool"   : <tên tool được gọi>,
                "result" : <kết quả từ Tool dưới dạng dict>
            }
        """
        # Bước 1: Gọi Tool qua dispatcher, nhận JSON string
        raw_json_str = dispatch_tool_call(tool_name, arguments)

        # Bước 2: Parse JSON string → dict (xử lý lỗi nếu JSON không hợp lệ)
        try:
            result_dict = json.loads(raw_json_str)
        except (json.JSONDecodeError, TypeError):
            result_dict = {"status": "PARSE_ERROR", "raw_response": raw_json_str}

        # Bước 3: Đóng gói theo chuẩn JSON-RPC 2.0
        return {
            "jsonrpc": "2.0",
            "server":  self.server_name,
            "tool":    tool_name,
            "result":  result_dict,
        }


# Alias để tương thích với import cũ trong app.py
MCPAcademicServer = MCPVinmecServer


# ═══════════════════════════════════════════════════════════════════════════════
# SELF-TEST — Chạy trực tiếp để kiểm tra MCP Server hoạt động đúng
# ═══════════════════════════════════════════════════════════════════════════════

def _run_self_test() -> None:
    """Kiểm tra nhanh server sau khi hoàn thiện TODO 1.2 và TODO 2.1."""
    server = MCPVinmecServer()
    tools = server.list_tools()

    print("=" * 60)
    print("🔌 KIỂM THỬ MCP SERVER: vinmec-healthcare-mcp-server")
    print("=" * 60)
    print(f"✅ Server: {server.server_name}  |  Phiên bản: {server.version}")
    print(f"📦 Số Tool đã đăng ký: {len(tools)}\n")

    # ── Kiểm tra TODO 1.2: Tool schema đã có properties chưa? ──────────────
    book_tool = next((t for t in tools if t.get("name") == "book_appointment"), None)
    has_properties = bool(book_tool and book_tool.get("parameters", {}).get("properties"))
    status_1_2 = "✅" if has_properties else "⏳"
    print(f"{status_1_2} [Task 1.2] Tool 'book_appointment' schema: {'ĐỦ' if has_properties else 'THIẾU properties'}")

    # ── Kiểm tra TODO 2.1: call_tool() có trả về kết quả không? ───────────
    test_response = server.call_tool("doctor_query", {"specialty": "Tim mạch"})
    has_result = bool(test_response.get("result"))
    status_2_1 = "✅" if has_result else "⏳"
    print(f"{status_2_1} [Task 2.1] call_tool() 'doctor_query': {'OK' if has_result else 'Trả về rỗng'}")

    if has_result:
        # Chỉ in 200 ký tự đầu để tránh log quá dài
        preview = json.dumps(test_response, ensure_ascii=False)[:200]
        print(f"   Phản hồi JSON-RPC (200 ký tự đầu): {preview}...")

    # ── Test đặt lịch ──────────────────────────────────────────────────────
    print()
    book_response = server.call_tool("book_appointment", {
        "patient_id":   "BN2026042",
        "doctor_name":  "BS. Nguyễn Thị Lan",
        "specialty":    "Nhi",
        "datetime_str": "2026-09-20 09:00",
    })
    book_result = book_response.get("result", {})
    print(f"✅ Test 'book_appointment': status = {book_result.get('status')}")
    if book_result.get("booking_id"):
        print(f"   Mã đặt lịch: {book_result['booking_id']}")


if __name__ == "__main__":
    _run_self_test()
