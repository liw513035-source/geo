"use client";

import { useEffect, useState } from "react";
import { ScoreView } from "@/components/ScoreView";
import type { Score } from "@/lib/api";

export default function ResultPage() {
  const [score, setScore] = useState<Score | null>(null);
  useEffect(() => {
    const raw = sessionStorage.getItem("vertigeo-last-score");
    if (raw) setScore(JSON.parse(raw) as Score);
  }, []);
  if (!score) return <p>没有评分结果。请从首页重新评分。</p>;
  return <ScoreView score={score} />;
}
