from enum import Enum

APP_VERSION = "v1.0.0"

class Platform(str, Enum):

    YOUTUBE_SHORTS = "YOUTUBE_SHORTS"
    TIKTOK = "TIKTOK"
    FACEBOOK_REELS = "FACEBOOK_REELS"
    INSTAGRAM_REELS = "INSTAGRAM_REELS"

def parse_platform(code) -> "Platform | str":
    """Chấp nhận cả mã platform mới do người dùng tự thêm (trả về str thô)."""
    if isinstance(code, Platform):
        return code
    try:
        return Platform(str(code))
    except ValueError:
        return str(code)


def platform_value(platform) -> str:
    return platform.value if hasattr(platform, "value") else str(platform)


class ChannelStatus(str, Enum):
    NOT_SETUP = "NOT_SETUP"      # Chưa có cookies -> Màu Vàng/Cam
    READY = "READY"              # Sẵn sàng 1-click -> Màu Xanh lá
    IN_USE = "IN_USE"            # Đang có người dùng mở -> Màu Xanh dương / Đỏ
    EXPIRED = "EXPIRED"          # Cookies hết hạn -> Cần setup lại

PLATFORM_META = {
    Platform.YOUTUBE_SHORTS: {
        "title": "YouTube",
        "tag": "YouTube",
        "color": "#ef4444",
        "bg_color": "#2a1515",
        "border_color": "#7f1d1d",
        "studio_url": "https://studio.youtube.com",
        "login_url": "https://accounts.google.com/ServiceLogin?service=youtube",
    },
    Platform.TIKTOK: {
        "title": "TikTok",
        "tag": "TikTok",
        "color": "#06b6d4",
        "bg_color": "#112328",
        "border_color": "#155e75",
        "studio_url": "https://www.tiktok.com/creator-center/upload",
        "login_url": "https://www.tiktok.com/login",
    },
    Platform.FACEBOOK_REELS: {
        "title": "Facebook",
        "tag": "Facebook",
        "color": "#3b82f6",
        "bg_color": "#132338",
        "border_color": "#1e40af",
        "studio_url": "https://business.facebook.com/latest/reels_composer",
        "login_url": "https://www.facebook.com/login",
    },
    Platform.INSTAGRAM_REELS: {
        "title": "Instagram",
        "tag": "Instagram",
        "color": "#ec4899",
        "bg_color": "#2b1424",
        "border_color": "#9d174d",
        "studio_url": "https://www.instagram.com",
        "login_url": "https://www.instagram.com/accounts/login",
    },
}

STATUS_META = {
    ChannelStatus.NOT_SETUP: {
        "label": "Chưa Setup",
        "color": "#f59e0b",
        "bg": "#451a03",
        "btn_text": "Setup Đăng nhập",
        "btn_color": "#d97706",
        "btn_hover": "#b45309",
    },
    ChannelStatus.READY: {
        "label": "Sẵn sàng",
        "color": "#10b981",
        "bg": "#064e3b",
        "btn_text": "Mở Studio (1-Click)",
        "btn_color": "#059669",
        "btn_hover": "#047857",
    },
    ChannelStatus.IN_USE: {
        "label": "Đang sử dụng",
        "color": "#38bdf8",
        "bg": "#082f49",
        "btn_text": "Đang mở...",
        "btn_color": "#0284c7",
        "btn_hover": "#0369a1",
    },
    ChannelStatus.EXPIRED: {
        "label": "Hết hạn",
        "color": "#ef4444",
        "bg": "#450a0a",
        "btn_text": "Setup Lại",
        "btn_color": "#dc2626",
        "btn_hover": "#b91c1c",
    },
}
