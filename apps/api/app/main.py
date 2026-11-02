import json
import logging
import time
import uuid
from decimal import Decimal

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from psycopg.types.json import Json
from pydantic import BaseModel

from app.billing import payment_ready, refresh_subscription
from app.config import settings
from app.db import connection
from app.errors import AppError
from app.export_report import to_markdown, to_pdf
from app.extract import parse_html
from app.fetch import fetch
from app.score import public_issues, score_document
from app.security import SHANGHAI, day_start, dump_session, hash_value, load_session
from app.suggest import encrypt_secret, generate, public_suggestions

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("vertigeo")

app = FastAPI(title="VertiGEO")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:3000", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class UrlBody(BaseModel):
    url: str
    device_id: str | None = None


class AuthBody(BaseModel):
    email: str
    password: str


class CheckoutBody(BaseModel):
    plan_code: str
    provider: str


class PlanBody(BaseModel):
    code: str
    name: str
    price: Decimal
    discount_amount: Decimal = Decimal("0")
    features: list[str] = []
    enabled: bool = True


class PlanPatch(BaseModel):
    name: str | None = None
    price: Decimal | None = None
    discount_amount: Decimal | None = None
    enabled: bool | None = None


class ModelBody(BaseModel):
    provider: str
    model: str
    api_key: str
    enabled: bool = True
    priority: int = 100


class ModelPatch(BaseModel):
    enabled: bool | None = None
    priority: int | None = None
    api_key: str | None = None


class StatusBody(BaseModel):
    status: str


class SettingsBody(BaseModel):
    anonymous_daily_limit: int | None = None
    registered_daily_limit: int | None = None


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = uuid.uuid4().hex
    request.state.request_id = request_id
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(json.dumps({"request_id": request_id, "path": request.url.path, "event": "unhandled"}))
        response = JSONResponse(
            status_code=500,
            content={"code": "INTERNAL", "message": "服务暂时不可用", "request_id": request_id},
        )
    elapsed = round((time.perf_counter() - started) * 1000)
    host = request.url.hostname or ""
    logger.info(json.dumps({"request_id": request_id, "path": request.url.path, "host": host, "elapsed_ms": elapsed, "status": response.status_code}))
    response.headers["X-Request-Id"] = request_id
    return response


@app.exception_handler(AppError)
async def app_error(_request: Request, exc: AppError):
    request_id = getattr(_request.state, "request_id", "")
    return JSONResponse(status_code=exc.status, content={"code": exc.code, "message": exc.message, "request_id": request_id})


def _error_id(request: Request) -> str:
    return getattr(request.state, "request_id", "")


@app.get("/api/v1/health")
def health():
    with connection() as conn:
        row = conn.execute("SELECT current_schema() AS schema").fetchone()
    return {"status": "ok", "database": "up", "schema": row["schema"]}


