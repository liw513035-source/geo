"use client";

import { useState } from "react";
import type { Score } from "@/lib/api";

const labels: [string, string][] = [
  ["citability", "可引用性"],
  ["entity", "商品实体"],
  ["structure", "结构清晰度"],
  ["schema", "Schema"],
  ["technical", "技术可访问性"],
];

export function ScoreView({ score, exportable = false }: { score: Score; exportable?: boolean }) {
  const verdict = score.score >= 80 ? "整体表现良好" : score.score >= 60 ? "仍有明显缺口" : "难以被直接引用";
  const p0 = score.issues.filter((item) => item.severity === "P0");
  const p1 = score.issues.filter((item) => item.severity === "P1");
  const host = safeHost(score.url);
  const suggestionText = [
    score.suggestions.description,
    ...score.suggestions.faq.map((item) => `${item.q}\n${item.a}`),
    ...score.suggestions.question_titles,
  ].filter(Boolean).join("\n\n");

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-[#0b1f44]">评分结果</h1>
          <p className="mt-1 max-w-xl truncate text-sm text-[#64748b]">{host}</p>
        </div>
        {exportable && (
          <div className="flex gap-2 text-sm">
            <a className="rounded-lg border border-[#dbe3ef] bg-white px-3 py-1.5" href={`/api/v1/scores/${score.id}/export.md`}>Markdown</a>
            <a className="rounded-lg border border-[#dbe3ef] bg-white px-3 py-1.5" href={`/api/v1/scores/${score.id}/export.pdf`}>PDF</a>
          </div>
        )}
      </div>

      <section className="grid gap-4 lg:grid-cols-[1.15fr_0.85fr]">
        <article className="flex items-center gap-6 rounded-2xl border border-[#e8edf5] bg-white p-5">
          <Ring value={score.score} />
          <div>
            <p className="text-lg font-medium text-[#0b1f44]">{verdict}</p>
            <p className="mt-2 text-sm text-[#64748b]">总体 GEO 分数</p>
          </div>
        </article>
        <article className="rounded-2xl border border-[#e8edf5] bg-white p-5">
          <h2 className="text-sm font-medium text-[#0b1f44]">维度得分</h2>
          <ul className="mt-4 space-y-3">
            {labels.map(([key, label]) => {
              const value = Number(score.dimensions[key] || 0);
              return (
                <li key={key} className="grid grid-cols-[5.5rem_1fr_2rem] items-center gap-3 text-sm">
                  <span className="text-[#475569]">{label}</span>
                  <span className="h-2 overflow-hidden rounded-full bg-[#e8eef8]">
                    <span className="block h-full rounded-full bg-[#3b82f6]" style={{ width: `${value}%` }} />
                  </span>
                  <span className="text-right tabular-nums text-[#334155]">{value}</span>
                </li>
              );
            })}
          </ul>
        </article>
      </section>

      <section className="rounded-2xl border border-[#e8edf5] bg-white p-5">
        <div className="flex items-center justify-between">
          <h2 className="font-medium text-[#0b1f44]">前 30% 窗口</h2>
          <span className="rounded-full bg-[#eff6ff] px-2 py-0.5 text-xs text-[#1d4ed8]">Top 30%</span>
        </div>
        <div className="mt-3 flex flex-wrap gap-2 text-xs">
          <Mark ok={score.window.has_name} label="商品名" />
          <Mark ok={score.window.has_price} label="价格" />
          <Mark ok={score.window.has_spec} label="规格" />
          <Mark ok={score.window.has_quotable_sentence} label="可引用句" />
        </div>
        {score.window.excerpt && <p className="mt-3 line-clamp-3 text-sm leading-6 text-[#475569]">{score.window.excerpt}</p>}
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <IssueColumn title={`P0 严重问题（${p0.length}）`} items={p0} badge="P0" />
        <IssueColumn title={`P1 高优先级（${p1.length}）`} items={p1} badge="P1" />
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <article className="rounded-2xl border border-[#e8edf5] bg-white p-5">
          <div className="flex items-center justify-between">
            <h2 className="font-medium">优化建议</h2>
            {score.suggestions.status === "ok" && <Copy text={suggestionText} label="复制" />}
          </div>
          {score.suggestions.status !== "ok" ? (
            <p className="mt-3 text-sm text-[#64748b]">暂不可用</p>
          ) : (
            <div className="mt-3 space-y-3 text-sm leading-6 text-[#334155]">
              <p>{score.suggestions.description}</p>
              {score.suggestions.question_titles.map((title) => <p key={title}>{title}</p>)}
              {score.suggestions.faq.map((item) => (
                <p key={item.q}><span className="font-medium">{item.q}</span> {item.a}</p>
              ))}
            </div>
          )}
        </article>
        <article className="rounded-2xl border border-[#e8edf5] bg-white p-5">
          <div className="flex items-center justify-between">
            <h2 className="font-medium">Schema</h2>
            <Copy text={JSON.stringify(score.schema_json, null, 2)} label="复制 JSON" />
          </div>
          <pre className="mt-3 max-h-64 overflow-auto rounded-xl bg-[#0f172a] p-3 text-xs leading-5 text-[#dbeafe]">{JSON.stringify(score.schema_json, null, 2)}</pre>
        </article>
      </section>
    </div>
  );
}

