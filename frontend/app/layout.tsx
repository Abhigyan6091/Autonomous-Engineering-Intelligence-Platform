import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "AEIP — Autonomous Engineering Intelligence Platform",
  description:
    "AI-powered software reliability and engineering investigation platform. Detect problems, investigate incidents, generate hypotheses, validate fixes.",
  keywords: ["AI", "SRE", "incident investigation", "root cause analysis", "autonomous engineering"],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className={inter.className}>{children}</body>
    </html>
  );
}
