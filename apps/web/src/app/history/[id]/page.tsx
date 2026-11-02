"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { AppFrame } from "@/components/Shell";
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
  return (
    <AppFrame active="history">
      {error && <p className="text-sm text-rose-600">{error}</p>}
      {!error && !score && <p className="text-sm text-[#64748b]">读取中</p>}
      {score && <ScoreView score={score} exportable />}
    </AppFrame>
  );
}
