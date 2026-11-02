"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    try {
      await api("/api/v1/auth/login", { method: "POST", body: JSON.stringify({ email, password }) });
      router.push("/account");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "登录失败");
    }
  }

  return (
    <form onSubmit={onSubmit} className="mx-auto max-w-sm space-y-3">
      <h1 className="text-2xl font-semibold">登录</h1>
      <input className="w-full rounded-lg border bg-white px-3 py-2" placeholder="邮箱" value={email} onChange={(event) => setEmail(event.target.value)} />
      <input className="w-full rounded-lg border bg-white px-3 py-2" placeholder="密码" type="password" value={password} onChange={(event) => setPassword(event.target.value)} />
      {error && <p className="text-sm text-red-700">{error}</p>}
      <button className="rounded-lg bg-stone-900 px-4 py-2 text-white">登录</button>
      <p className="text-sm"><Link href="/register" className="underline">注册</Link></p>
    </form>
  );
}