@app.post("/api/v1/score")
def score(body: UrlBody, request: Request):
    ip = request.client.host if request.client else ""
    ip_hash = hash_value(ip)
    device_hash = hash_value(body.device_id) if body.device_id else None
    with connection() as conn:
        user = _user(conn, request)
        if user is None and not body.device_id:
            raise AppError("DEVICE_REQUIRED", "缺少设备标识")
        _ensure_quota(conn, user, ip_hash, device_hash)
    fetched = fetch(body.url.strip())
    document = parse_html(fetched.html, status_code=fetched.status, truncated=fetched.truncated)
    scored = score_document(document)
    with connection() as conn:
        configs = conn.execute(
            "SELECT provider, model, api_key_encrypted, enabled, priority FROM t_model_configs WHERE enabled = TRUE ORDER BY priority"
        ).fetchall()
    suggestions, usage = generate(document, scored, configs, fetched.url)
    with connection() as conn:
        user = _user(conn, request)
        _ensure_quota(conn, user, ip_hash, device_hash, lock=True)
        row = conn.execute(
            """
            INSERT INTO t_scores (url, score, dimensions, issues, suggestions, schema_json, user_id, ip_hash, device_hash)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, created_at
            """,
            (
                fetched.url,
                scored.score,
                Json(scored.dimensions),
                Json(scored.issues),
                json.dumps(suggestions, ensure_ascii=False),
                Json(scored.schema_json),
                user["id"] if user else None,
                ip_hash,
                device_hash,
            ),
        ).fetchone()
        conn.execute(
            "INSERT INTO t_usage_logs (user_id, action, model, tokens) VALUES (%s, 'score', NULL, NULL)",
            (user["id"] if user else None,),
        )
        if usage:
            conn.execute(
                "INSERT INTO t_usage_logs (user_id, action, model, tokens) VALUES (%s, 'generate', %s, %s)",
                (user["id"] if user else None, usage["model"], usage["tokens"]),
            )
        quota = _quota_view(conn, user, ip_hash, device_hash)
    return {
        "id": str(row["id"]),
        "url": fetched.url,
        "page_type": scored.page_type,
        "score": scored.score,
        "dimensions": scored.dimensions,
        "window": scored.window,
        "issues": public_issues(scored.issues),
        "schema_json": scored.schema_json,
        "suggestions": public_suggestions(suggestions),
        "quota": quota,
        "created_at": row["created_at"].isoformat(),
    }


@app.get("/api/v1/quota")
def quota(request: Request, device_id: str | None = None):
    ip = request.client.host if request.client else ""
    with connection() as conn:
        user = _user(conn, request)
        device_hash = hash_value(device_id) if device_id else None
        return _quota_view(conn, user, hash_value(ip), device_hash)


@app.post("/api/v1/auth/register")
def register(body: AuthBody):
    from argon2 import PasswordHasher
    from argon2.exceptions import HashingError

    email = body.email.strip().lower()
    if "@" not in email or len(body.password) < 8:
        raise AppError("INVALID_URL", "邮箱或密码不符合要求")
    try:
        password_hash = PasswordHasher().hash(body.password)
    except HashingError as exc:
        raise AppError("INTERNAL", "服务暂时不可用", 500) from exc
    with connection() as conn:
        admin_email = _setting(conn, "admin_email", "")
        if isinstance(admin_email, str):
            admin_email = admin_email.strip().lower()
        role = "admin" if email == admin_email else "user"
        try:
            row = conn.execute(
                "INSERT INTO t_users (email, password_hash, role) VALUES (%s, %s, %s) RETURNING id, email, role",
                (email, password_hash, role),
            ).fetchone()
        except Exception as exc:
            if getattr(exc, "sqlstate", "") == "23505":
                raise AppError("INVALID_URL", "该邮箱已注册") from exc
            raise
    response = JSONResponse({"email": row["email"], "role": row["role"]})
    response.set_cookie("geo_session", dump_session(str(row["id"])), httponly=True, samesite="lax", max_age=1209600, path="/")
    return response


@app.post("/api/v1/auth/login")
def login(body: AuthBody):
    from argon2 import PasswordHasher
    from argon2.exceptions import VerifyMismatchError

    email = body.email.strip().lower()
    with connection() as conn:
        row = conn.execute("SELECT id, email, role, password_hash FROM t_users WHERE lower(email) = %s", (email,)).fetchone()
        if not row:
            raise AppError("UNAUTHENTICATED", "邮箱或密码不正确", 401)
        try:
            PasswordHasher().verify(row["password_hash"], body.password)
        except VerifyMismatchError as exc:
            raise AppError("UNAUTHENTICATED", "邮箱或密码不正确", 401) from exc
        conn.execute("UPDATE t_users SET last_login = now() WHERE id = %s", (row["id"],))
    response = JSONResponse({"email": row["email"], "role": row["role"]})
    response.set_cookie("geo_session", dump_session(str(row["id"])), httponly=True, samesite="lax", max_age=1209600, path="/")
    return response


@app.post("/api/v1/auth/logout")
def logout():
    response = JSONResponse({"ok": True})
    response.delete_cookie("geo_session", path="/")
    return response


