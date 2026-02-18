"use client";

import { useReadContract } from "wagmi";
import { formatEther } from "viem";
import { CONTRACTS, SEASON_STATES } from "@/lib/contracts";
import { CommentaryFeed } from "@/components/CommentaryFeed";

export default function DashboardPage() {
  // ── Read chain data ──────────────────────────────────────────────────
  const { data: totalSupply } = useReadContract({
    ...CONTRACTS.sensiToken,
    functionName: "totalSupply",
  });

  const { data: genesisSupply } = useReadContract({
    ...CONTRACTS.sensiToken,
    functionName: "GENESIS_SUPPLY",
  });

  const { data: nftSupply } = useReadContract({
    ...CONTRACTS.playerNFT,
    functionName: "totalSupply",
  });

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

  const { data: nextListingId } = useReadContract({
    ...CONTRACTS.transferMarket,
    functionName: "nextListingId",
  });

  // ── Format values ────────────────────────────────────────────────────
  const totalSensi = totalSupply ? formatEther(totalSupply) : "—";
  const genesisSensi = genesisSupply ? formatEther(genesisSupply) : "—";
  const burned =
    totalSupply && genesisSupply && totalSupply < genesisSupply
      ? formatEther(genesisSupply - totalSupply)
      : "0";

  const formatBigNumber = (n: string) => {
    const num = parseFloat(n);
    if (isNaN(num)) return "—";
    if (num >= 1_000_000_000) return `${(num / 1_000_000_000).toFixed(2)}B`;
    if (num >= 1_000_000) return `${(num / 1_000_000).toFixed(2)}M`;
    if (num >= 1_000) return `${(num / 1_000).toFixed(1)}K`;
    return num.toFixed(0);
  };

  const stateIndex = seasonState !== undefined ? Number(seasonState) : 0;
  const stateLabel = SEASON_STATES[stateIndex] ?? "Unknown";
  const stateClass = stateLabel.toLowerCase();

  return (
    <>
      {/* ── Hero ──────────────────────────────────────────────────────── */}
      <div className="hero glass-card">
        <div className="hero-title">SWOS420</div>
        <div className="hero-subtitle">
          The most addictive football experience onchain. Own players as NFTs,
          earn $SENSI from wages &amp; match rewards, trade on the decentralized
          transfer market. Built on Base.
        </div>
        <div style={{ marginTop: 20, display: "flex", gap: 12, alignItems: "center" }}>
          <span className={`season-badge ${stateClass}`}>
            {stateClass === "active" && <span className="live-dot" />}
            Season {currentSeason?.toString() ?? "—"} · {stateLabel}
          </span>
          <span
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 13,
              color: "var(--text-secondary)",
            }}
          >
            Matchday {matchday?.toString() ?? "0"}
          </span>
        </div>
      </div>

      {/* ── Stats Grid ────────────────────────────────────────────────── */}
      <div className="stat-grid">
        <div className="stat-card glass-card">
          <div className="stat-label">$SENSI Supply</div>
          <div className="stat-value green">{formatBigNumber(totalSensi)}</div>
        </div>
        <div className="stat-card glass-card">
          <div className="stat-label">Genesis Minted</div>
          <div className="stat-value blue">{formatBigNumber(genesisSensi)}</div>
        </div>
        <div className="stat-card glass-card">
          <div className="stat-label">$SENSI Burned</div>
          <div className="stat-value" style={{ color: "var(--accent-red)" }}>
            {formatBigNumber(burned)}
          </div>
        </div>
        <div className="stat-card glass-card">
          <div className="stat-label">Player NFTs</div>
          <div className="stat-value gold">{nftSupply?.toString() ?? "—"}</div>
        </div>
        <div className="stat-card glass-card">
          <div className="stat-label">Market Listings</div>
          <div className="stat-value">
            {nextListingId ? (Number(nextListingId) - 1).toString() : "0"}
          </div>
        </div>
      </div>

      {/* ── Two Column: Commentary + Economy Info ──────────────────────── */}
      <div className="two-col">
        <CommentaryFeed />

        <div className="glass-card" style={{ padding: "20px 24px" }}>
          <div className="section-title">💎 Economy Rules</div>
          <div
            style={{
              display: "grid",
              gap: 12,
              fontSize: 13,
              lineHeight: 1.8,
              color: "var(--text-secondary)",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span>Win Reward</span>
              <span style={{ fontFamily: "var(--font-mono)", color: "var(--accent-green)" }}>
                100 $SENSI
              </span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span>Draw Reward</span>
              <span style={{ fontFamily: "var(--font-mono)", color: "var(--accent-blue)" }}>
                50 $SENSI
              </span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span>League Winner Bonus</span>
              <span style={{ fontFamily: "var(--font-mono)", color: "var(--accent-gold)" }}>
                100,000 $SENSI
              </span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span>Top Scorer Bonus</span>
              <span style={{ fontFamily: "var(--font-mono)", color: "var(--accent-gold)" }}>
                10,000 $SENSI
              </span>
            </div>
            <div
              style={{
                borderTop: "1px solid var(--glass-border)",
                paddingTop: 12,
                marginTop: 4,
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span>Wage Split (Owner)</span>
                <span style={{ fontFamily: "var(--font-mono)", fontWeight: 700 }}>90%</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span>Burn Rate</span>
                <span
                  style={{
                    fontFamily: "var(--font-mono)",
                    color: "var(--accent-red)",
                    fontWeight: 700,
                  }}
                >
                  5%
                </span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span>Treasury</span>
                <span style={{ fontFamily: "var(--font-mono)", fontWeight: 700 }}>5%</span>
              </div>
            </div>
            <div
              style={{
                borderTop: "1px solid var(--glass-border)",
                paddingTop: 12,
                marginTop: 4,
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span>Transfer Fee</span>
                <span style={{ fontFamily: "var(--font-mono)", fontWeight: 700 }}>10%</span>
              </div>
              <div
                style={{
                  fontSize: 11,
                  color: "var(--text-muted)",
                  marginTop: 4,
                }}
              >
                5% burned + 5% treasury on every trade
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
