export type Score = {
  id: string;
  url: string;
  page_type?: string;
  score: number;
  dimensions: Record<string, number>;
  window: {
    excerpt: string;
    has_name: boolean | null;
    has_price: boolean | null;
    has_spec: boolean | null;
    has_quotable_sentence: boolean | null;
  };
  issues: { id: string; severity: string; message: string; evidence: string }[];
  schema_json: unknown;
  suggestions: {
    status: string;
    description: string;
    faq: { q: string; a: string }[];
    question_titles: string[];
  };
  quota?: { limit: number | null; remaining: number | null; unlimited: boolean };
  created_at?: string;
};

export function deviceId() {
  const key = "vertigeo-device";
  const existing = localStorage.getItem(key);
  if (existing) return existing;
  const created = crypto.randomUUID();
  localStorage.setItem(key, created);
  return created;
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    credentials: "include",
  });
  const text = await response.text();
  const data = text ? JSON.parse(text) : {};
  if (!response.ok) {
    throw new Error(data.message || "请求失败");
  }
  return data as T;
}
