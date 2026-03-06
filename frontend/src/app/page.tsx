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
  const latestEvent = scoreboard?.story ?? events?.latest?.text ?? latestNarrativeLine(lines);
  const xgLine = events?.summary?.xg ?? findSummaryLine(lines, "xG:");
  const motmLine = events?.summary?.motm ?? findSummaryLine(lines, "⭐");

  const leader = table[0];
  const titleRace = table.slice(0, 4);
  const goals = lines.filter((line) => classifyEventLine(line) === "goal").length;
  const chances = lines.filter((line) => classifyEventLine(line) === "chance").length;
  const cards = lines.filter((line) => classifyEventLine(line) === "card").length;
  const injuries = lines.filter((line) => classifyEventLine(line) === "injury").length;

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
              <span className="story-card-label">Match Texture</span>
              <strong>{goals} goals</strong>
              <p>
                {chances} key chances, {cards} cards, and {injuries} injuries have shaped the current feed.
              </p>
            </article>

            <article className="glass-card story-card">
              <span className="story-card-label">Title Race</span>
              <strong>{titleRace.map((team) => team.team).join(" · ") || "Waiting"}</strong>
              <p>
                The front of the table should feel like a chase, not just a spreadsheet.
              </p>
            </article>

            <article className="glass-card story-card">
              <span className="story-card-label">Next Move</span>
              <strong>Keep the viewer in the match</strong>
              <p>
                <Link href="/league">Open the full league table</Link> or jump straight into the
                overlay for the best watch view.
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
