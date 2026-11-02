"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, deviceId, type Score } from "@/lib/api";

const stages = ["抓取页面", "规则分析", "生成建议"];

export default function HomePage() {
  const router = useRouter();
  const [url, setUrl] = useState("");
  const [quota, setQuota] = useState("正在读取剩余次数");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [stage, setStage] = useState(0);

  useEffect(() => {
    const id = deviceId();
    api<{ limit: number | null; remaining: number | null; unlimited: boolean }>(`/api/v1/quota?device_id=${id}`)
      .then((data) => setQuota(data.unlimited ? "当前不限次数" : `今日剩余 ${data.remaining} / ${data.limit} 次`))
      .catch(() => setQuota("暂时无法读取次数"));
  }, []);

  useEffect(() => {
    if (!loading) return;
    setStage(0);
    const timers = [window.setTimeout(() => setStage(1), 700), window.setTimeout(() => setStage(2), 1800)];
    return () => timers.forEach((timer) => window.clearTimeout(timer));
  }, [loading]);

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

  return (
    <section className="mx-auto max-w-2xl">
      <p className="text-sm text-stone-500">电商页面 GEO 健康分</p>
      <h1 className="mt-2 text-3xl font-semibold">粘贴商品页或店铺页地址</h1>
      <p className="mt-3 text-stone-600">无需注册即可评分。系统抓取公开页面，用规则给出 0 到 100 分，并生成可替换的文案和 Schema。</p>
      <form onSubmit={onSubmit} className="mt-8 space-y-3">
        <input
          value={url}
          onChange={(event) => setUrl(event.target.value)}
          placeholder="https://"
          className="w-full rounded-lg border border-stone-300 bg-white px-4 py-3"
          required
        />
        <button disabled={loading} className="rounded-lg bg-stone-900 px-5 py-3 text-white disabled:opacity-60">
          {loading ? "正在评分" : "开始评分"}
        </button>
      </form>
      <p className="mt-4 text-sm text-stone-500">{quota}</p>
      {loading && (
        <ol className="mt-6 space-y-2 text-sm">
          {stages.map((label, index) => (
            <li key={label} className={index <= stage ? "text-stone-900" : "text-stone-400"}>
              {index < stage ? "完成" : index === stage ? "进行中" : "等待"} · {label}
            </li>
          ))}
        </ol>
      )}
      {error && <p className="mt-4 text-sm text-red-700">{error}</p>}
    </section>
  );
}