function Ring({ value }: { value: number }) {
  const radius = 42;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - Math.max(0, Math.min(100, value)) / 100);
  return (
    <svg viewBox="0 0 120 120" className="h-32 w-32 shrink-0">
      <circle cx="60" cy="60" r={radius} fill="none" stroke="#e8eef8" strokeWidth="10" />
      <circle cx="60" cy="60" r={radius} fill="none" stroke="#3b82f6" strokeWidth="10" strokeLinecap="round" strokeDasharray={circumference} strokeDashoffset={offset} transform="rotate(-90 60 60)" />
      <text x="60" y="58" textAnchor="middle" fontSize="32" fontWeight="650" fill="#0b1f44">{value}</text>
      <text x="60" y="78" textAnchor="middle" fontSize="12" fill="#94a3b8">/100</text>
    </svg>
  );
}

function IssueColumn({ title, items, badge }: { title: string; items: Score["issues"]; badge: string }) {
  return (
    <article className="rounded-2xl border border-[#e8edf5] bg-white p-5">
      <h2 className="text-sm font-medium">{title}</h2>
      <ul className="mt-3 space-y-2">
        {items.length === 0 && <li className="text-sm text-[#94a3b8]">无</li>}
        {items.map((item) => (
          <li key={item.id} className="flex items-start justify-between gap-3 rounded-xl bg-[#f8fafc] px-3 py-2 text-sm">
            <span>{item.message}</span>
            <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs ${badge === "P0" ? "bg-rose-50 text-rose-600" : "bg-amber-50 text-amber-700"}`}>{badge}</span>
          </li>
        ))}
      </ul>
    </article>
  );
}

function Mark({ ok, label }: { ok: boolean | null; label: string }) {
  if (ok === null) return null;
  return <span className={`rounded-full px-2 py-1 ${ok ? "bg-emerald-50 text-emerald-700" : "bg-rose-50 text-rose-600"}`}>{ok ? "有" : "缺"}{label}</span>;
}

function Copy({ text, label }: { text: string; label: string }) {
  const [done, setDone] = useState(false);
  return (
    <button className="rounded-lg border border-[#dbe3ef] px-2.5 py-1 text-xs text-[#1d4ed8]" onClick={async () => {
      await navigator.clipboard.writeText(text);
      setDone(true);
      window.setTimeout(() => setDone(false), 1000);
    }}>{done ? "已复制" : label}</button>
  );
}

function safeHost(raw: string) {
  try {
    return new URL(raw).hostname;
  } catch {
    return raw.slice(0, 48);
  }
}
