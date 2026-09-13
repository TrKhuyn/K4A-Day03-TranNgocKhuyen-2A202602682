"""
tools.py — Khai báo Tool Schemas & Execution Layer cho Vinmec Healthcare Agent

Kiến trúc file:
  1. TOOLS_SCHEMA      : Khai báo JSON Schema cho LLM hiểu cách gọi từng Tool.
  2. DOCTOR_DATABASE   : Dữ liệu mô phỏng bác sĩ Vinmec theo chuyên khoa.
  3. PATIENT_DATABASE  : Dữ liệu mô phỏng bệnh nhân (dùng để validate mã BN).
  4. execute_*         : Hàm thực thi logic từng Tool, trả về JSON string.
  5. dispatch_tool_call: Hàm điều phối — nhận tên Tool → gọi đúng execute_*.
"""

import json
import random
from typing import Any, Optional

# ═══════════════════════════════════════════════════════════════════════════════
# 1. TOOL SCHEMAS — Khai báo cho LLM biết cách sử dụng từng công cụ
#    Tuân thủ chuẩn JSON Schema (https://json-schema.org)
# ═══════════════════════════════════════════════════════════════════════════════

TOOLS_SCHEMA: list[dict] = [

    # ── Tool 1: Tra cứu bác sĩ ─────────────────────────────────────────────
    {
        "name": "doctor_query",
        "description": (
            "Tra cứu danh sách bác sĩ theo chuyên khoa tại Bệnh viện Vinmec. "
            "Có thể lọc theo ngày cụ thể để kiểm tra lịch làm việc còn trống."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "specialty": {
                    "type": "string",
                    "description": (
                        "Tên chuyên khoa cần tra cứu. "
                        "Các giá trị hợp lệ: 'Tim mạch', 'Nhi', 'Da liễu', 'Nội tổng quát'."
                    ),
                },
                "date": {
                    "type": "string",
                    "description": (
                        "Ngày muốn kiểm tra lịch trống, định dạng 'YYYY-MM-DD' "
                        "(ví dụ: '2026-09-20'). Bỏ qua tham số này để tra cứu tất cả các ngày."
                    ),
                },
            },
            "required": ["specialty"],
        },
    },

    # ── Tool 2: Đặt lịch khám ──────────────────────────────────────────────
    {
        "name": "book_appointment",
        "description": (
            "Đặt lịch khám bệnh tại Bệnh viện Đa khoa Quốc tế Vinmec. "
            "Yêu cầu đủ thông tin bệnh nhân, bác sĩ, chuyên khoa và thời gian."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "patient_id": {
                    "type": "string",
                    "description": "Mã bệnh nhân (ví dụ: 'BN2026042').",
                },
                "doctor_name": {
                    "type": "string",
                    "description": "Tên đầy đủ của bác sĩ (ví dụ: 'BS. Nguyễn Thị Lan').",
                },
                "specialty": {
                    "type": "string",
                    "description": "Chuyên khoa của bác sĩ (ví dụ: 'Nhi', 'Tim mạch').",
                },
                "datetime_str": {
                    "type": "string",
                    "description": "Thời gian hẹn khám, định dạng 'YYYY-MM-DD HH:MM' (ví dụ: '2026-09-20 09:00').",
                },
            },
            "required": ["patient_id", "doctor_name", "specialty", "datetime_str"],
        },
    },
]


# ═══════════════════════════════════════════════════════════════════════════════
# 2. DỮ LIỆU MÔ PHỎNG — Thay thế cho CSDL thực tế trong môi trường Lab
# ═══════════════════════════════════════════════════════════════════════════════

