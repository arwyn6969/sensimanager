"use client";

import Link from "next/link";

import { MatchCentre } from "@/components/MatchCentre";
import { MatchPlayerStatsPanel } from "@/components/MatchPlayerStatsPanel";
import { SessionProgressRail } from "@/components/SessionProgressRail";
import { StreamCommentaryPanel } from "@/components/StreamCommentaryPanel";
import { StreamLeagueTable } from "@/components/StreamLeagueTable";
import { useStreamState } from "@/hooks/useStreamState";
import { STREAM_URL } from "@/lib/contracts";
import {
  classifyEventLine,
  deriveLifecycleState,
  describeDangerZone,
  describeLeaderGap,
  describeResultImpact,
  formatConnectionLabel,
  formatLifecycleLabel,
  findSummaryLine,
  latestNarrativeLine,
  makeStreamUrl,
  normalizeEventLines,
} from "@/lib/stream";

export default function DashboardPage() {
  const { scoreboard, events, table, leaders, session, connection, lastUpdated, sessionId } = useStreamState();
  const lines = normalizeEventLines(events?.lines ?? []);
  const pressureNote = scoreboard?.pressure_note ?? null;
  const latestEvent = pressureNote ?? scoreboard?.story ?? events?.latest?.text ?? latestNarrativeLine(lines);
  const xgLine = events?.summary?.xg ?? findSummaryLine(lines, "xG:");
  const motmLine = events?.summary?.motm ?? findSummaryLine(lines, "⭐");
  const matchPlayerStats = events?.match_player_stats ?? null;

  const lifecycle = deriveLifecycleState(session, connection, scoreboard);
  const leader = table[0];
  const goals = lines.filter((line) => classifyEventLine(line) === "goal").length;
  const chances = lines.filter((line) => classifyEventLine(line) === "chance").length;
  const cards = lines.filter((line) => classifyEventLine(line) === "card").length;
  const injuries = lines.filter((line) => classifyEventLine(line) === "injury").length;
  const matchNarrative =
    scoreboard?.match_narrative ?? "The stream needs distinct identities, not the same match wearing new badges.";
  const tacticalMatchup = scoreboard
    ? `${scoreboard.home_team} ${scoreboard.home_formation ?? "4-4-2"} vs ${scoreboard.away_team} ${scoreboard.away_formation ?? "4-4-2"}`
    : "Waiting for the next tactical frame";
  const pressureSummary = pressureNote ?? "Table pressure will appear when the live feed has standings context.";
  const tableHeat = describeLeaderGap(table);
  const dangerSummary = describeDangerZone(table);
  const resultImpact = describeResultImpact(table, session?.last_result, lifecycle);
  const connectionClass =
    connection === "live" ? "active" : connection === "stale" ? "stale" : "registration";
  const previewAvailable = connection !== "offline";

  return (
    <>
      <div className="page-header watch-header">
        <div>
          <div className="page-title">Live Match Centre</div>
          <div className="page-subtitle watch-subtitle">
            Watch-first mainline: live fixture, commentary pulse, standings pressure,
            and the direct path into the local broadcast overlay.
          </div>
        </div>
        <div className="watch-header-chips">
          <span className={`season-badge ${connectionClass}`}>
            {connection === "live" && <span className="live-dot" />}
            {formatConnectionLabel(connection)}
          </span>
          {sessionId && <span className="header-pill">Session {sessionId}</span>}
          <span className="header-pill">
            {leader ? `Leader ${leader.team} • ${leader.points} pts` : "Standings waiting"}
          </span>
        </div>
      </div>

      <SessionProgressRail session={session} connection={connection} scoreboard={scoreboard} table={table} />

      <div className="broadcast-home-grid">
        <MatchCentre
          scoreboard={scoreboard}
          latestEvent={latestEvent}
          xgLine={xgLine}
          motmLine={motmLine}
          connection={connection}
          lastUpdated={lastUpdated}
          sessionId={sessionId}
          session={session}
        />

        <div className="broadcast-side-stack">
          <div className="story-card-grid">
            <article className="glass-card story-card">
              <span className="story-card-label">
                {lifecycle === "season_complete" || lifecycle === "matchday_complete"
                  ? "Show State"
                  : pressureNote
                    ? "Pressure State"
                    : "Match Texture"}
              </span>
              <strong>
                {lifecycle === "season_complete" || lifecycle === "matchday_complete"
                  ? formatLifecycleLabel(lifecycle)
                  : pressureNote
                  ? `${(scoreboard?.pressure_tone ?? "live").replace(/^\w/, (char) => char.toUpperCase())} pressure`
                  : `${goals} goals`}
              </strong>
              <p>
                {lifecycle === "season_complete" || lifecycle === "matchday_complete"
                  ? resultImpact
                  : pressureNote
                  ? pressureSummary
                  : `${chances} key chances, ${cards} cards, and ${injuries} injuries have shaped the current feed.`}
              </p>
            </article>

            <article className="glass-card story-card">
              <span className="story-card-label">Shape Clash</span>
              <strong>{tacticalMatchup}</strong>
              <p>
                {matchNarrative}
              </p>
            </article>

            <article className="glass-card story-card">
              <span className="story-card-label">Table Consequence</span>
              <strong>{leader ? `Leader ${leader.team}` : "Standings waiting"}</strong>
              <p>
                {tableHeat} {dangerSummary} <Link href="/league">Open the full league table</Link> to follow the pressure
                building above and below the line.
              </p>
            </article>
          </div>
        </div>
      </div>

      <section className="glass-card broadcast-panel preview-panel preview-panel-wide">
        <div className="panel-header">
          <div>
            <div className="panel-kicker">Broadcast Preview</div>
            <h2 className="panel-title-lg">Overlay Window</h2>
            <p className="panel-copy">
              Use this as the watch surface. The full overlay should dominate the frame,
              not sit crushed into a narrow dashboard column.
            </p>
          </div>
        </div>

        {previewAvailable ? (
          <iframe
            className="watch-frame"
            src={makeStreamUrl(STREAM_URL, "overlay.html")}
            title="SWOS420 broadcast overlay preview"
          />
        ) : (
          <div className="watch-frame-fallback">
            <p>Start the local watch loop to preview the overlay and session feed.</p>
            <code>./.venv/bin/python scripts/serve_overlay.py</code>
            <code>./.venv/bin/python scripts/stream_league.py --source demo --num-teams 4 --matchdays 2 --seed 420</code>
          </div>
        )}
      </section>

      <div className="watch-grid">
        <StreamCommentaryPanel
          lines={lines}
          summary={[xgLine, motmLine].filter((value): value is string => Boolean(value))}
        />
        <div className="league-side-stack">
          <MatchPlayerStatsPanel
            stats={matchPlayerStats}
            homeTeam={scoreboard?.home_team}
            awayTeam={scoreboard?.away_team}
            leaders={leaders}
          />
          <StreamLeagueTable rows={table} />
        </div>
      </div>
    </>
  );
}
