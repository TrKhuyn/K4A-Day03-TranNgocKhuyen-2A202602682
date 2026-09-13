"""
providers.py — LLM Provider Adapter (Gemini · OpenAI · Mock Offline)

Vai trò: Cung cấp interface thống nhất để ReAct Agent giao tiếp với bất kỳ
LLM nào mà không cần biết chi tiết SDK cụ thể.

Cách chọn Provider: đặt biến môi trường LLM_PROVIDER trong file .env
  LLM_PROVIDER=gemini   → dùng Google Gemini  (yêu cầu GEMINI_API_KEY)
  LLM_PROVIDER=openai   → dùng OpenAI GPT     (yêu cầu OPENAI_API_KEY)
  LLM_PROVIDER=mock     → dùng Mock offline   (không cần API Key)

Khi API Key chưa được cấu hình, tất cả Provider tự động fallback về Mock.
"""

import json
import os
import re
import sys
from abc import ABC, abstractmethod
from typing import Any

from dotenv import load_dotenv

load_dotenv()

# Đảm bảo terminal Windows hiển thị đúng tiếng Việt
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════════════
# BASE INTERFACE — Tất cả Provider phải kế thừa và implement đủ 2 phương thức
# ═══════════════════════════════════════════════════════════════════════════════

class BaseLLMProvider(ABC):
    """
    Abstract base class định nghĩa interface chung cho mọi LLM Provider.

    Mọi Provider (Gemini, OpenAI, Mock) phải implement:
      • generate()           : sinh văn bản đơn thuần (Chatbot Baseline).
      • generate_with_tools(): sinh phản hồi có thể kèm Tool Call (ReAct Agent).
    """

    model_name: str = "base"

    @abstractmethod
    def generate(self, prompt: str, system_prompt: str = "") -> str:
        """
        Sinh văn bản phản hồi cho prompt (không có Tool Calling).
        Dùng cho Chatbot Baseline.
        """

    @abstractmethod
    def generate_with_tools(
        self,
        prompt: str,
        tools_schema: list[dict],
        system_prompt: str = "",
    ) -> dict[str, Any]:
        """
        Sinh phản hồi có hỗ trợ Native Tool Calling. Dùng cho ReAct Agent.

        Returns:
            Một trong 2 dạng dict:
              • {"type": "text",      "content": str,  "thought": str}
              • {"type": "tool_call", "tool_name": str, "arguments": dict, "thought": str}
        """


# ═══════════════════════════════════════════════════════════════════════════════
# MOCK OFFLINE PROVIDER — Chạy không cần API Key, dùng rule-based intent detection
# ═══════════════════════════════════════════════════════════════════════════════

# Từ khoá nhận diện intent "đặt lịch"
_BOOKING_KEYWORDS = ("đặt lịch", "book", "đặt hẹn")

# Từ khoá nhận diện intent "tra cứu bác sĩ"
_DOCTOR_QUERY_KEYWORDS = ("tra cứu", "bác sĩ", "chuyên khoa", "lịch khám", "doctor")

# Ánh xạ từ khoá → tên chuyên khoa chuẩn
_SPECIALTY_KEYWORD_MAP = {
    "nhi":       "Nhi",
    "da liễu":   "Da liễu",
    "nội":       "Nội tổng quát",
    "tim mạch":  "Tim mạch",
}
_DEFAULT_SPECIALTY = "Tim mạch"

# Mã bệnh nhân mặc định khi không tìm thấy trong prompt
_DEFAULT_PATIENT_ID = "BN2026042"


