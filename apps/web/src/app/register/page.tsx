"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { MarketingHeader } from "@/components/Shell";
import { api } from "@/lib/api";

export default function RegisterPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    try {
      await api("/api/v1/auth/register", { method: "POST", body: JSON.stringify({ email, password }) });
      router.push("/account");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "注册失败");
    }
  }

  return (
    <div className="min-h-screen bg-[#f7f8fb]">
      <MarketingHeader />
      <form onSubmit={onSubmit} className="mx-auto mt-16 max-w-md space-y-3 rounded-2xl border border-[#e8edf5] bg-white p-6">
        <h1 className="text-2xl font-semibold text-[#0b1f44]">注册</h1>
        <input className="h-11 w-full rounded-xl border border-[#e2e8f0] px-3" placeholder="邮箱" value={email} onChange={(event) => setEmail(event.target.value)} />
        <input className="h-11 w-full rounded-xl border border-[#e2e8f0] px-3" placeholder="至少 8 位密码" type="password" value={password} onChange={(event) => setPassword(event.target.value)} />
        {error && <p className="text-sm text-rose-600">{error}</p>}
        <button className="h-11 w-full rounded-xl bg-[#2563eb] text-white">注册</button>
      </form>
    </div>
  );
}