# Danh sách bác sĩ Vinmec, phân theo chuyên khoa.
# Mỗi bác sĩ có: tên, chức danh, lịch trống, kinh nghiệm.
DOCTOR_DATABASE: dict[str, list[dict]] = {
    "Tim mạch": [
        {
            "name": "PGS.TS. Trần Minh Khoa",
            "title": "Phó Giáo sư, Tiến sĩ",
            "available_slots": ["2026-09-20 08:00", "2026-09-20 10:00", "2026-09-21 14:00"],
            "experience": "15 năm kinh nghiệm tim mạch can thiệp",
        },
        {
            "name": "TS. Lê Thị Hương",
            "title": "Tiến sĩ",
            "available_slots": ["2026-09-20 09:00", "2026-09-22 08:00"],
            "experience": "10 năm chuyên về suy tim và rối loạn nhịp",
        },
    ],
    "Nhi": [
        {
            "name": "BS. Nguyễn Thị Lan",
            "title": "Bác sĩ chuyên khoa II",
            "available_slots": ["2026-09-20 09:00", "2026-09-20 11:00", "2026-09-21 09:00"],
            "experience": "12 năm nhi khoa tổng quát và dinh dưỡng trẻ em",
        },
        {
            "name": "ThS. Phạm Văn Đức",
            "title": "Thạc sĩ",
            "available_slots": ["2026-09-21 14:00", "2026-09-23 10:00"],
            "experience": "8 năm nhi khoa và bệnh truyền nhiễm trẻ em",
        },
    ],
    "Da liễu": [
        {
            "name": "PGS.TS. Vũ Thu Hà",
            "title": "Phó Giáo sư, Tiến sĩ",
            "available_slots": ["2026-09-20 13:00", "2026-09-21 08:00"],
            "experience": "18 năm da liễu thẩm mỹ và điều trị mãn tính",
        },
    ],
    "Nội tổng quát": [
        {
            "name": "BS.CKI. Hoàng Văn Nam",
            "title": "Bác sĩ chuyên khoa I",
            "available_slots": ["2026-09-20 08:30", "2026-09-20 10:30", "2026-09-20 14:00"],
            "experience": "9 năm nội khoa và quản lý bệnh mãn tính",
        },
    ],
}

# Danh sách bệnh nhân — dùng để xác thực mã bệnh nhân trước khi đặt lịch.
PATIENT_DATABASE: dict[str, dict] = {
    "BN2026001": {"name": "Nguyễn Văn An",  "dob": "1990-05-15", "phone": "0912345678"},
    "BN2026042": {"name": "Trần Thị Bình",  "dob": "1985-08-22", "phone": "0987654321"},
    "BN2026099": {"name": "Lê Minh Tuấn",   "dob": "2000-12-01", "phone": "0934567890"},
}


# ═══════════════════════════════════════════════════════════════════════════════
# 3. HÀM THỰC THI TOOL — Mỗi hàm tương ứng đúng 1 Tool trong TOOLS_SCHEMA
#    Trả về chuỗi JSON để MCP Server có thể parse và trả về cho Agent.
# ═══════════════════════════════════════════════════════════════════════════════

def _to_json(data: dict) -> str:
    """Chuyển dict sang JSON string, giữ nguyên ký tự Unicode tiếng Việt."""
    return json.dumps(data, ensure_ascii=False)


def _find_specialty_key(specialty: str) -> Optional[str]:
    """
    Tìm tên chuyên khoa trong DOCTOR_DATABASE theo cách khớp không phân biệt hoa thường.
    Trả về key chính xác trong database, hoặc None nếu không tìm thấy.
    """
    specialty_normalized = specialty.strip().lower()
    for key in DOCTOR_DATABASE:
        if specialty_normalized in key.lower() or key.lower() in specialty_normalized:
            return key
    return None


def _filter_doctors_by_date(doctors: list[dict], date: str) -> list[dict]:
    """
    Lọc danh sách bác sĩ, chỉ giữ lại những bác sĩ có lịch trống vào ngày `date`.
    Trả về danh sách mới (không sửa dữ liệu gốc).
    """
    result = []
    for doctor in doctors:
        # Chỉ giữ các slot bắt đầu bằng ngày cần tìm (format: "YYYY-MM-DD")
        matching_slots = [slot for slot in doctor["available_slots"] if slot.startswith(date)]
        if matching_slots:
            # Tạo bản copy với available_slots đã được lọc
            result.append({**doctor, "available_slots": matching_slots})
    return result


def execute_doctor_query(specialty: str, date: Optional[str] = None) -> str:
    """
    Tool 1: Tra cứu bác sĩ theo chuyên khoa, có thể lọc theo ngày.

    Args:
        specialty: Tên chuyên khoa (ví dụ: 'Tim mạch', 'Nhi').
        date     : Ngày lọc lịch, định dạng 'YYYY-MM-DD'. None = tra tất cả ngày.

    Returns:
        JSON string chứa danh sách bác sĩ phù hợp hoặc thông báo lỗi.
    """
    # Bước 1: Tìm chuyên khoa trong database
    specialty_key = _find_specialty_key(specialty)
    if specialty_key is None:
        return _to_json({
            "status": "NOT_FOUND",
            "message": (
                f"Không tìm thấy bác sĩ cho chuyên khoa '{specialty}'. "
                "Các chuyên khoa hiện có: Tim mạch, Nhi, Da liễu, Nội tổng quát."
            ),
        })

    # Bước 2: Lấy danh sách bác sĩ, lọc theo ngày nếu cần
    doctors = DOCTOR_DATABASE[specialty_key]
    if date:
        doctors = _filter_doctors_by_date(doctors, date)
        if not doctors:
            return _to_json({
                "status": "NO_AVAILABILITY",
                "specialty": specialty_key,
                "date": date,
                "message": (
                    f"Không có lịch trống cho chuyên khoa '{specialty_key}' vào ngày {date}. "
                    "Vui lòng chọn ngày khác."
                ),
            })

    # Bước 3: Trả về kết quả thành công
    return _to_json({
        "status": "SUCCESS",
        "specialty": specialty_key,
        "date_filter": date if date else "Tất cả ngày",
        "total_doctors": len(doctors),
        "doctors": doctors,
    })


