import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "股市风险观察 | 看清信号，了解依据",
  description: "输入 A 股代码，查看最新已收盘日的短期风险信号、判断依据和查询历史。",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
