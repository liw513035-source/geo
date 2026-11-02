"use client";

import { useEffect, useState } from "react";
import { MarketingHeader } from "@/components/Shell";
import { api } from "@/lib/api";

type Model = { id: string; provider: string; model: string; enabled: boolean; priority: number; configured: boolean };
type Plan = { code: string; name: string; price: string; discount_amount: string; pay_amount: string; enabled: boolean };
type Sub = { id: string; email: string; plan_code: string; status: string; current_period_end: string | null; provider: string | null };
type Usage = { day: string; action: string; calls: number; tokens: number };

export default function ConsolePage() {
  const [tab, setTab] = useState("models");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [models, setModels] = useState<Model[]>([]);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [subs, setSubs] = useState<Sub[]>([]);
  const [statusFilter, setStatusFilter] = useState("");
  const [usage, setUsage] = useState<Usage[]>([]);
  const [anonymous, setAnonymous] = useState(3);
  const [registered, setRegistered] = useState(20);
  const [draft, setDraft] = useState({ provider: "deepseek", model: "", apiKey: "", priority: 100 });

  async function load(next = tab, filter = statusFilter) {
    setError("");
    try {
      if (next === "models") {
        const payload = await api<{ items: Model[] }>("/admin/models");
        setModels(payload.items);
      } else if (next === "plans") {
        const payload = await api<{ items: Plan[] }>("/admin/plans");
        setPlans(payload.items);
      } else if (next === "subscriptions") {
        const query = filter ? `?status=${filter}` : "";
        const payload = await api<{ items: Sub[] }>(`/admin/subscriptions${query}`);
        setSubs(payload.items);
      } else if (next === "usage") {
        const payload = await api<{ items: Usage[] }>("/admin/usage");
        setUsage(payload.items);
      } else {
        const payload = await api<{ anonymous_daily_limit: number; registered_daily_limit: number }>("/admin/settings");
        setAnonymous(payload.anonymous_daily_limit);
        setRegistered(payload.registered_daily_limit);
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "无法打开后台");
    }
  }

  useEffect(() => {
    void load("models");
  }, []);

  async function saveModel(item: Model, patch: { enabled?: boolean; priority?: number }) {
    setNotice("");
    await api(`/admin/models/${item.id}`, { method: "PATCH", body: JSON.stringify(patch) });
    setNotice("模型已更新");
    await load("models");
  }

  async function addModel(event: React.FormEvent) {
    event.preventDefault();
    setNotice("");
    await api("/admin/models", {
      method: "POST",
      body: JSON.stringify({
        provider: draft.provider,
        model: draft.model,
        api_key: draft.apiKey,
        priority: draft.priority,
        enabled: true,
      }),
    });
    setDraft({ provider: "deepseek", model: "", apiKey: "", priority: 100 });
    setNotice("模型已添加，密钥不会回显");
    await load("models");
  }

  async function savePlan(plan: Plan) {
    setNotice("");
    await api(`/admin/plans/${plan.code}`, {
      method: "PUT",
      body: JSON.stringify({
        name: plan.name,
        price: plan.price,
        discount_amount: plan.discount_amount,
        enabled: plan.enabled,
      }),
    });
    setNotice("计划已保存");
    await load("plans");
  }

  async function setSubStatus(id: string, status: "active" | "expired") {
    setNotice("");
    await api(`/admin/subscriptions/${id}`, { method: "POST", body: JSON.stringify({ status }) });
    setNotice("订阅状态已更新");
    await load("subscriptions");
  }

  return (
    <div className="min-h-screen bg-[#f7f8fb]">
    <MarketingHeader />
    <section className="mx-auto max-w-5xl px-4 py-8">
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
      {notice && <p className="mt-4 text-sm text-stone-600">{notice}</p>}

      {tab === "models" && (
        <div className="mt-4 space-y-3">
          {models.map((item) => (
            <article key={item.id} className="flex flex-col gap-3 rounded-xl bg-white p-4 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="font-medium">{item.provider} / {item.model}</p>
                <p className="text-sm text-stone-500">{item.configured ? "密钥已配置" : "未配置密钥"}</p>
              </div>
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <label>优先级 <input className="ml-1 w-16 rounded border px-2 py-1" type="number" value={item.priority} onChange={(event) => setModels(models.map((row) => row.id === item.id ? { ...row, priority: Number(event.target.value) } : row))} /></label>
                <button className="rounded border px-2 py-1" onClick={() => saveModel(item, { priority: item.priority })}>保存优先级</button>
                <button className="rounded border px-2 py-1" onClick={() => saveModel(item, { enabled: !item.enabled })}>{item.enabled ? "禁用" : "启用"}</button>
              </div>
            </article>
          ))}
          <form onSubmit={addModel} className="grid gap-2 rounded-xl bg-white p-4 sm:grid-cols-2">
            <input className="rounded border px-2 py-1" placeholder="供应商" value={draft.provider} onChange={(event) => setDraft({ ...draft, provider: event.target.value })} />
            <input className="rounded border px-2 py-1" placeholder="模型名" value={draft.model} onChange={(event) => setDraft({ ...draft, model: event.target.value })} required />
            <input className="rounded border px-2 py-1" placeholder="API Key" type="password" value={draft.apiKey} onChange={(event) => setDraft({ ...draft, apiKey: event.target.value })} required />
            <input className="rounded border px-2 py-1" type="number" value={draft.priority} onChange={(event) => setDraft({ ...draft, priority: Number(event.target.value) })} />
            <button className="rounded bg-stone-900 px-3 py-2 text-sm text-white sm:col-span-2">添加模型</button>
          </form>
        </div>
      )}

      {tab === "plans" && (
        <div className="mt-4 space-y-3">
          {plans.map((plan) => (
            <form key={plan.code} className="grid gap-2 rounded-xl bg-white p-4 sm:grid-cols-4" onSubmit={(event) => { event.preventDefault(); void savePlan(plan); }}>
              <p className="font-medium sm:col-span-4">{plan.name} · {plan.code} · 应付 {plan.pay_amount} 元</p>
              <input className="rounded border px-2 py-1" value={plan.name} onChange={(event) => setPlans(plans.map((row) => row.code === plan.code ? { ...row, name: event.target.value } : row))} />
              <input className="rounded border px-2 py-1" value={plan.price} onChange={(event) => setPlans(plans.map((row) => row.code === plan.code ? { ...row, price: event.target.value } : row))} />
              <input className="rounded border px-2 py-1" value={plan.discount_amount} onChange={(event) => setPlans(plans.map((row) => row.code === plan.code ? { ...row, discount_amount: event.target.value } : row))} />
              <button className="rounded bg-stone-900 px-3 py-2 text-sm text-white">保存</button>
            </form>
          ))}
        </div>
      )}

      {tab === "subscriptions" && (
        <div className="mt-4 space-y-3">
          <select className="rounded border bg-white px-2 py-1 text-sm" value={statusFilter} onChange={(event) => { setStatusFilter(event.target.value); void load("subscriptions", event.target.value); }}>
            <option value="">全部状态</option>
            <option value="active">active</option>
            <option value="canceled">canceled</option>
            <option value="expired">expired</option>
          </select>
          {subs.length === 0 && <p className="text-sm text-stone-500">没有订阅。</p>}
          {subs.map((item) => (
            <article key={item.id} className="rounded-xl bg-white p-4 text-sm">
              <p>{item.email} · {item.plan_code} · {item.status}</p>
              <p className="text-stone-500">{item.current_period_end || "无到期时间"} · {item.provider || "无渠道"}</p>
              <div className="mt-2 flex gap-2">
                <button className="rounded border px-2 py-1" onClick={() => setSubStatus(item.id, "active")}>设为有效</button>
                <button className="rounded border px-2 py-1" onClick={() => setSubStatus(item.id, "expired")}>设为过期</button>
              </div>
            </article>
          ))}
        </div>
      )}

      {tab === "usage" && (
        <table className="mt-4 w-full overflow-hidden rounded-xl bg-white text-left text-sm">
          <thead className="text-stone-500"><tr><th className="p-3">日期</th><th>动作</th><th>次数</th><th>Token</th></tr></thead>
          <tbody>
            {usage.map((item) => (
              <tr key={`${item.day}-${item.action}`} className="border-t"><td className="p-3">{item.day}</td><td>{item.action}</td><td>{item.calls}</td><td>{item.tokens}</td></tr>
            ))}
          </tbody>
        </table>
      )}

      {tab === "settings" && (
        <form onSubmit={async (event) => { event.preventDefault(); await api("/admin/settings", { method: "PUT", body: JSON.stringify({ anonymous_daily_limit: anonymous, registered_daily_limit: registered }) }); setNotice("次数已保存"); }} className="mt-4 space-y-3">
          <label className="block text-sm">匿名每日次数 <input className="ml-2 rounded border px-2 py-1" type="number" value={anonymous} onChange={(event) => setAnonymous(Number(event.target.value))} /></label>
          <label className="block text-sm">注册每日次数 <input className="ml-2 rounded border px-2 py-1" type="number" value={registered} onChange={(event) => setRegistered(Number(event.target.value))} /></label>
          <button className="rounded-lg bg-stone-900 px-3 py-2 text-sm text-white">保存</button>
        </form>
      )}
    </section>
    </div>
  );
}