def execute_book_appointment(
    patient_id: str,
    doctor_name: str,
    specialty: str,
    datetime_str: str,
) -> str:
    """
    Tool 2: Đặt lịch khám bệnh tại Vinmec.

    Args:
        patient_id  : Mã bệnh nhân (ví dụ: 'BN2026042').
        doctor_name : Tên bác sĩ (ví dụ: 'BS. Nguyễn Thị Lan').
        specialty   : Chuyên khoa (ví dụ: 'Nhi').
        datetime_str: Thời gian hẹn khám (ví dụ: '2026-09-20 09:00').

    Returns:
        JSON string xác nhận đặt lịch thành công hoặc thông báo lỗi.
    """
    # Bước 1: Xác thực mã bệnh nhân — không tìm thấy thì từ chối ngay
    normalized_id = patient_id.strip().upper()
    patient = PATIENT_DATABASE.get(normalized_id)
    if patient is None:
        return _to_json({
            "status": "NOT_FOUND",
            "message": (
                f"Không tìm thấy thông tin bệnh nhân có mã '{patient_id}'. "
                "Vui lòng kiểm tra lại mã bệnh nhân."
            ),
        })

    # Bước 2: Tạo mã đặt lịch duy nhất
    booking_id = f"VMC-{normalized_id}-{random.randint(1000, 9999)}"

    # Bước 3: Trả về xác nhận đặt lịch thành công
    return _to_json({
        "status": "SUCCESS",
        "booking_id": booking_id,
        "patient_id": normalized_id,
        "patient_name": patient["name"],
        "doctor": doctor_name,
        "specialty": specialty,
        "appointment_time": datetime_str,
        "hospital": "Bệnh viện Đa khoa Quốc tế Vinmec",
        "message": (
            f"Đặt lịch khám thành công! Mã đặt lịch: {booking_id}. "
            f"Bệnh nhân {patient['name']} có lịch khám với {doctor_name} "
            f"(Chuyên khoa: {specialty}) vào lúc {datetime_str} tại Vinmec. "
            "Vui lòng đến trước 15 phút và mang theo CMND/CCCD."
        ),
    })


# ═══════════════════════════════════════════════════════════════════════════════
# 4. TOOL ROUTER & DISPATCHER — Liên kết tên Tool với hàm thực thi tương ứng
# ═══════════════════════════════════════════════════════════════════════════════

# Ánh xạ: tên tool (string) → hàm execute tương ứng
# Khi thêm Tool mới, chỉ cần đăng ký vào đây — không cần sửa dispatcher.
_TOOL_ROUTER: dict[str, Any] = {
    "doctor_query":    execute_doctor_query,
    "book_appointment": execute_book_appointment,
}


def dispatch_tool_call(tool_name: str, arguments: dict[str, Any]) -> str:
    """
    Điều phối lời gọi Tool từ MCP Server đến hàm execute tương ứng.

    Args:
        tool_name : Tên tool cần gọi (phải khớp với key trong _TOOL_ROUTER).
        arguments : Dict tham số sẽ được unpack và truyền vào hàm execute.

    Returns:
        JSON string là kết quả từ hàm execute, hoặc thông báo lỗi nếu:
          - tool_name không tồn tại → status: UNKNOWN_TOOL
          - hàm execute raise exception → status: EXECUTION_ERROR
    """
    handler = _TOOL_ROUTER.get(tool_name)

    if handler is None:
        return _to_json({
            "status": "UNKNOWN_TOOL",
            "error": f"Tool '{tool_name}' không tồn tại. Các tool hợp lệ: {list(_TOOL_ROUTER.keys())}",
        })

    try:
        return handler(**arguments)
    except TypeError as e:
        # Lỗi khi arguments không khớp với signature của hàm execute
        return _to_json({"status": "EXECUTION_ERROR", "error": f"Tham số không hợp lệ: {e}"})
    except Exception as e:
        return _to_json({"status": "EXECUTION_ERROR", "error": str(e)})