class MockOfflineProvider(BaseLLMProvider):
    """
    Provider chạy offline, không cần API Key.

    Sử dụng rule-based keyword matching để mô phỏng quyết định của LLM:
      - Nhận ra "đặt lịch" + mã bệnh nhân → gọi book_appointment
      - Nhận ra từ khoá bác sĩ/chuyên khoa  → gọi doctor_query
      - Câu hỏi khác                         → trả lời văn bản trực tiếp
    """

    model_name = "Offline-Mock-Model-2026"

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        return (
            "[Mock Chatbot] Xin chào! Tôi là Trợ lý Vinmec. "
            "Tôi không có quyền tra cứu dữ liệu thời gian thực trong chế độ này."
        )

    def generate_with_tools(
        self,
        prompt: str,
        tools_schema: list[dict],
        system_prompt: str = "",
    ) -> dict[str, Any]:
        prompt_lower = prompt.lower()

        # ── Nhánh 1: Đặt lịch ──────────────────────────────────────────────
        wants_booking = any(kw in prompt_lower for kw in _BOOKING_KEYWORDS)
        has_patient   = "bn" in prompt_lower or "bệnh nhân" in prompt_lower

        if wants_booking and has_patient:
            patient_id = self._extract_patient_id(prompt_lower)
            return {
                "type":      "tool_call",
                "tool_name": "book_appointment",
                "arguments": {
                    "patient_id":   patient_id,
                    "doctor_name":  "BS. Nguyễn Thị Lan",
                    "specialty":    "Nhi",
                    "datetime_str": "2026-09-20 09:00",
                },
                "thought": (
                    f"Bệnh nhân yêu cầu đặt lịch khám. "
                    f"Tôi sẽ gọi book_appointment với mã bệnh nhân {patient_id}."
                ),
            }

        # ── Nhánh 2: Tra cứu bác sĩ ────────────────────────────────────────
        wants_doctor_query = any(kw in prompt_lower for kw in _DOCTOR_QUERY_KEYWORDS)

        if wants_doctor_query:
            specialty = self._detect_specialty(prompt_lower)
            return {
                "type":      "tool_call",
                "tool_name": "doctor_query",
                "arguments": {"specialty": specialty},
                "thought":   f"Bệnh nhân muốn tra cứu bác sĩ chuyên khoa {specialty}. Gọi doctor_query.",
            }

        # ── Nhánh 3: Câu hỏi chung — trả lời trực tiếp ────────────────────
        return {
            "type":    "text",
            "content": (
                "Xin chào! Bệnh viện Vinmec cung cấp các chuyên khoa: "
                "Tim mạch, Nhi, Da liễu, Nội tổng quát. "
                "Tôi có thể tra cứu lịch bác sĩ và đặt lịch khám cho bạn."
            ),
            "thought": "Câu hỏi chung về Vinmec — trả lời trực tiếp, không cần gọi Tool.",
        }

    # ── Helper methods ──────────────────────────────────────────────────────

    @staticmethod
    def _extract_patient_id(prompt_lower: str) -> str:
        """Trích xuất mã bệnh nhân dạng 'bn<số>' từ prompt. Trả về mặc định nếu không tìm thấy."""
        match = re.search(r"bn\d+", prompt_lower)
        return match.group().upper() if match else _DEFAULT_PATIENT_ID

    @staticmethod
    def _detect_specialty(prompt_lower: str) -> str:
        """Xác định chuyên khoa từ từ khoá trong prompt. Trả về mặc định nếu không rõ."""
        for keyword, specialty in _SPECIALTY_KEYWORD_MAP.items():
            if keyword in prompt_lower:
                return specialty
        return _DEFAULT_SPECIALTY


# ═══════════════════════════════════════════════════════════════════════════════
# GEMINI PROVIDER — Kết nối Google Gemini API với Native Tool Calling
# ═══════════════════════════════════════════════════════════════════════════════

_GEMINI_PLACEHOLDER = "your_gemini_api_key_here"


class GeminiProvider(BaseLLMProvider):
    """
    Provider sử dụng Google Gemini API (google-genai SDK).
    Hỗ trợ Native Function Calling — Gemini tự quyết định gọi Tool nào.
    """

    def __init__(self, api_key: str = "", model: str = "") -> None:
        self.api_key    = api_key    or os.getenv("GEMINI_API_KEY", "")
        self.model_name = model      or os.getenv("LLM_MODEL", "gemini-2.5-flash")

    def _is_api_key_valid(self) -> bool:
        return bool(self.api_key) and self.api_key != _GEMINI_PLACEHOLDER

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        if not self._is_api_key_valid():
            return "[Gemini] Chưa cấu hình GEMINI_API_KEY trong file .env."

        try:
            from google import genai  # type: ignore

            client   = genai.Client(api_key=self.api_key)
            contents = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
            response = client.models.generate_content(model=self.model_name, contents=contents)
            return response.text or ""
        except Exception as exc:
            return f"[Gemini Error] {exc}"

    def generate_with_tools(
        self,
        prompt: str,
        tools_schema: list[dict],
        system_prompt: str = "",
    ) -> dict[str, Any]:
        if not self._is_api_key_valid():
            print("ℹ️ [Gemini] Chưa có API Key hợp lệ — tự động dùng MockOfflineProvider.")
            return MockOfflineProvider().generate_with_tools(prompt, tools_schema, system_prompt)

        try:
            from google import genai        # type: ignore
            from google.genai import types  # type: ignore

            client = genai.Client(api_key=self.api_key)

            # Chuyển TOOLS_SCHEMA sang định dạng Gemini SDK yêu cầu
            function_declarations = [
                {
                    "name":        tool["name"],
                    "description": tool.get("description", ""),
                    "parameters":  tool.get("parameters", {}),
                }
                for tool in tools_schema
                if tool.get("name") and tool.get("parameters")
            ]

            config = types.GenerateContentConfig(
                system_instruction=system_prompt or None,
                tools=[{"function_declarations": function_declarations}] if function_declarations else None,
                temperature=0.2,
            )

            response = client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config,
            )

            # Gemini trả về Tool Call
            if response.function_calls:
                call = response.function_calls[0]
                args = dict(call.args) if hasattr(call, "args") and call.args else {}
                return {
                    "type":      "tool_call",
                    "tool_name": call.name,
                    "arguments": args,
                    "thought":   f"Gemini gọi tool '{call.name}' với tham số: {json.dumps(args, ensure_ascii=False)}",
                }

            # Gemini trả về văn bản trực tiếp
            return {
                "type":    "text",
                "content": response.text or "",
                "thought": "Gemini trả lời trực tiếp (không cần gọi Tool).",
            }

        except Exception as exc:
            print(f"⚠️ [Gemini] Lỗi kết nối API ({exc}) — fallback về Mock.")
            return MockOfflineProvider().generate_with_tools(prompt, tools_schema, system_prompt)


