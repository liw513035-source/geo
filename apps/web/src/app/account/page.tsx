"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Me = { email: string; role: string; plan: string; quota: { limit: number | null; remaining: number | null; unlimited: boolean } };
type Item = { id: string; url: string; score: number; created_at: string };
type Subscription = { plan: string; status: string; current_period_end: string | null; cancel_at_period_end?: boolean };

export default function AccountPage() {
  const [me, setMe] = useState<Me | null>(null);
  const [items, setItems] = useState<Item[]>([]);
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    api<Me>("/api/v1/me")
      .then(async (profile) => {
        setMe(profile);
        const [history, current] = await Promise.all([
          api<{ items: Item[] }>("/api/v1/scores"),
          api<Subscription>("/api/v1/subscription"),
        ]);
        setItems(history.items);
        setSubscription(current);
      })
      .catch((caught) => setError(caught instanceof Error ? caught.message : "请先登录"));
  }, []);

  async function cancel() {
    const result = await api<{ cancel_at_period_end: boolean; current_period_end: string }>("/api/v1/subscription/cancel", { method: "POST" });
    setSubscription((current) => current ? { ...current, cancel_at_period_end: result.cancel_at_period_end, current_period_end: result.current_period_end } : current);
    setNotice("本期结束后不再续费，当前自然月仍有效。");
  }

  async function logout() {
    await api("/api/v1/auth/logout", { method: "POST" });
    location.href = "/";
  }

  if (error) return <p>{error}。<Link className="underline" href="/login">去登录</Link></p>;
  if (!me) return <p>正在读取账号</p>;
  return (
    <section className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">会员中心</h1>
        <p className="mt-2 text-sm text-stone-600">{me.email} · {subscription?.plan === "free" || !subscription ? "注册用户" : subscription.plan} · {me.quota.unlimited ? "不限次数" : `今日剩余 ${me.quota.remaining} 次`}</p>
        {subscription?.current_period_end && <p className="mt-1 text-sm text-stone-500">有效期至 {subscription.current_period_end}</p>}
        {subscription && subscription.plan !== "free" && !subscription.cancel_at_period_end && (
          <button className="mt-2 text-sm underline" onClick={cancel}>到期后不续费</button>
        )}
        {notice && <p className="mt-2 text-sm text-stone-600">{notice}</p>}
        <div className="mt-3 flex gap-3 text-sm">
          <Link className="underline" href="/pricing">升级</Link>
          {me.role === "admin" && <Link className="underline" href="/console">管理后台</Link>}
          <button className="underline" onClick={logout}>退出</button>
        </div>
      </div>
      <ul className="space-y-2">
        {items.length === 0 && <li className="text-sm text-stone-500">还没有历史记录。</li>}
        {items.map((item) => (
          <li key={item.id} className="rounded-lg bg-white px-3 py-2 text-sm">
            <Link href={`/history/${item.id}`} className="font-medium">{item.score} 分</Link>
            <span className="ml-2 break-all text-stone-500">{item.url}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
