import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "URL Markdown Workbench",
  description: "A local workbench for capturing URLs into raw and polished Markdown for Obsidian.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
