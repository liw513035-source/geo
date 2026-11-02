"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { MarketingHeader } from "@/components/Shell";
import { api, deviceId, type Score } from "@/lib/api";

export default function HomePage() {
  const router = useRouter();
  const [url, setUrl] = useState("");
  const [quota, setQuota] = useState<{ remaining: number | null; limit: number | null; unlimited: boolean } | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api<{ remaining: number | null; limit: number | null; unlimited: boolean }>(`/api/v1/quota?device_id=${deviceId()}`)
      .then(setQuota)
      .catch(() => setQuota(null));
  }, []);

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      const result = await api<Score>("/api/v1/score", {
        method: "POST",
        body: JSON.stringify({ url, device_id: deviceId() }),
      });
      sessionStorage.setItem("vertigeo-last-score", JSON.stringify(result));
      router.push("/result");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "评分失败");
      setLoading(false);
    }
  }

  const quotaText = !quota ? "—" : quota.unlimited ? "不限" : `${quota.remaining} / ${quota.limit}`;

  return (
    <div className="min-h-screen bg-[#f7f8fb]">
      <MarketingHeader />
      <main className="mx-auto max-w-3xl px-4 pb-16 pt-16 text-center">
        <h1 className="text-4xl font-semibold tracking-tight text-[#0b1f44] sm:text-5xl">电商 GEO 评分工具</h1>
        <p className="mt-4 text-[#64748b]">分析商品页与店铺质量，获取 GEO 评分与优化建议</p>
        <form onSubmit={onSubmit} className="mx-auto mt-10 max-w-2xl rounded-2xl border border-[#e8edf5] bg-white p-5 text-left shadow-[0_10px_30px_-24px_rgba(15,23,42,0.35)]">
          <p className="mb-3 flex items-center gap-2 text-sm font-medium text-[#2563eb]">商品页或店铺 URL</p>
          <div className="flex flex-col gap-3 sm:flex-row">
            <input value={url} onChange={(event) => setUrl(event.target.value)} required placeholder="粘贴商品页或店铺 URL..." className="h-12 flex-1 rounded-xl border border-[#e2e8f0] px-4 outline-none focus:border-[#2563eb]" />
            <button disabled={loading} className="h-12 rounded-xl bg-[#2563eb] px-5 font-medium text-white disabled:opacity-60">
              {loading ? "评分中" : "开始评分 →"}
            </button>
          </div>
        </form>
        <p className="mt-6 text-sm text-[#64748b]">今日剩余次数：<span className="font-semibold text-[#2563eb]">{quotaText}</span></p>
        {error && <p className="mt-3 text-sm text-rose-600">{error}</p>}
      </main>
    </div>
  );
}
