"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const WATCH_ITEMS = [
  { href: "/", icon: "📺", label: "Live Match" },
  { href: "/league", icon: "🏆", label: "Season Desk" },
] as const;

const EXPERIMENT_ITEMS = [
  { href: "/gallery", icon: "⚽", label: "Gallery" },
  { href: "/market", icon: "💰", label: "Market" },
] as const;

export function Sidebar() {
  const pathname = usePathname();
  const isExperimentalRoute = EXPERIMENT_ITEMS.some((item) => item.href === pathname);

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">SWOS420</div>
      <div className="sidebar-subtitle">Live Autonomous League</div>

      <div className="sidebar-section-label">Watch MVP</div>
      <nav className="sidebar-nav sidebar-nav-primary">
        {WATCH_ITEMS.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={`sidebar-link ${pathname === item.href ? "active" : ""}`}
          >
            <span className="icon">{item.icon}</span>
            <span>{item.label}</span>
          </Link>
        ))}
      </nav>

      <div className="sidebar-section-label sidebar-section-secondary">Parked Experiments</div>
      <nav className="sidebar-nav">
        {EXPERIMENT_ITEMS.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={`sidebar-link parked ${pathname === item.href ? "active" : ""}`}
          >
            <span className="icon">{item.icon}</span>
            <span>{item.label}</span>
            <span className="sidebar-pill">Parked</span>
          </Link>
        ))}
      </nav>

      <div className={`sidebar-note ${isExperimentalRoute ? "sidebar-note-parked" : ""}`}>
        {isExperimentalRoute
          ? "Parked route. Ownership and wallet flows stay archived until the watch-first MVP earns their return."
          : "Watch-first mainline active. Ownership screens stay parked until the spectator MVP is good."}
      </div>
    </aside>
  );
}
