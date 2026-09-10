class TTSError(RuntimeError):
    """Safe to display; never contains API response bodies or credentials."""
    def __init__(self, message, title="Voice operation failed", availability_status="error"):
        super().__init__(message)
        self.title = title
        self.availability_status = availability_status


def api_error(code):
    messages = {
        401: ("ElevenLabs authentication failed", "API key không hợp lệ hoặc đã hết hiệu lực. Hãy kiểm tra ELEVENLABS_API_KEY.", "unauthorized"),
        402: ("Voice unavailable via API", "Voice này hiện không thể dùng qua ElevenLabs API với tài khoản hoặc gói hiện tại. Hãy chọn voice khác hoặc kiểm tra gói/credits/quyền API.", "payment_required"),
        403: ("Voice permission denied", "Tài khoản/API key hiện không có quyền dùng voice này qua API.", "restricted"),
        429: ("ElevenLabs rate limit", "Đã vượt giới hạn request hoặc quota. Kiểm tra credits; nếu bị giới hạn tốc độ, hãy thử lại sau.", "error"),
    }
    title, message, status = messages.get(code, ("ElevenLabs request failed", f"ElevenLabs từ chối yêu cầu (HTTP {code}). Kiểm tra voice/model và thử lại khi đã xử lý nguyên nhân.", "error"))
    return TTSError(message, title, status)


def connection_error():
    return TTSError("Không thể kết nối ElevenLabs. Kiểm tra Internet và thử lại.", "ElevenLabs connection error")


class TTSCancelled(TTSError):
    pass


def check_cancel(cancel):
    if cancel is not None and cancel.is_set():
        raise TTSCancelled("Voice operation cancelled. Existing text was kept.")
