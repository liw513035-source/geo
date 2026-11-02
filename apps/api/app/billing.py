import calendar
import secrets
from datetime import datetime
from decimal import Decimal

from app.errors import AppError
from app.security import SHANGHAI


def add_month(moment: datetime) -> datetime:
    month = moment.month + 1
    year = moment.year
    if month == 13:
        month = 1
        year += 1
    day = min(moment.day, calendar.monthrange(year, month)[1])
    return moment.replace(year=year, month=month, day=day)


def payable(price: Decimal, discount: Decimal) -> Decimal:
    amount = (price - discount).quantize(Decimal("0.01"))
    if amount <= 0:
        raise AppError("INVALID_URL", "应付金额必须大于 0")
    return amount


def payment_ready(provider: str, settings) -> bool:
    if provider == "wechat":
        return bool(settings.wechat_mch_id and settings.wechat_app_id and settings.wechat_api_v3_key and settings.wechat_private_key)
    if provider == "alipay":
        return bool(settings.alipay_app_id and settings.alipay_private_key and settings.alipay_public_key)
    return False


def new_trade_no() -> str:
    return "geo" + secrets.token_hex(12)


def apply_payment(conn, payment: dict, paid_at: datetime | None = None) -> None:
    paid_at = paid_at or datetime.now(SHANGHAI)
    existing = conn.execute(
        "SELECT status FROM t_payments WHERE out_trade_no = %s FOR UPDATE",
        (payment["out_trade_no"],),
    ).fetchone()
    if existing and existing["status"] == "paid":
        return
    conn.execute(
        """
        UPDATE t_payments
        SET status = 'paid', paid_at = %s, provider_trade_no = COALESCE(%s, provider_trade_no)
        WHERE out_trade_no = %s
        """,
        (paid_at, payment.get("provider_trade_no"), payment["out_trade_no"]),
    )
    current = conn.execute(
        """
        SELECT id, plan_code, status, current_period_end
        FROM t_subscriptions
        WHERE user_id = %s AND status = 'active'
        ORDER BY current_period_end DESC NULLS LAST
        LIMIT 1
        FOR UPDATE
        """,
        (payment["user_id"],),
    ).fetchone()
    if current and current["current_period_end"] and current["current_period_end"] > paid_at and current["plan_code"] == payment["plan_code"]:
        period_end = add_month(current["current_period_end"])
        conn.execute(
            """
            UPDATE t_subscriptions
            SET current_period_end = %s, provider = %s, provider_subscription_id = %s, cancel_at_period_end = FALSE
            WHERE id = %s
            """,
            (period_end, payment["provider"], payment["out_trade_no"], current["id"]),
        )
        return
    period_end = add_month(paid_at)
    if current:
        conn.execute(
            """
            UPDATE t_subscriptions
            SET plan_code = %s, status = 'active', current_period_end = %s,
                provider = %s, provider_subscription_id = %s, cancel_at_period_end = FALSE
            WHERE id = %s
            """,
            (payment["plan_code"], period_end, payment["provider"], payment["out_trade_no"], current["id"]),
        )
        return
    conn.execute(
        """
        INSERT INTO t_subscriptions
            (user_id, plan_code, status, current_period_end, provider, provider_subscription_id, cancel_at_period_end)
        VALUES (%s, %s, 'active', %s, %s, %s, FALSE)
        """,
        (payment["user_id"], payment["plan_code"], period_end, payment["provider"], payment["out_trade_no"]),
    )


def refresh_subscription(conn, user_id):
    row = conn.execute(
        """
        SELECT id, plan_code, status, current_period_end, cancel_at_period_end, provider
        FROM t_subscriptions
        WHERE user_id = %s AND status = 'active'
        ORDER BY current_period_end DESC NULLS LAST
        LIMIT 1
        """,
        (user_id,),
    ).fetchone()
    if not row:
        return None
    end = row["current_period_end"]
    now = datetime.now(SHANGHAI)
    if end is not None and end <= now:
        status = "canceled" if row["cancel_at_period_end"] else "expired"
        conn.execute("UPDATE t_subscriptions SET status = %s WHERE id = %s", (status, row["id"]))
        return None
    return row