# ═══════════════════════════════════════════════════════════════════════════════
# OPENAI PROVIDER — Kết nối OpenAI API với Native Tool Calling
# ═══════════════════════════════════════════════════════════════════════════════

_OPENAI_PLACEHOLDER = "your_openai_api_key_here"


class OpenAIProvider(BaseLLMProvider):
    """
    Provider sử dụng OpenAI API (openai SDK).
    Hỗ trợ Native Function Calling — GPT tự quyết định gọi Tool nào.
    """

    def __init__(self, api_key: str = "", model: str = "") -> None:
        self.api_key    = api_key or os.getenv("OPENAI_API_KEY", "")
        self.model_name = model   or os.getenv("LLM_MODEL", "gpt-4o-mini")

    def _is_api_key_valid(self) -> bool:
        return bool(self.api_key) and self.api_key != _OPENAI_PLACEHOLDER

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        if not self._is_api_key_valid():
            return "[OpenAI] Chưa cấu hình OPENAI_API_KEY trong file .env."

        try:
            from openai import OpenAI  # type: ignore

            client   = OpenAI(api_key=self.api_key)
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            response = client.chat.completions.create(model=self.model_name, messages=messages)
            return response.choices[0].message.content or ""
        except Exception as exc:
            return f"[OpenAI Error] {exc}"

    def generate_with_tools(
        self,
        prompt: str,
        tools_schema: list[dict],
        system_prompt: str = "",
    ) -> dict[str, Any]:
        if not self._is_api_key_valid():
            print("ℹ️ [OpenAI] Chưa có API Key hợp lệ — tự động dùng MockOfflineProvider.")
            return MockOfflineProvider().generate_with_tools(prompt, tools_schema, system_prompt)

        try:
            from openai import OpenAI  # type: ignore

            client = OpenAI(api_key=self.api_key)

            # Chuyển TOOLS_SCHEMA sang định dạng OpenAI SDK yêu cầu
            openai_tools = [
                {
                    "type": "function",
                    "function": {
                        "name":        tool["name"],
                        "description": tool.get("description", ""),
                        "parameters":  tool.get("parameters", {}),
                    },
                }
                for tool in tools_schema
                if tool.get("name")
            ]

            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            response = client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                tools=openai_tools or None,
                tool_choice="auto" if openai_tools else None,
            )

            message = response.choices[0].message

            # OpenAI trả về Tool Call
            if message.tool_calls:
                call = message.tool_calls[0]
                args = json.loads(call.function.arguments) if call.function.arguments else {}
                return {
                    "type":      "tool_call",
                    "tool_name": call.function.name,
                    "arguments": args,
                    "thought":   f"OpenAI gọi tool '{call.function.name}' với tham số: {json.dumps(args, ensure_ascii=False)}",
                }

            # OpenAI trả về văn bản trực tiếp
            return {
                "type":    "text",
                "content": message.content or "",
                "thought": "OpenAI trả lời trực tiếp (không cần gọi Tool).",
            }

        except Exception as exc:
            print(f"⚠️ [OpenAI] Lỗi kết nối API ({exc}) — fallback về Mock.")
            return MockOfflineProvider().generate_with_tools(prompt, tools_schema, system_prompt)


# ═══════════════════════════════════════════════════════════════════════════════
# FACTORY FUNCTION — Tạo Provider đúng loại theo biến môi trường LLM_PROVIDER
# ═══════════════════════════════════════════════════════════════════════════════

def get_llm_provider() -> BaseLLMProvider:
    """
    Khởi tạo và trả về Provider phù hợp dựa trên biến môi trường LLM_PROVIDER.

    Nếu API Key chưa được cấu hình hoặc LLM_PROVIDER không hợp lệ,
    tự động trả về MockOfflineProvider để tránh crash.
    """
    provider_type = os.getenv("LLM_PROVIDER", "gemini").strip().lower()

    if provider_type == "gemini":
        api_key = os.getenv("GEMINI_API_KEY", "")
        if api_key and api_key != _GEMINI_PLACEHOLDER:
            return GeminiProvider()
        print("ℹ️ [Config] GEMINI_API_KEY chưa được đặt — dùng MockOfflineProvider.")
        return MockOfflineProvider()

    if provider_type == "openai":
        api_key = os.getenv("OPENAI_API_KEY", "")
        if api_key and api_key != _OPENAI_PLACEHOLDER:
            return OpenAIProvider()
        print("ℹ️ [Config] OPENAI_API_KEY chưa được đặt — dùng MockOfflineProvider.")
        return MockOfflineProvider()

    if provider_type == "mock":
        return MockOfflineProvider()

    print(f"⚠️ [Config] LLM_PROVIDER='{provider_type}' không hợp lệ — dùng MockOfflineProvider.")
    return MockOfflineProvider()
