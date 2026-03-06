"use client";

import type { StreamTableRow } from "@/lib/stream";

interface StreamLeagueTableProps {
  rows: StreamTableRow[];
  title?: string;
  subtitle?: string;
}

export function StreamLeagueTable({
  rows,
  title = "Standings",
  subtitle = "Matchday shape, title race, and relegation line.",
}: StreamLeagueTableProps) {
  return (
    <section className="glass-card broadcast-panel">
      <div className="panel-header">
        <div>
          <div className="panel-kicker">Table Pulse</div>
          <h2 className="panel-title-lg">{title}</h2>
          <p className="panel-copy">{subtitle}</p>
        </div>
      </div>

      {rows.length === 0 ? (
        <div className="empty-state empty-state-left">
          League standings will populate after the first streamed fixtures.
        </div>
      ) : (
        <table className="league-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Team</th>
              <th>P</th>
              <th>W</th>
              <th>D</th>
              <th>L</th>
              <th>GD</th>
              <th>Pts</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((team, index) => {
              const position = index + 1;
              const classes = [
                position === 1 ? "pos-1 pos-champion" : "",
                position >= rows.length - 2 ? "pos-relegate" : "",
              ]
                .filter(Boolean)
                .join(" ");

              return (
                <tr key={team.team} className={classes}>
                  <td>{position}</td>
                  <td>{team.team}</td>
                  <td>{team.played}</td>
                  <td>{team.wins}</td>
                  <td>{team.draws}</td>
                  <td>{team.losses}</td>
                  <td>{team.gd > 0 ? `+${team.gd}` : team.gd}</td>
                  <td>{team.points}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </section>
  );
}
