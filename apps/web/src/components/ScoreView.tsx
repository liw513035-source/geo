"use client";

import type { Score } from "@/lib/api";

const labels: Record<string, string> = {
  citability: "可引用性",
  entity: "实体完整性",
  structure: "结构清晰度",
  schema: "Schema",
  technical: "技术可访问性",
};

export function ScoreView({ score }: { score: Score }) {
  const axes = Object.entries(labels);
  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-6 sm:flex-row sm:items-center">
        <div className="grid h-28 w-28 place-items-center rounded-full border-8 border-stone-900 text-3xl font-semibold">
          {score.score}
        </div>
        <div>
          <p className="text-sm text-stone-500 break-all">{score.url}</p>
          <h1 className="mt-1 text-2xl font-semibold">GEO 健康分 {score.score}</h1>
        </div>
      </div>
      <svg viewBox="0 0 320 220" className="w-full max-w-md rounded-xl bg-white p-2">
        {axes.map(([key], index) => {
          const angle = -Math.PI / 2 + (index * 2 * Math.PI) / axes.length;
          const value = Number(score.dimensions[key] || 0) / 100;
          const x = 160 + Math.cos(angle) * 80 * value;
          const y = 110 + Math.sin(angle) * 70 * value;
          const labelX = 160 + Math.cos(angle) * 100;
          const labelY = 110 + Math.sin(angle) * 88;
          return (
            <g key={key}>
              <line x1="160" y1="110" x2={160 + Math.cos(angle) * 80} y2={110 + Math.sin(angle) * 70} stroke="#d6d3d1" />
              <circle cx={x} cy={y} r="4" fill="#1c1917" />
              <text x={labelX} y={labelY} fontSize="11" textAnchor="middle" fill="#57534e">
                {labels[key]} {score.dimensions[key]}
              </text>
            </g>
          );
        })}
      </svg>
      <section className="rounded-xl bg-white p-4">
        <h2 className="font-semibold">前 30% 窗口</h2>
        <p className="mt-2 text-sm leading-6 text-stone-700">{score.window.excerpt || "没有摘录"}</p>
        <p className="mt-2 text-sm text-stone-500">
          商品名 {flag(score.window.has_name)} · 价格 {flag(score.window.has_price)} · 规格 {flag(score.window.has_spec)} · 可引用句子 {flag(score.window.has_quotable_sentence)}
        </p>
      </section>
      <section>
        <h2 className="font-semibold">问题</h2>
        <ul className="mt-3 space-y-2">
          {score.issues.length === 0 && <li className="text-sm text-stone-500">没有扣分项。</li>}
          {score.issues.map((issue) => (
            <li key={issue.id} className="rounded-lg bg-white px-3 py-2 text-sm">
              <span className="font-medium">{issue.severity}</span> {issue.id} {issue.message}
            </li>
          ))}
        </ul>
      </section>
      <section className="rounded-xl bg-white p-4">
        <h2 className="font-semibold">优化文案</h2>
        {score.suggestions.status !== "ok" ? (
          <p className="mt-2 text-sm text-stone-500">建议暂时无法生成</p>
        ) : (
          <div className="mt-3 space-y-4 text-sm leading-6">
            <Copy text={score.suggestions.description} />
            {score.suggestions.faq.map((item) => (
              <div key={item.q}>
                <p className="font-medium">{item.q}</p>
                <Copy text={item.a} />
              </div>
            ))}
            {score.suggestions.question_titles.map((title) => (
              <Copy key={title} text={title} />
            ))}
          </div>
        )}
      </section>
      <section>
        <div className="flex items-center justify-between">
          <h2 className="font-semibold">Schema</h2>
          <button className="text-sm underline" onClick={() => navigator.clipboard.writeText(JSON.stringify(score.schema_json, null, 2))}>
            复制
          </button>
        </div>
        <pre className="mt-3 overflow-auto rounded-xl bg-stone-900 p-4 text-xs text-stone-100">{JSON.stringify(score.schema_json, null, 2)}</pre>
      </section>
    </div>
  );
}

function flag(value: boolean | null) {
  if (value === null) return "—";
  return value ? "有" : "无";
}

function Copy({ text }: { text: string }) {
  return (
    <div className="flex items-start justify-between gap-3">
      <p className="whitespace-pre-wrap">{text}</p>
      <button className="shrink-0 text-stone-500 underline" onClick={() => navigator.clipboard.writeText(text)}>
        复制
      </button>
    </div>
  );
}
