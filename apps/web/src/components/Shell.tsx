import type { ReactNode } from "react";
import Link from "next/link";

export function Logo() {
  return (
    <span className="grid h-8 w-8 place-items-center rounded-lg bg-[#2563eb] text-white">
      <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M12 3 20 8v8l-8 5-8-5V8l8-5Z" />
        <path d="M12 8v8M8.5 10.5 12 12l3.5-1.5" />
      </svg>
    </span>
  );
}

export function MarketingHeader() {
  return (
    <header className="border-b border-[#e8edf5] bg-white">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4">
        <Link href="/" className="flex items-center gap-2 text-lg font-semibold text-[#0b1f44]">
          <Logo />
          VertiGEO
        </Link>
        <nav className="flex items-center gap-1 text-sm text-[#334155]">
          <Link className="rounded-lg px-3 py-2 hover:bg-[#f4f7fb]" href="/pricing">定价</Link>
          <Link className="rounded-lg px-3 py-2 hover:bg-[#f4f7fb]" href="/account">历史</Link>
          <Link className="ml-2 rounded-lg bg-[#0b1f44] px-4 py-2 text-white" href="/login">登录</Link>
        </nav>
      </div>
    </header>
  );
}

const items = [
  { id: "score", href: "/", label: "评分结果" },
  { id: "history", href: "/account", label: "历史记录" },
  { id: "pricing", href: "/pricing", label: "定价" },
];

export function AppFrame({ active, children }: { active: "score" | "history" | "pricing"; children: ReactNode }) {
  return (
    <div className="min-h-screen bg-[#f5f7fb]">
      <header className="flex h-14 items-center justify-between border-b border-[#e8edf5] bg-white px-4">
        <Link href="/" className="flex items-center gap-2 font-semibold text-[#0b1f44]">
          <Logo />
          VertiGEO
        </Link>
        <Link href="/login" className="rounded-lg bg-[#0b1f44] px-3 py-1.5 text-sm text-white">登录</Link>
      </header>
      <div className="mx-auto flex max-w-7xl">
        <aside className="hidden w-52 shrink-0 border-r border-[#e8edf5] bg-white p-3 md:block">
          <nav className="space-y-1">
            {items.map((item) => (
              <Link key={item.id} href={item.href} className={`block rounded-lg px-3 py-2 text-sm ${active === item.id ? "bg-[#eff6ff] font-medium text-[#1d4ed8]" : "text-[#334155] hover:bg-[#f8fafc]"}`}>
                {item.label}
              </Link>
            ))}
          </nav>
        </aside>
        <div className="min-w-0 flex-1">
          <div className="flex gap-2 border-b border-[#e8edf5] bg-white px-3 py-2 md:hidden">
            {items.map((item) => (
              <Link key={item.id} href={item.href} className={`rounded-full px-3 py-1 text-sm ${active === item.id ? "bg-[#eff6ff] text-[#1d4ed8]" : "text-[#64748b]"}`}>
                {item.label}
              </Link>
            ))}
          </div>
          <div className="p-4 md:p-6">{children}</div>
        </div>
      </div>
    </div>
  );
}
