from typing import Any, Optional

def success_response(data: Any = None, message: str = "Success", code: int = 200) -> dict:
    return {
        "success": True,
        "data": data,
        "message": message,
        "code": code
    }

def error_response(error: str, detail: Optional[str] = None, code: int = 400) -> dict:
    return {
        "success": False,
        "error": error,
        "detail": detail,
        "code": code
    }