@app.get("/api/v1/me")
def me(request: Request):
    ip = request.client.host if request.client else ""
    with connection() as conn:
        user = _require_user(conn, request)
        sub = refresh_subscription(conn, user["id"])
        return {
            "email": user["email"],
            "role": user["role"],
            "plan": sub["plan_code"] if sub else "free",
            "quota": _quota_view(conn, user, hash_value(ip), None),
        }


@app.get("/api/v1/scores")
def list_scores(request: Request):
    with connection() as conn:
        user = _require_user(conn, request)
        rows = conn.execute(
            "SELECT id, url, score, created_at FROM t_scores WHERE user_id = %s ORDER BY created_at DESC LIMIT 50",
            (user["id"],),
        ).fetchall()
    return {"items": [_score_brief(row) for row in rows]}


@app.get("/api/v1/scores/{score_id}")
def get_score(score_id: str, request: Request):
    with connection() as conn:
        user = _require_user(conn, request)
        row = _owned_score(conn, user["id"], score_id)
    return _score_detail(row)


@app.get("/api/v1/scores/{score_id}/export.md")
def export_md(score_id: str, request: Request):
    row = _load_owned(score_id, request)
    return Response(to_markdown(row), media_type="text/markdown; charset=utf-8")


@app.get("/api/v1/scores/{score_id}/export.pdf")
def export_pdf(score_id: str, request: Request):
    row = _load_owned(score_id, request)
    return Response(to_pdf(to_markdown(row)), media_type="application/pdf")


