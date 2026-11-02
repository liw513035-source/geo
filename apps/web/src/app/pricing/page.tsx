"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Plan = {
  code: string;
  name: string;
  price: string;
  discount_amount: string;
  pay_amount: string;
  features: string[];
};

const featureText: Record<string, string> = {
  unlimited_score: "不限评分次数",
  batch: "批量处理（未开放）",
  open_api: "开放 API（未开放）",
  white_label: "白标（未开放）",
};

export default function PricingPage() {
  const [plans, setPlans] = useState<Plan[]>([]);
  const [message, setMessage] = useState("");

  useEffect(() => {
    api<{ items: Plan[] }>("/api/v1/plans").then((data) => setPlans(data.items)).catch(() => setMessage("暂时无法读取计划"));
  }, []);

  async function pay(code: string, provider: "wechat" | "alipay") {
    setMessage("");
    try {
      await api("/api/v1/subscription/checkout", { method: "POST", body: JSON.stringify({ plan_code: code, provider }) });
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : "无法发起支付");
    }
  }

  return (
    <section>
      <h1 className="text-2xl font-semibold">订阅</h1>
      <p className="mt-2 text-sm text-stone-600">人民币月付。一次付款使用一个自然月。注册用户即可导出报告，基础会员解除每日次数限制。</p>
      <div className="mt-6 grid gap-4 md:grid-cols-2">
        {plans.map((plan) => (
          <article key={plan.code} className="rounded-xl bg-white p-5">
            <h2 className="text-xl font-semibold">{plan.name}</h2>
            <p className="mt-2 text-2xl">{plan.discount_amount === "0.00" ? `${plan.price} 元/月` : <span><s className="text-stone-400">{plan.price}</s> {plan.pay_amount} 元/月</span>}</p>
            <ul className="mt-3 space-y-1 text-sm text-stone-600">
              {plan.features.map((feature) => <li key={feature}>{featureText[feature] || feature}</li>)}
            </ul>
            <div className="mt-4 flex gap-2">
              <button className="rounded-lg bg-stone-900 px-3 py-2 text-sm text-white" onClick={() => pay(plan.code, "wechat")}>微信支付</button>
              <button className="rounded-lg border px-3 py-2 text-sm" onClick={() => pay(plan.code, "alipay")}>支付宝</button>
            </div>
          </article>
        ))}
      </div>
      {message && <p className="mt-4 text-sm text-stone-600">{message}</p>}
    </section>
  );
}
