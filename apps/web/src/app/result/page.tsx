"use client";

import { useEffect, useState } from "react";
import { AppFrame } from "@/components/Shell";
import { ScoreView } from "@/components/ScoreView";
import type { Score } from "@/lib/api";

export default function ResultPage() {
  const [score, setScore] = useState<Score | null>(null);
  useEffect(() => {
    const raw = sessionStorage.getItem("vertigeo-last-score");
    if (raw) setScore(JSON.parse(raw) as Score);
  }, []);
  return (
    <AppFrame active="score">
      {score ? <ScoreView score={score} /> : <p className="text-sm text-[#64748b]">还没有评分结果。</p>}
    </AppFrame>
  );
}
