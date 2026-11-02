"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AppFrame } from "@/components/Shell";
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

  return (
    <AppFrame active="history">
      {error && <p className="text-sm text-rose-600">{error} <Link className="underline" href="/login">登录</Link></p>}
      {!error && !me && <p className="text-sm text-[#64748b]">读取中</p>}
      {me && (
        <section className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h1 className="text-xl font-semibold text-[#0b1f44]">历史记录</h1>
              <p className="mt-1 text-sm text-[#64748b]">{me.email} · {me.quota.unlimited ? "不限次数" : `剩余 ${me.quota.remaining} 次`}</p>
            </div>
            <div className="flex gap-3 text-sm">
              {me.role === "admin" && <Link className="text-[#2563eb]" href="/console">后台</Link>}
              <button className="text-[#64748b]" onClick={logout}>退出</button>
            </div>
          </div>
          {subscription && subscription.plan !== "free" && (
            <p className="text-sm text-[#64748b]">
              {subscription.plan} {subscription.current_period_end ? `· ${subscription.current_period_end}` : ""}
              {!subscription.cancel_at_period_end && <button className="ml-3 text-[#2563eb]" onClick={cancel}>不续费</button>}
            </p>
          )}
          {notice && <p className="text-sm text-[#64748b]">{notice}</p>}
          <ul className="overflow-hidden rounded-2xl border border-[#e8edf5] bg-white">
            {items.length === 0 && <li className="px-4 py-6 text-sm text-[#94a3b8]">暂无记录</li>}
            {items.map((item) => (
              <li key={item.id} className="flex items-center justify-between gap-3 border-t border-[#f1f5f9] px-4 py-3 text-sm first:border-t-0">
                <Link href={`/history/${item.id}`} className="truncate text-[#0f172a]">{safeHost(item.url)}</Link>
                <span className="shrink-0 font-semibold text-[#2563eb]">{item.score}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </AppFrame>
  );
}

function safeHost(raw: string) {
  try {
    return new URL(raw).hostname + new URL(raw).pathname;
  } catch {
    return raw;
  }
}
