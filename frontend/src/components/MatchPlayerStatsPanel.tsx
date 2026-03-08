"use client";

import type {
  StreamLeaderEntry,
  StreamLeaders,
  StreamMatchPlayerStats,
  StreamPlayerMatchStat,
} from "@/lib/stream";

interface MatchPlayerStatsPanelProps {
  stats: StreamMatchPlayerStats | null;
  homeTeam?: string;
  awayTeam?: string;
  leaders?: StreamLeaders | null;
}

function sortPlayers(players: StreamPlayerMatchStat[]): StreamPlayerMatchStat[] {
  return [...players].sort(
    (left, right) =>
      right.rating - left.rating
      || right.goals - left.goals
      || right.assists - left.assists
      || left.display_name.localeCompare(right.display_name),
  );
}

function statusLabel(player: StreamPlayerMatchStat): string {
  if (player.red_card) return "RC";
  if (player.yellow_card) return "YC";
  if (player.injured) return `INJ ${player.injury_days}d`;
  return "OK";
}

function leaderboardSignal(
  entries: StreamLeaderEntry[],
  playerName: string,
  label: string,
): string | null {
  const index = entries.findIndex((entry) => entry.display_name === playerName);
  return index >= 0 ? `#${index + 1} ${label}` : null;
}

export function MatchPlayerStatsPanel({
  stats,
  homeTeam = "Home",
  awayTeam = "Away",
  leaders,
}: MatchPlayerStatsPanelProps) {
  const homePlayers = sortPlayers(stats?.home ?? []).slice(0, 5);
  const awayPlayers = sortPlayers(stats?.away ?? []).slice(0, 5);
  const spotlight = sortPlayers([...(stats?.home ?? []), ...(stats?.away ?? [])])[0] ?? null;
  const seasonSignals = spotlight
    ? [
      leaderboardSignal(leaders?.top_scorers ?? [], spotlight.display_name, "scorer"),
      leaderboardSignal(leaders?.top_assists ?? [], spotlight.display_name, "assist chart"),
      leaderboardSignal(leaders?.form_leaders ?? [], spotlight.display_name, "form line"),
    ].filter((value): value is string => Boolean(value))
    : [];

  return (
    <section className="glass-card broadcast-panel">
      <div className="panel-header">
        <div>
          <div className="panel-kicker">Player Spotlight</div>
          <h2 className="panel-title-lg">Current Match Ratings</h2>
          <p className="panel-copy">
            The live feed should make player impact obvious, not hide it behind the final score.
          </p>
        </div>
      </div>

      {spotlight ? (
        <>
          <article className="spotlight-card">
            <span className="story-card-label">Top Performer</span>
            <strong>
              {spotlight.display_name} · {spotlight.rating.toFixed(1)}
            </strong>
            <p>
              {spotlight.goals} goals · {spotlight.assists} assists · {statusLabel(spotlight)}
              {seasonSignals.length > 0 ? ` · ${seasonSignals.join(" · ")}` : ""}
            </p>
          </article>

          <div className="player-table-grid">
            <div className="player-table-card">
              <div className="player-table-label">{homeTeam}</div>
              <table className="player-mini-table">
                <thead>
                  <tr>
                    <th>Player</th>
                    <th>Pos</th>
                    <th>Rt</th>
                    <th>G/A</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {homePlayers.map((player) => (
                    <tr key={`${homeTeam}-${player.player_id}`}>
                      <td>{player.display_name}</td>
                      <td>{player.position}</td>
                      <td>{player.rating.toFixed(1)}</td>
                      <td>{player.goals}/{player.assists}</td>
                      <td>{statusLabel(player)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="player-table-card">
              <div className="player-table-label">{awayTeam}</div>
              <table className="player-mini-table">
                <thead>
                  <tr>
                    <th>Player</th>
                    <th>Pos</th>
                    <th>Rt</th>
                    <th>G/A</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {awayPlayers.map((player) => (
                    <tr key={`${awayTeam}-${player.player_id}`}>
                      <td>{player.display_name}</td>
                      <td>{player.position}</td>
                      <td>{player.rating.toFixed(1)}</td>
                      <td>{player.goals}/{player.assists}</td>
                      <td>{statusLabel(player)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      ) : (
        <div className="empty-state empty-state-left">
          Match player stats will appear once the stream runner emits a live result payload.
        </div>
      )}
    </section>
  );
}
