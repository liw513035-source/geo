"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Me = { email: string; role: string; plan: string; quota: { limit: number | null; remaining: number | null; unlimited: boolean } };
type Item = { id: string; url: string; score: number; created_at: string };

export default function AccountPage() {
  const [me, setMe] = useState<Me | null>(null);
  const [items, setItems] = useState<Item[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    api<Me>("/api/v1/me")
      .then(async (profile) => {
        setMe(profile);
        const history = await api<{ items: Item[] }>("/api/v1/scores");
        setItems(history.items);
      })
      .catch((caught) => setError(caught instanceof Error ? caught.message : "请先登录"));
  }, []);

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
        <p className="mt-2 text-sm text-stone-600">{me.email} · {me.plan === "free" ? "注册用户" : me.plan} · {me.quota.unlimited ? "不限次数" : `今日剩余 ${me.quota.remaining} 次`}</p>
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
