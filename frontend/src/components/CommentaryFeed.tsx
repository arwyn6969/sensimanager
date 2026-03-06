"use client";

import { useState, useEffect } from "react";
import { COMMENTARY_URL } from "@/lib/contracts";
import { makeStreamRuntimePath, makeStreamUrl } from "@/lib/stream";

interface EventsData {
  count: number;
  lines: string[];
}

export function CommentaryFeed() {
  const [lines, setLines] = useState<string[]>([]);
  const [lastCount, setLastCount] = useState(0);

  useEffect(() => {
    const poll = async () => {
      try {
        const url = `${makeStreamUrl(COMMENTARY_URL, makeStreamRuntimePath("events.json"))}?_=${Date.now()}`;
        const res = await fetch(url);
        if (!res.ok) return;
        const data: EventsData = await res.json();
        if (data.count !== lastCount) {
          setLastCount(data.count);
          const filtered = data.lines.filter((l) => l.trim()).slice(-12).reverse();
          setLines(filtered);
        }
      } catch {
        // Commentary feed unavailable — expected when no stream running
      }
    };

    poll();
    const interval = setInterval(poll, 2000);
    return () => clearInterval(interval);
  }, [lastCount]);

  const classifyLine = (line: string): string => {
    const lower = line.toLowerCase();
    if (lower.includes("⚽") || lower.includes("goal")) return "goal";
    if (lower.includes("🟨") || lower.includes("🟥") || lower.includes("card") || lower.includes("booked"))
      return "card";
    if (lower.includes("🏥") || lower.includes("injur")) return "injury";
    return "";
  };

  return (
    <div className="glass-card" style={{ padding: "20px 24px" }}>
      <div className="section-title">⚡ Live Commentary</div>
      <div className="commentary-feed">
        {lines.length === 0 ? (
          <div className="empty-state" style={{ padding: "40px 20px", fontSize: 11 }}>
            ⚽ AWAITING MATCH DATA
          </div>
        ) : (
          lines.map((line, i) => (
            <div
              key={`${lastCount}-${i}`}
              className={`event-line ${classifyLine(line)}`}
              style={{ animationDelay: `${i * 0.05}s` }}
            >
              {line}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
