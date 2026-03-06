"use client";

import Link from "next/link";

import { MatchCentre } from "@/components/MatchCentre";
import { StreamCommentaryPanel } from "@/components/StreamCommentaryPanel";
import { StreamLeagueTable } from "@/components/StreamLeagueTable";
import { useStreamState } from "@/hooks/useStreamState";
import { STREAM_URL } from "@/lib/contracts";
import {
  classifyEventLine,
  findSummaryLine,
  latestNarrativeLine,
  makeStreamUrl,
  normalizeEventLines,
} from "@/lib/stream";

export default function DashboardPage() {
  const { scoreboard, events, table, connection, lastUpdated } = useStreamState();
  const lines = normalizeEventLines(events?.lines ?? []);
  const pressureNote = scoreboard?.pressure_note ?? null;
  const latestEvent = pressureNote ?? scoreboard?.story ?? events?.latest?.text ?? latestNarrativeLine(lines);
  const xgLine = events?.summary?.xg ?? findSummaryLine(lines, "xG:");
  const motmLine = events?.summary?.motm ?? findSummaryLine(lines, "⭐");

  const leader = table[0];
  const titleRace = table.slice(0, 4);
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
  const tableHeat =
    titleRace.map((team) => team.team).join(" · ") || "Waiting";

  return (
    <>
      <div className="page-header watch-header">
        <div>
          <div className="page-title">Live Match Centre</div>
          <div className="page-subtitle watch-subtitle">
            The homepage is now the show itself: live fixture, commentary pulse,
            standings pressure, and a direct path into the broadcast overlay.
          </div>
        </div>
        <div className="watch-header-chips">
          <span className={`season-badge ${connection === "live" ? "active" : "registration"}`}>
            {connection === "live" && <span className="live-dot" />}
            {connection === "live" ? "Feed Connected" : "Feed Offline"}
          </span>
          <span className="header-pill">
            {leader ? `Leader ${leader.team} • ${leader.points} pts` : "Standings waiting"}
          </span>
        </div>
      </div>

      <div className="broadcast-home-grid">
        <MatchCentre
          scoreboard={scoreboard}
          latestEvent={latestEvent}
          xgLine={xgLine}
          motmLine={motmLine}
          lastUpdated={lastUpdated}
        />

        <div className="broadcast-side-stack">
          <section className="glass-card broadcast-panel preview-panel">
            <div className="panel-header">
              <div>
                <div className="panel-kicker">Broadcast Preview</div>
                <h2 className="panel-title-lg">Overlay Window</h2>
                <p className="panel-copy">
                  Keep the overlay visible while tuning the stream runner and OBS scene.
                </p>
              </div>
            </div>

            {connection === "live" ? (
              <iframe
                className="watch-frame"
                src={makeStreamUrl(STREAM_URL, "overlay.html")}
                title="SWOS420 broadcast overlay preview"
              />
            ) : (
              <div className="watch-frame-fallback">
                <p>Overlay preview appears here when the local stream server is running.</p>
                <code>python scripts/serve_overlay.py</code>
              </div>
            )}
          </section>

          <div className="story-card-grid">
            <article className="glass-card story-card">
              <span className="story-card-label">{pressureNote ? "Pressure State" : "Match Texture"}</span>
              <strong>
                {pressureNote
                  ? `${(scoreboard?.pressure_tone ?? "live").replace(/^\w/, (char) => char.toUpperCase())} pressure`
                  : `${goals} goals`}
              </strong>
              <p>
                {pressureNote
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
              <span className="story-card-label">Table Heat</span>
              <strong>{tableHeat}</strong>
              <p>
                <Link href="/league">Open the full league table</Link> to follow the pressure building
                above and below the line.
              </p>
            </article>
          </div>
        </div>
      </div>

      <div className="watch-grid">
        <StreamCommentaryPanel
          lines={lines}
          summary={[xgLine, motmLine].filter((value): value is string => Boolean(value))}
        />
        <StreamLeagueTable rows={table} />
      </div>
    </>
  );
}
