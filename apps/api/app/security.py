import hashlib
from datetime import datetime
from zoneinfo import ZoneInfo

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.config import settings

SHANGHAI = ZoneInfo("Asia/Shanghai")


def hash_value(raw: str) -> str:
    payload = f"{settings.geo_master_key}|{raw}".encode()
    return hashlib.sha256(payload).hexdigest()


def day_start() -> datetime:
    now = datetime.now(SHANGHAI)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.geo_master_key, salt="geo-session")


def dump_session(user_id: str) -> str:
    return serializer().dumps({"uid": user_id})


def load_session(token: str | None) -> str | None:
    if not token:
        return None
    try:
        data = serializer().loads(token, max_age=60 * 60 * 24 * 14)
    except (BadSignature, SignatureExpired):
        return None
    uid = data.get("uid") if isinstance(data, dict) else None
    return str(uid) if uid else None