@app.get("/api/v1/plans")
def plans():
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT code, name, price, discount_amount, currency, billing_interval, features
            FROM t_plans WHERE enabled = TRUE ORDER BY price
            """
        ).fetchall()
    return {"items": [_plan_view(row) for row in rows]}


@app.get("/api/v1/subscription")
def subscription(request: Request):
    with connection() as conn:
        user = _require_user(conn, request)
        sub = refresh_subscription(conn, user["id"])
        if not sub:
            return {"plan": "free", "status": "free", "current_period_end": None}
        return {
            "plan": sub["plan_code"],
            "status": sub["status"],
            "current_period_end": sub["current_period_end"].isoformat() if sub["current_period_end"] else None,
            "cancel_at_period_end": sub["cancel_at_period_end"],
        }


@app.post("/api/v1/subscription/checkout")
def checkout(body: CheckoutBody, request: Request):
    if body.provider not in {"wechat", "alipay"}:
        raise AppError("INVALID_URL", "支付方式只支持微信或支付宝")
    if not payment_ready(body.provider, settings):
        raise AppError("PAYMENT_DISABLED", "该支付方式尚未配置", 503)
    with connection() as conn:
        _require_user(conn, request)
        plan = conn.execute("SELECT code FROM t_plans WHERE code = %s AND enabled = TRUE", (body.plan_code,)).fetchone()
        if not plan:
            raise AppError("NOT_FOUND", "找不到该计划", 404)
    raise AppError("PAYMENT_DISABLED", "支付渠道暂时不可用", 503)


@app.post("/api/v1/subscription/cancel")
def cancel(request: Request):
    with connection() as conn:
        user = _require_user(conn, request)
        row = conn.execute(
            """
            UPDATE t_subscriptions SET cancel_at_period_end = TRUE
            WHERE user_id = %s AND status = 'active'
            RETURNING current_period_end
            """,
            (user["id"],),
        ).fetchone()
        if not row:
            raise AppError("NOT_FOUND", "没有可取消的订阅", 404)
    return {"cancel_at_period_end": True, "current_period_end": row["current_period_end"].isoformat()}


@app.post("/api/v1/webhook/wechat")
def wechat_webhook():
    if not payment_ready("wechat", settings):
        raise AppError("PAYMENT_DISABLED", "微信支付尚未配置", 503)
    raise AppError("PAYMENT_DISABLED", "无法校验微信支付通知", 400)


@app.post("/api/v1/webhook/alipay")
def alipay_webhook():
    if not payment_ready("alipay", settings):
        raise AppError("PAYMENT_DISABLED", "支付宝尚未配置", 503)
    raise AppError("PAYMENT_DISABLED", "无法校验支付宝通知", 400)


@app.get("/admin/models")
def admin_models(request: Request):
    with connection() as conn:
        _require_admin(conn, request)
        rows = conn.execute(
            "SELECT id, provider, model, enabled, priority, created_at, api_key_encrypted FROM t_model_configs ORDER BY priority"
        ).fetchall()
    return {
        "items": [
            {
                "id": str(row["id"]),
                "provider": row["provider"],
                "model": row["model"],
                "enabled": row["enabled"],
                "priority": row["priority"],
                "configured": bool(row["api_key_encrypted"]),
            }
            for row in rows
        ]
    }


@app.post("/admin/models")
def admin_create_model(body: ModelBody, request: Request):
    with connection() as conn:
        _require_admin(conn, request)
        row = conn.execute(
            """
            INSERT INTO t_model_configs (provider, model, api_key_encrypted, enabled, priority)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
            """,
            (body.provider, body.model, encrypt_secret(body.api_key), body.enabled, body.priority),
        ).fetchone()
    return {"id": str(row["id"]), "configured": True}


@app.patch("/admin/models/{model_id}")
def admin_patch_model(model_id: str, body: ModelPatch, request: Request):
    with connection() as conn:
        _require_admin(conn, request)
        current = conn.execute("SELECT * FROM t_model_configs WHERE id = %s", (model_id,)).fetchone()
        if not current:
            raise AppError("NOT_FOUND", "找不到模型配置", 404)
        enabled = current["enabled"] if body.enabled is None else body.enabled
        priority = current["priority"] if body.priority is None else body.priority
        secret = current["api_key_encrypted"] if not body.api_key else encrypt_secret(body.api_key)
        conn.execute(
            "UPDATE t_model_configs SET enabled = %s, priority = %s, api_key_encrypted = %s WHERE id = %s",
            (enabled, priority, secret, model_id),
        )
    return {"ok": True, "configured": True}


@app.get("/admin/usage")
def admin_usage(request: Request):
    with connection() as conn:
        _require_admin(conn, request)
        rows = conn.execute(
            """
            SELECT (created_at AT TIME ZONE 'Asia/Shanghai')::date AS day, action, count(*) AS calls, COALESCE(sum(tokens), 0) AS tokens
            FROM t_usage_logs
            GROUP BY 1, 2
            ORDER BY 1 DESC, 2
            LIMIT 60
            """
        ).fetchall()
    return {"items": [{"day": str(row["day"]), "action": row["action"], "calls": row["calls"], "tokens": int(row["tokens"])} for row in rows]}


@app.get("/admin/plans")
def admin_plans(request: Request):
    with connection() as conn:
        _require_admin(conn, request)
        rows = conn.execute("SELECT * FROM t_plans ORDER BY price").fetchall()
    return {"items": [_plan_view(row) | {"enabled": row["enabled"]} for row in rows]}


@app.post("/admin/plans")
def admin_update_plan(body: PlanBody, request: Request):
    patch = PlanPatch(name=body.name, price=body.price, discount_amount=body.discount_amount, enabled=body.enabled)
    return admin_put_plan(body.code, patch, request)


@app.put("/admin/plans/{code}")
def admin_put_plan(code: str, body: PlanPatch, request: Request):
    with connection() as conn:
        _require_admin(conn, request)
        plan = conn.execute("SELECT * FROM t_plans WHERE code = %s", (code,)).fetchone()
        if not plan:
            raise AppError("NOT_FOUND", "找不到该计划", 404)
        price = plan["price"] if body.price is None else body.price
        discount = plan["discount_amount"] if body.discount_amount is None else body.discount_amount
        if discount < 0 or discount >= price:
            raise AppError("INVALID_URL", "减免金额必须大于等于 0 且小于标价")
        name = body.name or plan["name"]
        enabled = plan["enabled"] if body.enabled is None else body.enabled
        conn.execute(
            "UPDATE t_plans SET name = %s, price = %s, discount_amount = %s, enabled = %s WHERE code = %s",
            (name, price, discount, enabled, code),
        )
    return {"ok": True}


@app.get("/admin/subscriptions")
def admin_subscriptions(request: Request, status: str | None = None):
    with connection() as conn:
        _require_admin(conn, request)
        if status:
            rows = conn.execute(
                """
                SELECT s.id, u.email, s.plan_code, s.status, s.current_period_end, s.provider
                FROM t_subscriptions s JOIN t_users u ON u.id = s.user_id
                WHERE s.status = %s
                ORDER BY s.created_at DESC LIMIT 100
                """,
                (status,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT s.id, u.email, s.plan_code, s.status, s.current_period_end, s.provider
                FROM t_subscriptions s JOIN t_users u ON u.id = s.user_id
                ORDER BY s.created_at DESC LIMIT 100
                """
            ).fetchall()
    return {
        "items": [
            {
                "id": str(row["id"]),
                "email": row["email"],
                "plan_code": row["plan_code"],
                "status": row["status"],
                "current_period_end": row["current_period_end"].isoformat() if row["current_period_end"] else None,
                "provider": row["provider"],
            }
            for row in rows
        ]
    }


