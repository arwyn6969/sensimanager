import type { Metadata } from "next";
import { Providers } from "./providers";
import { Sidebar } from "@/components/Sidebar";
import "./globals.css";

export const metadata: Metadata = {
  title: "SWOS420 — Live Autonomous Football League",
  description:
    "A watch-first autonomous football league with live commentary, table pressure, and a broadcast overlay you can run locally.",
  keywords: ["SWOS420", "football", "soccer", "live stream", "simulation", "autonomous league"],
  openGraph: {
    title: "SWOS420 — Live Autonomous Football League",
    description: "Watch seeded matchdays, commentary, table pressure, and the live broadcast overlay.",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          rel="preconnect"
          href="https://fonts.gstatic.com"
          crossOrigin="anonymous"
        />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@400;700&family=Press+Start+2P&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        <Providers>
          <div className="app-layout">
            <Sidebar />
            <main className="main-content">{children}</main>
          </div>
        </Providers>
      </body>
    </html>
  );
}
