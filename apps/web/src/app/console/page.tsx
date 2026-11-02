"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function ConsolePage() {
  const [tab, setTab] = useState("models");
  const [data, setData] = useState<unknown>(null);
  const [error, setError] = useState("");
  const [anonymous, setAnonymous] = useState(3);
  const [registered, setRegistered] = useState(20);

  async function load(next = tab) {
    setError("");
    const path =
      next === "models" ? "/admin/models" :
      next === "plans" ? "/admin/plans" :
      next === "subscriptions" ? "/admin/subscriptions" :
      next === "usage" ? "/admin/usage" :
      "/admin/settings";
    try {
      const payload = await api<Record<string, unknown>>(path);
      setData(payload);
      if (next === "settings") {
        setAnonymous(Number(payload.anonymous_daily_limit));
        setRegistered(Number(payload.registered_daily_limit));
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "无法打开后台");
    }
  }

  useEffect(() => {
    void load("models");
  }, []);

  async function saveSettings(event: React.FormEvent) {
    event.preventDefault();
    await api("/admin/settings", {
      method: "PUT",
      body: JSON.stringify({ anonymous_daily_limit: anonymous, registered_daily_limit: registered }),
    });
    await load("settings");
  }

  return (
    <section>
      <h1 className="text-2xl font-semibold">管理后台</h1>
      <div className="mt-4 flex flex-wrap gap-2 text-sm">
        {[
          ["models", "模型"],
          ["plans", "计划"],
          ["subscriptions", "订阅"],
          ["usage", "用量"],
          ["settings", "次数"],
        ].map(([id, label]) => (
          <button key={id} className={`rounded-full px-3 py-1 ${tab === id ? "bg-stone-900 text-white" : "bg-white"}`} onClick={() => { setTab(id); void load(id); }}>
            {label}
          </button>
        ))}
      </div>
      {error && <p className="mt-4 text-sm text-red-700">{error}</p>}
      {tab === "settings" ? (
        <form onSubmit={saveSettings} className="mt-4 space-y-3">
          <label className="block text-sm">匿名每日次数 <input className="ml-2 rounded border px-2 py-1" type="number" value={anonymous} onChange={(event) => setAnonymous(Number(event.target.value))} /></label>
          <label className="block text-sm">注册每日次数 <input className="ml-2 rounded border px-2 py-1" type="number" value={registered} onChange={(event) => setRegistered(Number(event.target.value))} /></label>
          <button className="rounded-lg bg-stone-900 px-3 py-2 text-sm text-white">保存</button>
        </form>
      ) : (
        <pre className="mt-4 overflow-auto rounded-xl bg-white p-4 text-xs">{JSON.stringify(data, null, 2)}</pre>
      )}
    </section>
  );
}
