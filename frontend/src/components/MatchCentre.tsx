"use client";

import Link from "next/link";

import { STREAM_URL } from "@/lib/contracts";
import { formatClock, formatStatusLabel, makeStreamUrl, type StreamScoreboard } from "@/lib/stream";

interface MatchCentreProps {
  scoreboard: StreamScoreboard | null;
  latestEvent: string | null;
  xgLine: string | null;
  motmLine: string | null;
  lastUpdated: number | null;
}

const HOME_MARKERS = [
  [16, 22],
  [22, 38],
  [28, 56],
  [36, 28],
  [40, 70],
];

const AWAY_MARKERS = [
  [84, 24],
  [76, 40],
  [70, 60],
  [62, 30],
  [58, 72],
];

function formatUpdated(lastUpdated: number | null): string {
  if (!lastUpdated) return "waiting for stream";
  return `updated ${new Date(lastUpdated).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  })}`;
}

export function MatchCentre({
  scoreboard,
  latestEvent,
  xgLine,
  motmLine,
  lastUpdated,
}: MatchCentreProps) {
  const homeTeam = scoreboard?.home_team ?? "Home";
  const awayTeam = scoreboard?.away_team ?? "Away";
  const homeGoals = scoreboard?.home_goals ?? 0;
  const awayGoals = scoreboard?.away_goals ?? 0;
  const scoreTilt = Math.max(-12, Math.min(12, (homeGoals - awayGoals) * 4));
  const minuteDrift = scoreboard ? (scoreboard.minute % 15) - 7 : 0;

  return (
    <section className="glass-card match-centre-card">
      <div className="match-centre-head">
        <div>
          <div className="panel-kicker">Now Showing</div>
          <h2 className="panel-title-xl">{formatStatusLabel(scoreboard?.status)}</h2>
        </div>
        <div className="match-centre-status">
          <span className="live-signal-dot" />
          {formatUpdated(lastUpdated)}
        </div>
      </div>

      <div className="score-shell">
        <div className="club-panel club-panel-home">
          <span className="club-panel-label">Home</span>
          <span className="club-panel-name">{homeTeam}</span>
        </div>
        <div className="score-panel">
          <div className="score-panel-tally">
            <span>{homeGoals}</span>
            <span className="score-divider">:</span>
            <span>{awayGoals}</span>
          </div>
          <div className="score-panel-clock">{formatClock(scoreboard)}</div>
        </div>
        <div className="club-panel club-panel-away">
          <span className="club-panel-label">Away</span>
          <span className="club-panel-name">{awayTeam}</span>
        </div>
      </div>

      <div className="pitch-board">
        <div className="pitch-board-lines" />
        <div className="pitch-board-circle" />
        {HOME_MARKERS.map(([left, top], index) => (
          <span
            key={`home-${index}`}
            className="pitch-marker home"
            style={{ left: `${left}%`, top: `${top}%` }}
          />
        ))}
        {AWAY_MARKERS.map(([left, top], index) => (
          <span
            key={`away-${index}`}
            className="pitch-marker away"
            style={{ left: `${left}%`, top: `${top}%` }}
          />
        ))}
        <span
          className="pitch-ball"
          style={{
            left: `${50 + scoreTilt}%`,
            top: `${48 + minuteDrift}%`,
          }}
        />
      </div>

      <div className="match-context-grid">
        <article className="match-context-card">
          <span className="match-context-label">Storyline</span>
          <p>{latestEvent ?? "The feed is quiet right now. Kick off the stream runner to start the show."}</p>
        </article>
        <article className="match-context-card">
          <span className="match-context-label">Data Layer</span>
          <p>{xgLine ?? "Expected goals will appear once the match summary lands."}</p>
        </article>
        <article className="match-context-card">
          <span className="match-context-label">Spotlight</span>
          <p>{motmLine ?? "Man of the match will be called once the game closes."}</p>
        </article>
      </div>

      <div className="match-actions">
        <a
          className="btn btn-primary"
          href={makeStreamUrl(STREAM_URL, "overlay.html")}
          target="_blank"
          rel="noreferrer"
        >
          Open Broadcast Overlay
        </a>
        <Link className="btn" href="/league">
          Open Full Table
        </Link>
      </div>
    </section>
  );
}
