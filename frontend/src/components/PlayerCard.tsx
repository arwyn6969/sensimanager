import { SkillRadar } from "./SkillRadar";
import { formatEther } from "viem";

interface PlayerCardProps {
  tokenId: number;
  name: string;
  baseSkills: number[];
  effectiveSkills: number[];
  form: number;
  value: bigint;
  age: number;
  seasonGoals: number;
  totalGoals: number;
  owner?: string;
}

export function PlayerCard({
  tokenId,
  name,
  effectiveSkills,
  form,
  value,
  age,
  seasonGoals,
  totalGoals,
  owner,
}: PlayerCardProps) {
  const formPct = ((form + 100) / 200) * 100; // Normalize -100..+100 to 0..100%
  const formLabel = form >= 0 ? `+${form}` : `${form}`;
  const isPositive = form >= 0;

  // Format value in a readable way
  const valueEth = parseFloat(formatEther(value));
  const valueDisplay =
    valueEth >= 1_000_000
      ? `${(valueEth / 1_000_000).toFixed(1)}M`
      : valueEth >= 1_000
        ? `${(valueEth / 1_000).toFixed(1)}K`
        : valueEth.toFixed(0);

  return (
    <div className="player-card glass-card">
      <div className="player-name">{name}</div>
      <div className="player-meta">
        <span className="badge">#{tokenId}</span>
        <span className="badge">Age {age}</span>
        {owner && (
          <span className="badge" title={owner}>
            {owner.slice(0, 6)}…{owner.slice(-4)}
          </span>
        )}
      </div>

      <div className="player-stats-row">
        <SkillRadar skills={effectiveSkills} />
        <div style={{ flex: 1 }}>
          {effectiveSkills.map((s, i) => (
            <div
              key={i}
              style={{
                display: "flex",
                justifyContent: "space-between",
                fontSize: 12,
                fontFamily: "var(--font-mono)",
                color: "var(--text-secondary)",
                padding: "2px 0",
              }}
            >
              <span style={{ color: "var(--text-muted)", letterSpacing: 1 }}>
                {["PA", "VE", "HE", "TA", "CO", "SP", "FI"][i]}
              </span>
              <span
                style={{
                  color: s >= 12 ? "var(--accent-green)" : s >= 8 ? "var(--text-primary)" : "var(--accent-red)",
                  fontWeight: 700,
                }}
              >
                {s}
              </span>
            </div>
          ))}
        </div>
      </div>

      <div className="form-bar-container">
        <div className="form-bar-label">
          <span>Form</span>
          <span style={{ color: isPositive ? "var(--accent-green)" : "var(--accent-red)" }}>
            {formLabel}
          </span>
        </div>
        <div className="form-bar">
          <div
            className={`form-bar-fill ${isPositive ? "positive" : "negative"}`}
            style={{ width: `${formPct}%` }}
          />
        </div>
      </div>

      <div className="value-display">
        <span className="value-amount">{valueDisplay} $SENSI</span>
        <span className="goals-badge">
          ⚽ {seasonGoals} (Total: {totalGoals})
        </span>
      </div>
    </div>
  );
}
