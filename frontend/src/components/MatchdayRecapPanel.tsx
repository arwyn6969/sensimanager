"use client";

import {
  describeResultImpact,
  deriveLifecycleState,
  formatLifecycleLabel,
  formatResultSummary,
  type StreamTableRow,
  type StreamConnection,
  type StreamScoreboard,
  type StreamSession,
} from "@/lib/stream";

interface MatchdayRecapPanelProps {
  session: StreamSession | null;
  connection: StreamConnection;
  scoreboard: StreamScoreboard | null;
  table: StreamTableRow[];
}

function slateCopy(entry: NonNullable<StreamSession["matchday_slate"]>[number]): string {
  if (entry.status === "completed" && typeof entry.home_goals === "number" && typeof entry.away_goals === "number") {
    return `${entry.home_goals} - ${entry.away_goals}`;
  }
  if (entry.status === "current") {
    return "Live now";
  }
  return entry.narrative || "Upcoming";
}

export function MatchdayRecapPanel({
  session,
  connection,
  scoreboard,
  table,
}: MatchdayRecapPanelProps) {
  const lifecycle = deriveLifecycleState(session, connection, scoreboard);
  const slate = session?.matchday_slate ?? [];
  const results = session?.recent_results ?? [];

  return (
    <section className="glass-card broadcast-panel">
      <div className="panel-header">
        <div>
          <div className="panel-kicker">Matchday Flow</div>
          <h2 className="panel-title-lg">Slate And Recap</h2>
          <p className="panel-copy">
            The desk should explain the whole matchday, not just the fixture currently in frame.
          </p>
        </div>
      </div>

      <div className="summary-chip-row">
        <span className="summary-chip">{formatLifecycleLabel(lifecycle)}</span>
        {session?.matchday && <span className="summary-chip">Matchday {session.matchday}</span>}
        {session?.fixtures_in_matchday && <span className="summary-chip">{session.fixtures_in_matchday} fixtures</span>}
      </div>

      <div className="session-detail-grid">
        <article className="session-detail-card">
          <div className="leader-card-title">Current Slate</div>
          {slate.length > 0 ? (
            <ol className="session-list">
              {slate.map((entry) => (
                <li key={`${entry.matchday}-${entry.fixture_index}-${entry.home_team}`}>
                  <div className="session-list-copy">
                    <strong>{entry.home_team} vs {entry.away_team}</strong>
                    <span>{entry.home_formation ?? "4-4-2"} vs {entry.away_formation ?? "4-4-2"}</span>
                  </div>
                  <span className={`session-status-pill ${entry.status}`}>{slateCopy(entry)}</span>
                </li>
              ))}
            </ol>
          ) : (
            <div className="empty-state empty-state-left">
              Matchday fixtures will appear here once the session file is live.
            </div>
          )}
        </article>

        <article className="session-detail-card">
          <div className="leader-card-title">Completed So Far</div>
          {results.length > 0 ? (
            <ol className="session-list">
              {results.map((result) => (
                <li key={`${result.matchday}-${result.fixture_index}-${result.home_team}`}>
                  <div className="session-list-copy">
                    <strong>{formatResultSummary(result)}</strong>
                    <span>{describeResultImpact(table, result) || result.xg || "Result context pending."}</span>
                  </div>
                  <span className="session-status-pill completed">Done</span>
                </li>
              ))}
            </ol>
          ) : (
            <div className="empty-state empty-state-left">
              Completed fixtures will roll into this recap as the matchday unfolds.
            </div>
          )}
        </article>
      </div>
    </section>
  );
}
