from datetime import datetime

from app.billing import add_month, apply_payment
from app.db import connect
from app.security import SHANGHAI


def test_payment_extends_one_month_and_is_idempotent():
    conn = connect()
    try:
        conn.execute("BEGIN")
        user = conn.execute(
            "INSERT INTO t_users (email, password_hash) VALUES (%s, %s) RETURNING id",
            ("pay-test@example.com", "hash"),
        ).fetchone()
        trade = "geo-test-trade"
        conn.execute(
            """
            INSERT INTO t_payments
                (user_id, plan_code, provider, out_trade_no, list_price, discount_amount, pay_amount, currency, status)
            VALUES (%s, 'basic', 'wechat', %s, 9.90, 0, 9.90, 'CNY', 'pending')
            """,
            (user["id"], trade),
        )
        payment = conn.execute("SELECT * FROM t_payments WHERE out_trade_no = %s", (trade,)).fetchone()
        paid_at = datetime(2026, 11, 3, 12, 0, tzinfo=SHANGHAI)
        apply_payment(conn, payment, paid_at)
        apply_payment(conn, payment, paid_at)
        sub = conn.execute("SELECT plan_code, status, current_period_end FROM t_subscriptions WHERE user_id = %s", (user["id"],)).fetchone()
        paid_rows = conn.execute("SELECT count(*) AS n FROM t_payments WHERE out_trade_no = %s AND status = 'paid'", (trade,)).fetchone()
        assert sub["plan_code"] == "basic"
        assert sub["status"] == "active"
        assert sub["current_period_end"] == add_month(paid_at)
        assert paid_rows["n"] == 1
    finally:
        conn.rollback()
        conn.close()
