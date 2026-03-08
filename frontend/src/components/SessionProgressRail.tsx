"use client";

import {
  describeLeaderGap,
  describeResultImpact,
  deriveLifecycleState,
  formatFixtureSummary,
  formatLifecycleLabel,
  formatResultSummary,
  type StreamTableRow,
  type StreamConnection,
  type StreamScoreboard,
  type StreamSession,
} from "@/lib/stream";

interface SessionProgressRailProps {
  session: StreamSession | null;
  connection: StreamConnection;
  scoreboard: StreamScoreboard | null;
  table: StreamTableRow[];
}

function fixtureTitle(fixture?: StreamSession["current_fixture"] | StreamSession["next_fixture"]): string {
  if (!fixture) {
    return "Waiting";
  }
  return `${fixture.home_team} vs ${fixture.away_team}`;
}

function liveStateCopy(
  state: ReturnType<typeof deriveLifecycleState>,
  table: StreamTableRow[],
  result: StreamSession["last_result"],
): string {
  switch (state) {
    case "between_matches":
      return "The last result is in and the next fixture is being queued.";
    case "matchday_complete":
      return describeResultImpact(table, result, state);
    case "season_complete":
      return describeResultImpact(table, result, state);
    case "stale":
      return "The session feed is stale. Restart the runner to resume live play.";
    case "offline":
      return "Start the runner to turn the session rail back on.";
    default:
      return "The show is live and the next swing in the table is already forming.";
  }
}

export function SessionProgressRail({
  session,
  connection,
  scoreboard,
  table,
}: SessionProgressRailProps) {
  const lifecycle = deriveLifecycleState(session, connection, scoreboard);
  const currentFixture = session?.current_fixture ?? null;
  const lastResult = session?.last_result ?? null;
  const nextFixture = session?.next_fixture ?? null;
  const leaderContext = describeLeaderGap(table);
  const progressLabel = session?.matchday
    ? `Matchday ${session.matchday}${session.fixture_index && session.fixtures_in_matchday ? ` · ${session.fixture_index}/${session.fixtures_in_matchday}` : ""}`
    : "Session progress pending";

  return (
    <section className="glass-card session-panel">
      <div className="panel-header">
        <div>
          <div className="panel-kicker">Session Flow</div>
          <h2 className="panel-title-lg">What Changed, What&apos;s Next</h2>
          <p className="panel-copy">
            The watcher should always know where the show is, what just landed, and which fixture is next.
          </p>
        </div>
      </div>

      <div className="summary-chip-row">
        <span className="summary-chip">{formatLifecycleLabel(lifecycle)}</span>
        <span className="summary-chip">{progressLabel}</span>
        {session?.season_id && <span className="summary-chip">Season {session.season_id}</span>}
      </div>

      <div className="session-card-grid">
        <article className="session-card">
          <span className="story-card-label">Now</span>
          <strong>{currentFixture ? fixtureTitle(currentFixture) : formatLifecycleLabel(lifecycle)}</strong>
          <p>
            {currentFixture
              ? currentFixture.pressure_note || currentFixture.narrative || formatFixtureSummary(currentFixture)
              : liveStateCopy(lifecycle, table, lastResult)}
          </p>
        </article>

        <article className="session-card emphasis-card">
          <span className="story-card-label">Just Happened</span>
          <strong>{lastResult ? formatResultSummary(lastResult) : "No Result Yet"}</strong>
          <p>
            {lastResult
              ? describeResultImpact(table, lastResult, lifecycle)
              : "The session recap will start filling in as soon as the first fixture closes."}
          </p>
        </article>

        <article className="session-card">
          <span className="story-card-label">Up Next</span>
          <strong>{fixtureTitle(nextFixture)}</strong>
          <p>
            {nextFixture
              ? nextFixture.pressure_note || nextFixture.narrative || formatFixtureSummary(nextFixture)
              : lifecycle === "season_complete"
                ? leaderContext
                : "No next fixture is queued yet. If the season is complete, the table is the final word."}
          </p>
        </article>
      </div>
    </section>
  );
}
