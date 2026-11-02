"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { ScoreView } from "@/components/ScoreView";
import { api, type Score } from "@/lib/api";

export default function HistoryPage() {
  const params = useParams<{ id: string }>();
  const [score, setScore] = useState<Score | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    api<Score>(`/api/v1/scores/${params.id}`)
      .then(setScore)
      .catch((caught) => setError(caught instanceof Error ? caught.message : "找不到记录"));
  }, [params.id]);
  if (error) return <p>{error}</p>;
  if (!score) return <p>正在读取记录</p>;
  return (
    <div className="space-y-4">
      <div className="flex gap-3 text-sm">
        <a className="underline" href={`/api/v1/scores/${score.id}/export.md`}>下载 Markdown</a>
        <a className="underline" href={`/api/v1/scores/${score.id}/export.pdf`}>下载 PDF</a>
      </div>
      <ScoreView score={score} />
    </div>
  );
}
