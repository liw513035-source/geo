"use client";

import { useEffect, useState, type ReactNode } from "react";
import Link from "next/link";
import { MarketingHeader } from "@/components/Shell";
import { api } from "@/lib/api";

type Plan = {
  code: string;
  name: string;
  price: string;
  discount_amount: string;
  pay_amount: string;
  features: string[];
};

type Payments = { wechat: boolean; alipay: boolean };

const featureText: Record<string, string> = {
  unlimited_score: "不限次数",
  batch: "批量（未开放）",
  open_api: "API（未开放）",
  white_label: "白标（未开放）",
};

export default function PricingPage() {
  const [plans, setPlans] = useState<Plan[]>([]);
  const [payments, setPayments] = useState<Payments>({ wechat: false, alipay: false });
  const [message, setMessage] = useState("");

  useEffect(() => {
    api<{ items: Plan[]; payments: Payments }>("/api/v1/plans")
      .then((data) => {
        setPlans(data.items);
        setPayments(data.payments);
      })
      .catch(() => setMessage("暂时无法读取计划"));
  }, []);

  async function pay(code: string, provider: "wechat" | "alipay") {
    setMessage("");
    try {
      await api("/api/v1/subscription/checkout", { method: "POST", body: JSON.stringify({ plan_code: code, provider }) });
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : "无法支付");
    }
  }

  const basic = plans.find((plan) => plan.code === "basic");
  const pro = plans.find((plan) => plan.code === "pro");

  return (
    <div className="min-h-screen bg-[#f7f8fb]">
      <MarketingHeader />
      <main className="mx-auto max-w-6xl px-4 py-12">
        <h1 className="text-3xl font-semibold text-[#0b1f44]">定价</h1>
        <p className="mt-2 text-sm text-[#64748b]">按月付费，人民币。</p>
        <div className="mt-8 grid gap-4 lg:grid-cols-3">
          <Card title="免费" price="0" note="每日 3 次" items={["无需注册", "规则评分", "优化建议"]} action={<Link href="/" className="block rounded-lg border border-[#cbd5e1] py-2.5 text-center text-sm font-medium">开始使用</Link>} />
          {basic && <PaidCard plan={basic} popular payments={payments} onPay={pay} />}
          {pro && <PaidCard plan={pro} payments={payments} onPay={pay} />}
        </div>
        {message && <p className="mt-4 text-sm text-[#64748b]">{message}</p>}
      </main>
    </div>
  );
}

function PaidCard({ plan, popular, payments, onPay }: { plan: Plan; popular?: boolean; payments: Payments; onPay: (code: string, provider: "wechat" | "alipay") => void }) {
  const price = plan.discount_amount === "0.00" ? plan.price : plan.pay_amount;
  return (
    <Card
      title={plan.name}
      price={price}
      note={plan.discount_amount === "0.00" ? undefined : `标价 ${plan.price}`}
      popular={popular}
      items={plan.features.map((feature) => featureText[feature] || feature)}
      action={
        <div className="grid grid-cols-2 gap-2">
          <button disabled={!payments.wechat} className="rounded-lg bg-[#2563eb] py-2.5 text-sm text-white disabled:opacity-40" onClick={() => onPay(plan.code, "wechat")}>微信</button>
          <button disabled={!payments.alipay} className="rounded-lg bg-[#2563eb] py-2.5 text-sm text-white disabled:opacity-40" onClick={() => onPay(plan.code, "alipay")}>支付宝</button>
        </div>
      }
    />
  );
}

function Card({ title, price, note, items, action, popular }: { title: string; price: string; note?: string; items: string[]; action: ReactNode; popular?: boolean }) {
  return (
    <article className={`relative rounded-2xl bg-white p-6 shadow-[0_12px_30px_-24px_rgba(15,23,42,0.4)] ${popular ? "border-2 border-[#2563eb]" : "border border-[#e8edf5]"}`}>
      {popular && <span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-[#2563eb] px-3 py-1 text-xs text-white">推荐</span>}
      <h2 className={`text-xl font-semibold ${popular ? "text-[#2563eb]" : "text-[#0b1f44]"}`}>{title}</h2>
      <p className="mt-4 text-4xl font-semibold text-[#0b1f44]">¥{price}<span className="text-base font-normal text-[#94a3b8]"> /月</span></p>
      {note && <p className="mt-1 text-xs text-[#94a3b8]">{note}</p>}
      <div className="mt-5">{action}</div>
      <ul className="mt-5 space-y-2 text-sm text-[#334155]">
        {items.map((item) => <li key={item}>✓ {item}</li>)}
      </ul>
    </article>
  );
}
