"use client";

import { StreamCommentaryPanel } from "@/components/StreamCommentaryPanel";
import { StreamLeagueTable } from "@/components/StreamLeagueTable";
import { SeasonLeadersPanel } from "@/components/SeasonLeadersPanel";
import { useStreamState } from "@/hooks/useStreamState";
import {
  classifyEventLine,
  findSummaryLine,
  formatConnectionLabel,
  normalizeEventLines,
} from "@/lib/stream";

export default function LeaguePage() {
  const { table, events, leaders, connection, sessionId } = useStreamState();
  const lines = normalizeEventLines(events?.lines ?? []);
  const xgLine = events?.summary?.xg ?? findSummaryLine(lines, "xG:");
  const goals = lines.filter((line) => classifyEventLine(line) === "goal").length;
  const leader = table[0];
  const cellar = table[table.length - 1];
  const connectionClass =
    connection === "live" ? "active" : connection === "stale" ? "stale" : "registration";

  return (
    <>
      <div className="page-header">
        <div className="page-title">Season Desk</div>
        <div className="page-subtitle watch-subtitle">
          Watch the title race, danger zone, and current matchday notes without leaving the spectator loop.
        </div>
        <div className="watch-header-chips">
          <span className={`season-badge ${connectionClass}`}>
            {connection === "live" && <span className="live-dot" />}
            {formatConnectionLabel(connection)}
          </span>
          {sessionId && <span className="header-pill">Session {sessionId}</span>}
          {xgLine && <span className="header-pill">{xgLine}</span>}
        </div>
      </div>

      <div className="story-card-grid story-card-grid-wide">
        <article className="glass-card story-card">
          <span className="story-card-label">Leader</span>
          <strong>{leader ? `${leader.team} · ${leader.points} pts` : "Waiting"}</strong>
          <p>The top of the table needs to feel alive every time the page opens.</p>
        </article>

        <article className="glass-card story-card">
          <span className="story-card-label">Current Matchday</span>
          <strong>{goals} key scoring moments</strong>
          <p>Every goal should feed narrative pressure back into the standings.</p>
        </article>

        <article className="glass-card story-card">
          <span className="story-card-label">Danger Zone</span>
          <strong>{cellar ? cellar.team : "Waiting"}</strong>
          <p>The bottom of the table should look consequential, not decorative.</p>
        </article>
      </div>

      <div className="watch-grid">
        <StreamLeagueTable
          rows={table}
          title="Full Standings"
          subtitle="Promotion, title chase, and relegation pressure in one view."
        />

        <div className="league-side-stack">
          <SeasonLeadersPanel leaders={leaders} />

          <StreamCommentaryPanel
            lines={lines}
            title="Matchday Notes"
            summary={[xgLine].filter((value): value is string => Boolean(value))}
          />
        </div>
      </div>
    </>
  );
}
