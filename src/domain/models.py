from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
from src.core.constants import Platform, ChannelStatus

@dataclass
class Account:
    id: str
    display_name: str
    email: str
    recovery_email: Optional[str] = None
    notes: Optional[str] = None
    logo: Optional[str] = None  # dataURL base64 hoặc đường dẫn file logo
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

@dataclass
class Channel:
    id: str
    account_id: str
    platform: Platform
    channel_name: str
    studio_url: str
    login_url: str
    avatar_url: Optional[str] = None
    status: ChannelStatus = ChannelStatus.NOT_SETUP
    account_display_name: Optional[str] = None
    account_email: Optional[str] = None
    pinned: bool = False
    pinned_at: Optional[datetime] = None

@dataclass
class SessionCookie:
    channel_id: str
    cookies_data: List[Dict[str, Any]] = field(default_factory=list)
    in_use_by: Optional[str] = None
    in_use_since: Optional[datetime] = None
    last_heartbeat: Optional[datetime] = None
    last_synced_at: Optional[datetime] = None
    updated_by: Optional[str] = None
    health: Optional[Dict[str, Any]] = None  # {status: alive|dead|unknown, checked_at, detail}


@dataclass
class AccessRequest:
    id: str
    channel_id: str
    requester: str
    message: Optional[str] = None
    status: str = "pending"  # pending | approved | denied | cancelled
    created_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None

@dataclass
class ChannelItemView:
    """View model used by UI cards"""
    channel: Channel
    session: Optional[SessionCookie] = None
    
    @property
    def current_status(self) -> ChannelStatus:
        if self.session and self.session.in_use_by:
            return ChannelStatus.IN_USE
        if self.session and self.session.cookies_data and len(self.session.cookies_data) > 0:
            # Soi cookies kết luận chết -> EXPIRED
            if self.session.health and self.session.health.get("status") == "dead":
                return ChannelStatus.EXPIRED
            return ChannelStatus.READY
        return ChannelStatus.NOT_SETUP

    @property
    def is_locked(self) -> bool:
        return self.session is not None and self.session.in_use_by is not None

    @property
    def locked_by(self) -> Optional[str]:
        return self.session.in_use_by if self.session else None