@app.post("/admin/subscriptions/{subscription_id}")
def admin_subscription_status(subscription_id: str, body: StatusBody, request: Request):
    if body.status not in {"active", "expired"}:
        raise AppError("INVALID_URL", "状态只能改为 active 或 expired")
    with connection() as conn:
        admin = _require_admin(conn, request)
        row = conn.execute(
            "UPDATE t_subscriptions SET status = %s WHERE id = %s RETURNING id",
            (body.status, subscription_id),
        ).fetchone()
        if not row:
            raise AppError("NOT_FOUND", "找不到订阅", 404)
    logger.info(json.dumps({"event": "admin_subscription", "admin": str(admin["id"]), "subscription": subscription_id, "status": body.status}))
    return {"ok": True}


@app.get("/admin/settings")
def admin_get_settings(request: Request):
    with connection() as conn:
        _require_admin(conn, request)
        return {
            "anonymous_daily_limit": int(_setting(conn, "anonymous_daily_limit", 3)),
            "registered_daily_limit": int(_setting(conn, "registered_daily_limit", 20)),
        }


@app.put("/admin/settings")
def admin_put_settings(body: SettingsBody, request: Request):
    with connection() as conn:
        _require_admin(conn, request)
        for key, value in (
            ("anonymous_daily_limit", body.anonymous_daily_limit),
            ("registered_daily_limit", body.registered_daily_limit),
        ):
            if value is None:
                continue
            if value < 0:
                raise AppError("INVALID_URL", "次数不能为负数")
            conn.execute(
                """
                INSERT INTO t_settings (key, value, updated_at) VALUES (%s, %s::jsonb, now())
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = now()
                """,
                (key, json.dumps(value)),
            )
    return {"ok": True}


def _user(conn, request: Request):
    uid = load_session(request.cookies.get("geo_session"))
    if not uid:
        return None
    return conn.execute("SELECT id, email, role FROM t_users WHERE id = %s", (uid,)).fetchone()


def _require_user(conn, request: Request):
    user = _user(conn, request)
    if not user:
        raise AppError("UNAUTHENTICATED", "请先登录", 401)
    return user


def _require_admin(conn, request: Request):
    user = _require_user(conn, request)
    if user["role"] != "admin":
        raise AppError("UNAUTHENTICATED", "需要管理员权限", 403)
    return user


def _setting(conn, key: str, default):
    row = conn.execute("SELECT value FROM t_settings WHERE key = %s", (key,)).fetchone()
    if not row:
        return default
    return row["value"]


