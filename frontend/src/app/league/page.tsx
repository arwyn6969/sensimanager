"use client";

import { useReadContract, useReadContracts } from "wagmi";
import { CONTRACTS, SEASON_STATES } from "@/lib/contracts";
import { CommentaryFeed } from "@/components/CommentaryFeed";

export default function LeaguePage() {
  // ── Read season state ─────────────────────────────────────────────────
  const { data: currentSeason } = useReadContract({
    ...CONTRACTS.leagueManager,
    functionName: "currentSeason",
  });

  const { data: seasonState } = useReadContract({
    ...CONTRACTS.leagueManager,
    functionName: "seasonState",
  });

  const { data: matchday } = useReadContract({
    ...CONTRACTS.leagueManager,
    functionName: "matchday",
  });

  // ── Read standings (list of team codes) ───────────────────────────────
  const season = currentSeason ?? 1n;
  const { data: teamCodes } = useReadContract({
    ...CONTRACTS.leagueManager,
    functionName: "getStandings",
    args: [season],
  });

  // ── Read each team's data ─────────────────────────────────────────────
  const codes = (teamCodes as `0x${string}`[]) ?? [];

  const { data: teamResults } = useReadContracts({
    contracts: codes.map((code) => ({
      ...CONTRACTS.leagueManager,
      functionName: "getTeam" as const,
      args: [season, code] as const,
    })),
  });

  // ── Parse and sort teams ──────────────────────────────────────────────
  interface TeamData {
    manager: string;
    playerTokenIds: bigint[];
    points: bigint;
    goalsFor: bigint;
    goalsAgainst: bigint;
    registered: boolean;
  }

  const teams = codes
    .map((code, i) => {
      const r = teamResults?.[i];
      if (r?.status !== "success") return null;
      const d = r.result as unknown as TeamData;
      const pts = Number(d.points);
      const gf = Number(d.goalsFor);
      const ga = Number(d.goalsAgainst);

      // Decode team code from bytes32 → string
      let teamName: string;
      try {
        // bytes32 → trim trailing zeros → UTF-8
        const hex = code.replace(/0+$/, "");
        teamName = hex.length > 2
          ? new TextDecoder().decode(
              new Uint8Array(
                (hex.slice(2).match(/.{2}/g) ?? []).map((b) => parseInt(b, 16)),
              ),
            )
          : code.slice(0, 10);
      } catch {
        teamName = code.slice(0, 10);
      }

      return {
        code,
        name: teamName,
        manager: d.manager,
        players: d.playerTokenIds.length,
        points: pts,
        goalsFor: gf,
        goalsAgainst: ga,
        gd: gf - ga,
        registered: d.registered,
      };
    })
    .filter((t): t is NonNullable<typeof t> => t !== null && t.registered)
    .sort((a, b) => {
      if (b.points !== a.points) return b.points - a.points;
      if (b.gd !== a.gd) return b.gd - a.gd;
      return b.goalsFor - a.goalsFor;
    });

  const stateIndex = seasonState !== undefined ? Number(seasonState) : 0;
  const stateLabel = SEASON_STATES[stateIndex] ?? "Unknown";
  const stateClass = stateLabel.toLowerCase();

  return (
    <>
      <div className="page-header">
        <div className="page-title">🏆 League Table</div>
        <div className="page-subtitle" style={{ display: "flex", gap: 16, alignItems: "center" }}>
          <span className={`season-badge ${stateClass}`}>
            {stateClass === "active" && <span className="live-dot" />}
            Season {currentSeason?.toString() ?? "—"} · {stateLabel}
          </span>
          <span style={{ fontFamily: "var(--font-mono)", color: "var(--text-muted)" }}>
            Matchday {matchday?.toString() ?? "0"}
          </span>
        </div>
      </div>

      <div className="two-col">
        {/* ── Standings Table ───────────────────────────────────────────── */}
        <div className="glass-card" style={{ padding: "20px 24px" }}>
          <div className="section-title">📊 Standings</div>

          {teams.length === 0 ? (
            <div className="empty-state">
              No teams registered yet
            </div>
          ) : (
            <table className="league-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Team</th>
                  <th>P</th>
                  <th>GF</th>
                  <th>GA</th>
                  <th>GD</th>
                  <th>Pts</th>
                </tr>
              </thead>
              <tbody>
                {teams.map((t, i) => {
                  const pos = i + 1;
                  let cls = "";
                  if (pos === 1) cls = "pos-1 pos-champion";
                  else if (pos > teams.length - 3 && teams.length > 4) cls = "pos-relegate";

                  return (
                    <tr key={t.code} className={cls}>
                      <td>{pos}</td>
                      <td title={t.manager}>
                        {t.name.length > 16 ? t.name.slice(0, 15) + "…" : t.name}
                      </td>
                      <td>{t.players}</td>
                      <td>{t.goalsFor}</td>
                      <td>{t.goalsAgainst}</td>
                      <td>{t.gd > 0 ? `+${t.gd}` : t.gd}</td>
                      <td>{t.points}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>

        {/* ── Commentary Feed ───────────────────────────────────────────── */}
        <CommentaryFeed />
      </div>

      {/* ── Team Details (expandable in future) ──────────────────────── */}
      {teams.length > 0 && (
        <div style={{ marginTop: 32 }}>
          <div className="section-title">👥 Registered Managers</div>
          <div className="stat-grid">
            {teams.map((t) => (
              <div key={t.code} className="stat-card glass-card">
                <div className="stat-label">{t.name}</div>
                <div
                  style={{
                    fontFamily: "var(--font-mono)",
                    fontSize: 12,
                    color: "var(--text-secondary)",
                    marginTop: 4,
                  }}
                >
                  {t.manager.slice(0, 6)}…{t.manager.slice(-4)}
                </div>
                <div
                  style={{
                    fontFamily: "var(--font-mono)",
                    fontSize: 11,
                    color: "var(--text-muted)",
                    marginTop: 8,
                  }}
                >
                  {t.players} players · {t.points} pts · GD {t.gd > 0 ? `+${t.gd}` : t.gd}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </>
  );
}
