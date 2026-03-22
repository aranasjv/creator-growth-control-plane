import type { Metadata } from "next";
import localFont from "next/font/local";
import type { ReactNode } from "react";
import "./globals.css";

const boldFont = localFont({
  src: "../public/fonts/bold_font.ttf",
  variable: "--font-display",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Creator Growth Control Plane",
  description: "Monitoring, profit analytics, and operations dashboard for creator growth workers.",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en">
      <body className={boldFont.variable}>{children}</body>
    </html>
  );
}