def _ensure_quota(conn, user, ip_hash: str, device_hash: str | None, lock: bool = False):
    if user:
        if lock:
            conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (str(user["id"]),))
        sub = refresh_subscription(conn, user["id"])
        if sub:
            return
        limit = int(_setting(conn, "registered_daily_limit", 20))
        count = _count(conn, "user_id = %s", (user["id"],))
        if count >= limit:
            raise AppError("QUOTA_EXCEEDED", "今日评分次数已用完", 429)
        return
    if lock:
        conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (ip_hash,))
    limit = int(_setting(conn, "anonymous_daily_limit", 3))
    ip_count = _count(conn, "user_id IS NULL AND ip_hash = %s", (ip_hash,))
    device_count = _count(conn, "user_id IS NULL AND device_hash = %s", (device_hash,)) if device_hash else 0
    if ip_count >= limit or device_count >= limit:
        raise AppError("QUOTA_EXCEEDED", "今日免费次数已用完，请注册后继续", 429)


def _count(conn, clause: str, params: tuple) -> int:
    row = conn.execute(
        f"SELECT count(*) AS n FROM t_scores WHERE {clause} AND created_at >= %s",
        (*params, day_start()),
    ).fetchone()
    return int(row["n"])


def _quota_view(conn, user, ip_hash: str, device_hash: str | None) -> dict:
    if user:
        sub = refresh_subscription(conn, user["id"])
        if sub:
            return {"limit": None, "remaining": None, "unlimited": True}
        limit = int(_setting(conn, "registered_daily_limit", 20))
        used = _count(conn, "user_id = %s", (user["id"],))
        return {"limit": limit, "remaining": max(0, limit - used), "unlimited": False}
    limit = int(_setting(conn, "anonymous_daily_limit", 3))
    ip_count = _count(conn, "user_id IS NULL AND ip_hash = %s", (ip_hash,))
    device_count = _count(conn, "user_id IS NULL AND device_hash = %s", (device_hash,)) if device_hash else 0
    used = max(ip_count, device_count)
    return {"limit": limit, "remaining": max(0, limit - used), "unlimited": False}


def _owned_score(conn, user_id, score_id: str):
    row = conn.execute("SELECT * FROM t_scores WHERE id = %s AND user_id = %s", (score_id, user_id)).fetchone()
    if not row:
        raise AppError("NOT_FOUND", "找不到评分记录", 404)
    return row


def _load_owned(score_id: str, request: Request):
    with connection() as conn:
        user = _require_user(conn, request)
        return _owned_score(conn, user["id"], score_id)


def _score_brief(row: dict) -> dict:
    return {"id": str(row["id"]), "url": row["url"], "score": row["score"], "created_at": row["created_at"].isoformat()}


def _score_detail(row: dict) -> dict:
    suggestions = json.loads(row["suggestions"]) if isinstance(row["suggestions"], str) else row["suggestions"]
    window = next((item for item in row["issues"] if item.get("id") == "WIN-30"), None)
    return {
        "id": str(row["id"]),
        "url": row["url"],
        "score": row["score"],
        "dimensions": row["dimensions"],
        "issues": public_issues(row["issues"]),
        "schema_json": row["schema_json"],
        "suggestions": public_suggestions(suggestions or _empty_suggestions()),
        "window": {"excerpt": window.get("evidence") if window else "", "has_name": None, "has_price": None, "has_spec": None, "has_quotable_sentence": None},
        "created_at": row["created_at"].isoformat(),
    }


def _empty_suggestions() -> dict:
    return {"status": "unavailable", "description": "", "faq": [], "question_titles": []}


def _plan_view(row: dict) -> dict:
    price = Decimal(row["price"])
    discount = Decimal(row["discount_amount"])
    return {
        "code": row["code"],
        "name": row["name"],
        "price": f"{price:.2f}",
        "discount_amount": f"{discount:.2f}",
        "pay_amount": f"{(price - discount):.2f}",
        "currency": row["currency"].strip() if isinstance(row["currency"], str) else row["currency"],
        "billing_interval": row["billing_interval"],
        "features": row["features"],
    }
