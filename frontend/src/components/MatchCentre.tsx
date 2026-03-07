"use client";

import Link from "next/link";

import { STREAM_URL } from "@/lib/contracts";
import {
  formatClock,
  formatFeedFreshness,
  formatStatusLabel,
  makeStreamUrl,
  type StreamConnection,
  type StreamScoreboard,
} from "@/lib/stream";

interface MatchCentreProps {
  scoreboard: StreamScoreboard | null;
  latestEvent: string | null;
  xgLine: string | null;
  motmLine: string | null;
  connection: StreamConnection;
  lastUpdated: number | null;
  sessionId: string | null;
}

const FORMATION_MARKERS: Record<string, Array<[number, number]>> = {
  "4-4-2": [
    [12, 50], [24, 18], [20, 38], [20, 62], [24, 82],
    [36, 20], [32, 42], [32, 58], [36, 80], [50, 42], [50, 58],
  ],
  "4-3-3": [
    [12, 50], [24, 20], [20, 40], [20, 60], [24, 80],
    [34, 28], [30, 50], [34, 72], [48, 16], [54, 50], [48, 84],
  ],
  "4-2-3-1": [
    [12, 50], [24, 18], [20, 38], [20, 62], [24, 82],
    [30, 40], [30, 60], [42, 18], [44, 50], [42, 82], [56, 50],
  ],
  "5-4-1": [
    [12, 50], [28, 14], [20, 30], [18, 50], [20, 70], [28, 86],
    [38, 24], [34, 42], [34, 58], [38, 76], [52, 50],
  ],
  "3-4-3": [
    [12, 50], [20, 28], [18, 50], [20, 72], [32, 14],
    [32, 40], [32, 60], [32, 86], [48, 16], [54, 50], [48, 84],
  ],
};

const STYLE_TRAITS: Record<string, { width: number; depth: number }> = {
  "balanced shape": { width: 1, depth: 1 },
  "patient possession": { width: 1.16, depth: 0.96 },
  "direct transition": { width: 0.94, depth: 1.16 },
  "compact defending": { width: 0.76, depth: 0.82 },
  "wing-heavy attacks": { width: 1.3, depth: 1.08 },
};

function buildMarkers(
  team: "home" | "away",
  formation: string,
  style: string,
): Array<{ left: number; top: number }> {
  const anchors = FORMATION_MARKERS[formation] ?? FORMATION_MARKERS["4-4-2"];
  const traits = STYLE_TRAITS[style] ?? STYLE_TRAITS["balanced shape"];

  return anchors.map(([left, top]) => {
    const lane = top - 50;
    const shapedTop = 50 + lane * traits.width;
    const depthShift = (traits.depth - 1) * 10;
    const shapedLeft = team === "home" ? left + depthShift : 100 - left - depthShift;

    return {
      left: Math.max(10, Math.min(90, shapedLeft)),
      top: Math.max(12, Math.min(88, shapedTop)),
    };
  });
}

function formatStatusTitle(
  scoreboard: StreamScoreboard | null,
  connection: StreamConnection,
): string {
  if (connection === "stale") return "Feed Stale";
  if (connection === "offline") return "Awaiting Feed";
  return formatStatusLabel(scoreboard?.status);
}

export function MatchCentre({
  scoreboard,
  latestEvent,
  xgLine,
  motmLine,
  connection,
  lastUpdated,
  sessionId,
}: MatchCentreProps) {
  const homeTeam = scoreboard?.home_team ?? "Home";
  const awayTeam = scoreboard?.away_team ?? "Away";
  const homeGoals = scoreboard?.home_goals ?? 0;
  const awayGoals = scoreboard?.away_goals ?? 0;
  const homeFormation = scoreboard?.home_formation ?? "4-4-2";
  const awayFormation = scoreboard?.away_formation ?? "4-4-2";
  const homeStyle = scoreboard?.home_style ?? "balanced shape";
  const awayStyle = scoreboard?.away_style ?? "balanced shape";
  const pressureNote = scoreboard?.pressure_note ?? null;
  const matchNarrative =
    scoreboard?.match_narrative ?? "The next job is making every fixture feel tactically distinct.";
  const tacticalFrame = scoreboard
    ? `${homeTeam} ${homeFormation} with ${homeStyle} against ${awayTeam} ${awayFormation} with ${awayStyle}.`
    : "Formation and pressure context will appear when the live feed is active.";
  const scoreTilt = Math.max(-12, Math.min(12, (homeGoals - awayGoals) * 4));
  const minuteDrift = scoreboard ? (scoreboard.minute % 15) - 7 : 0;
  const homeMarkers = buildMarkers("home", homeFormation, homeStyle);
  const awayMarkers = buildMarkers("away", awayFormation, awayStyle);
  const freshness = formatFeedFreshness(lastUpdated, connection);
  const statusText = sessionId ? `${sessionId} · ${freshness}` : freshness;

  return (
    <section className="glass-card match-centre-card">
      <div className="match-centre-head">
        <div>
          <div className="panel-kicker">Now Showing</div>
          <h2 className="panel-title-xl">{formatStatusTitle(scoreboard, connection)}</h2>
        </div>
        <div className="match-centre-status">
          <span className={`live-signal-dot ${connection}`} />
          {statusText}
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

      <div className="match-style-strip">
        <span className="match-style-chip home">{homeTeam}: {homeFormation} · {homeStyle}</span>
        <span className="match-style-chip narrative">{pressureNote ?? matchNarrative}</span>
        <span className="match-style-chip away">{awayTeam}: {awayFormation} · {awayStyle}</span>
      </div>

        <div className="pitch-board">
          <div className="pitch-board-lines" />
          <div className="pitch-board-circle" />
          {homeMarkers.map(({ left, top }, index) => (
            <span
              key={`home-${index}`}
              className="pitch-marker home"
              style={{ left: `${left}%`, top: `${top}%` }}
            />
          ))}
          {awayMarkers.map(({ left, top }, index) => (
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
          <span className="match-context-label">{pressureNote ? "Pressure State" : "Storyline"}</span>
          <p>
            {pressureNote
              ?? latestEvent
              ?? "The feed is quiet right now. Kick off the stream runner to start the show."}
          </p>
        </article>
        <article className="match-context-card">
          <span className="match-context-label">Shape Clash</span>
          <p>{tacticalFrame}</p>
        </article>
        <article className="match-context-card">
          <span className="match-context-label">Data Layer</span>
          <p>
            {xgLine && motmLine
              ? `${xgLine} · ${motmLine}`
              : xgLine
                ?? motmLine
                ?? "Expected goals and the man of the match will lock in once the game closes."}
          </p>
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
