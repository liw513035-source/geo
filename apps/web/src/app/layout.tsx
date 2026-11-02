import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "VertiGEO",
  description: "电商 GEO 评分",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="zh-CN">
      <body className="min-h-screen bg-[#f7f8fb] text-[#0f172a]">{children}</body>
    </html>
  );
}
