"use client";

import { useReadContract, useReadContracts } from "wagmi";
import { CONTRACTS } from "@/lib/contracts";
import { PlayerCard } from "@/components/PlayerCard";
import { useState } from "react";

const PAGE_SIZE = 12;

export default function GalleryPage() {
  const [page, setPage] = useState(0);

  // ── Get total supply to know how many NFTs exist ──────────────────────
  const { data: totalSupply } = useReadContract({
    ...CONTRACTS.playerNFT,
    functionName: "totalSupply",
  });

  const total = totalSupply ? Number(totalSupply) : 0;
  const startIdx = page * PAGE_SIZE;
  const endIdx = Math.min(startIdx + PAGE_SIZE, total);
  const indices = Array.from({ length: endIdx - startIdx }, (_, i) => startIdx + i);

  // ── Get token IDs by index ────────────────────────────────────────────
  const { data: tokenIdResults } = useReadContracts({
    contracts: indices.map((idx) => ({
      ...CONTRACTS.playerNFT,
      functionName: "tokenByIndex" as const,
      args: [BigInt(idx)],
    })),
  });

  const tokenIds = (tokenIdResults ?? [])
    .map((r) => (r.status === "success" ? Number(r.result as bigint) : null))
    .filter((id): id is number => id !== null);

  // ── Get player data for each token ────────────────────────────────────
  const { data: playerResults } = useReadContracts({
    contracts: tokenIds.flatMap((id) => [
      {
        ...CONTRACTS.playerNFT,
        functionName: "getPlayer" as const,
        args: [BigInt(id)],
      },
      {
        ...CONTRACTS.playerNFT,
        functionName: "getEffectiveSkills" as const,
        args: [BigInt(id)],
      },
      {
        ...CONTRACTS.playerNFT,
        functionName: "ownerOf" as const,
        args: [BigInt(id)],
      },
    ]),
  });

  // ── Parse results ─────────────────────────────────────────────────────
  interface PlayerData {
    name: string;
    baseSkills: readonly number[];
    form: number;
    value: bigint;
    age: number;
    seasonGoals: number;
    totalGoals: number;
  }

  const players = tokenIds.map((id, i) => {
    const playerResult = playerResults?.[i * 3];
    const skillsResult = playerResults?.[i * 3 + 1];
    const ownerResult = playerResults?.[i * 3 + 2];

    const player =
      playerResult?.status === "success"
        ? (playerResult.result as unknown as PlayerData)
        : null;
    const skills =
      skillsResult?.status === "success"
        ? (skillsResult.result as unknown as number[])
        : null;
    const owner =
      ownerResult?.status === "success"
        ? (ownerResult.result as string)
        : undefined;

    if (!player || !skills) return null;

    return {
      tokenId: id,
      name: player.name,
      baseSkills: Array.from(player.baseSkills),
      effectiveSkills: Array.from(skills),
      form: Number(player.form),
      value: player.value,
      age: Number(player.age),
      seasonGoals: Number(player.seasonGoals),
      totalGoals: Number(player.totalGoals),
      owner,
    };
  });

  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <>
      <div className="page-header">
        <div className="page-title">⚽ NFT Gallery</div>
        <div className="page-subtitle">
          {total} players minted on Base · Page {page + 1} of {totalPages || 1}
        </div>
      </div>

      {total === 0 ? (
        <div className="glass-card empty-state">
          <div>No players minted yet</div>
          <div style={{ fontSize: 10, marginTop: 8, color: "var(--text-muted)" }}>
            Players will appear here after deployment and minting
          </div>
        </div>
      ) : (
        <>
          <div className="player-grid">
            {players.map(
              (p) =>
                p && (
                  <PlayerCard
                    key={p.tokenId}
                    tokenId={p.tokenId}
                    name={p.name}
                    baseSkills={p.baseSkills}
                    effectiveSkills={p.effectiveSkills}
                    form={p.form}
                    value={p.value}
                    age={p.age}
                    seasonGoals={p.seasonGoals}
                    totalGoals={p.totalGoals}
                    owner={p.owner}
                  />
                ),
            )}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div
              style={{
                display: "flex",
                justifyContent: "center",
                gap: 8,
                marginTop: 32,
              }}
            >
              <button
                className="btn"
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={page === 0}
              >
                ← Prev
              </button>
              <span
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: 13,
                  color: "var(--text-secondary)",
                  display: "flex",
                  alignItems: "center",
                  padding: "0 12px",
                }}
              >
                {page + 1} / {totalPages}
              </span>
              <button
                className="btn"
                onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                disabled={page >= totalPages - 1}
              >
                Next →
              </button>
            </div>
          )}
        </>
      )}
    </>
  );
}
