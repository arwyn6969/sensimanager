"use client";

import { useReadContract, useReadContracts, useWriteContract, useAccount } from "wagmi";
import { CONTRACTS } from "@/lib/contracts";
import { formatEther, parseEther } from "viem";
import { useState } from "react";

export default function MarketPage() {
  const { address } = useAccount();

  // ── Read listing count ────────────────────────────────────────────────
  const { data: nextListingId } = useReadContract({
    ...CONTRACTS.transferMarket,
    functionName: "nextListingId",
  });

  const { data: nextLoanId } = useReadContract({
    ...CONTRACTS.transferMarket,
    functionName: "nextLoanId",
  });

  const listingCount = nextListingId ? Number(nextListingId) : 0;
  const loanCount = nextLoanId ? Number(nextLoanId) : 0;

  // ── Read all listings ─────────────────────────────────────────────────
  const listingIds = Array.from({ length: listingCount }, (_, i) => i + 1);
  const { data: listingResults } = useReadContracts({
    contracts: listingIds.map((id) => ({
      ...CONTRACTS.transferMarket,
      functionName: "listings" as const,
      args: [BigInt(id)],
    })),
  });

  // ── Read all loans ────────────────────────────────────────────────────
  const loanIds = Array.from({ length: loanCount }, (_, i) => i + 1);
  const { data: loanResults } = useReadContracts({
    contracts: loanIds.map((id) => ({
      ...CONTRACTS.transferMarket,
      functionName: "loans" as const,
      args: [BigInt(id)],
    })),
  });

  // ── Parse listings ────────────────────────────────────────────────────
  interface ListingTuple {
    0: string;
    1: bigint;
    2: bigint;
    3: bigint;
    4: bigint;
    5: bigint;
    6: string;
    7: boolean;
  }

  const listings = listingIds
    .map((id, i) => {
      const r = listingResults?.[i];
      if (r?.status !== "success") return null;
      const d = r.result as unknown as ListingTuple;
      return {
        id,
        seller: d[0] as string,
        tokenId: Number(d[1]),
        minPrice: d[2] as bigint,
        releaseClause: d[3] as bigint,
        deadline: Number(d[4]),
        highestBid: d[5] as bigint,
        highestBidder: d[6] as string,
        active: d[7] as boolean,
      };
    })
    .filter((l): l is NonNullable<typeof l> => l !== null && l.active);

  // ── Parse loans ───────────────────────────────────────────────────────
  interface LoanTuple {
    0: string;
    1: string;
    2: bigint;
    3: bigint;
    4: bigint;
    5: boolean;
  }

  const loans = loanIds
    .map((id, i) => {
      const r = loanResults?.[i];
      if (r?.status !== "success") return null;
      const d = r.result as unknown as LoanTuple;
      return {
        id,
        lender: d[0] as string,
        borrower: d[1] as string,
        tokenId: Number(d[2]),
        recallDate: Number(d[3]),
        fee: d[4] as bigint,
        active: d[5] as boolean,
      };
    })
    .filter((l): l is NonNullable<typeof l> => l !== null && l.active);

  // ── Write hooks ───────────────────────────────────────────────────────
  const { writeContract: placeBid } = useWriteContract();
  const { writeContract: cancelListing } = useWriteContract();
  const { writeContract: resolveListing } = useWriteContract();
  const { writeContract: recallLoan } = useWriteContract();

  // ── Bid state ─────────────────────────────────────────────────────────
  const [bidAmounts, setBidAmounts] = useState<Record<number, string>>({});

  const handleBid = (listingId: number) => {
    const amount = bidAmounts[listingId];
    if (!amount) return;
    placeBid({
      ...CONTRACTS.transferMarket,
      functionName: "placeBid",
      args: [BigInt(listingId), parseEther(amount)],
    });
  };

  const now = Math.floor(Date.now() / 1000);

  return (
    <>
      <div className="page-header">
        <div className="page-title">💰 Transfer Market</div>
        <div className="page-subtitle">
          {listings.length} active listings · {loans.length} active loans
        </div>
      </div>

      {/* ── Active Listings ──────────────────────────────────────────── */}
      <div className="section-title">📋 Active Listings</div>

      {listings.length === 0 ? (
        <div className="glass-card empty-state" style={{ marginBottom: 32 }}>
          No active listings · List a player to start trading
        </div>
      ) : (
        <div className="listing-grid" style={{ marginBottom: 32 }}>
          {listings.map((l) => {
            const isExpired = now > l.deadline;
            const timeLeft = l.deadline - now;
            const hoursLeft = Math.floor(timeLeft / 3600);
            const minsLeft = Math.floor((timeLeft % 3600) / 60);
            const isSeller = address?.toLowerCase() === l.seller.toLowerCase();

            return (
              <div key={l.id} className="listing-card glass-card">
                <div className="listing-header">
                  <div>
                    <div className="listing-player">Player #{l.tokenId}</div>
                    <div
                      style={{
                        fontSize: 11,
                        color: "var(--text-muted)",
                        fontFamily: "var(--font-mono)",
                        marginTop: 4,
                      }}
                    >
                      Seller: {l.seller.slice(0, 6)}…{l.seller.slice(-4)}
                    </div>
                  </div>
                  <span className={`listing-status ${isExpired ? "expired" : "active"}`}>
                    {isExpired ? "Expired" : "Live"}
                  </span>
                </div>

                <div className="listing-details">
                  <div>
                    <div className="listing-detail-label">Min Price</div>
                    <div className="listing-detail-value">{formatEther(l.minPrice)} $SENSI</div>
                  </div>
                  <div>
                    <div className="listing-detail-label">Release Clause</div>
                    <div className="listing-detail-value">
                      {l.releaseClause > 0n ? `${formatEther(l.releaseClause)} $SENSI` : "None"}
                    </div>
                  </div>
                  <div>
                    <div className="listing-detail-label">Highest Bid</div>
                    <div className="listing-detail-value" style={{ color: "var(--accent-green)" }}>
                      {l.highestBid > 0n
                        ? `${formatEther(l.highestBid)} $SENSI`
                        : "No bids"}
                    </div>
                  </div>
                  <div>
                    <div className="listing-detail-label">Time Left</div>
                    <div
                      className="listing-detail-value"
                      style={{ color: isExpired ? "var(--accent-red)" : "var(--text-primary)" }}
                    >
                      {isExpired ? "Ended" : `${hoursLeft}h ${minsLeft}m`}
                    </div>
                  </div>
                </div>

                <div style={{ display: "flex", gap: 8 }}>
                  {!isExpired && !isSeller && (
                    <>
                      <input
                        className="input"
                        placeholder="Bid amount ($SENSI)"
                        value={bidAmounts[l.id] ?? ""}
                        onChange={(e) =>
                          setBidAmounts((prev) => ({ ...prev, [l.id]: e.target.value }))
                        }
                        style={{ flex: 1 }}
                      />
                      <button className="btn btn-primary" onClick={() => handleBid(l.id)}>
                        Bid
                      </button>
                    </>
                  )}
                  {isSeller && l.highestBidder === "0x0000000000000000000000000000000000000000" && (
                    <button
                      className="btn btn-danger"
                      onClick={() =>
                        cancelListing({
                          ...CONTRACTS.transferMarket,
                          functionName: "cancelListing",
                          args: [BigInt(l.id)],
                        })
                      }
                    >
                      Cancel
                    </button>
                  )}
                  {isExpired && l.highestBid > 0n && (
                    <button
                      className="btn btn-primary"
                      onClick={() =>
                        resolveListing({
                          ...CONTRACTS.transferMarket,
                          functionName: "resolveListing",
                          args: [BigInt(l.id)],
                        })
                      }
                    >
                      Resolve
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* ── Active Loans ─────────────────────────────────────────────── */}
      <div className="section-title">🤝 Active Loans</div>

      {loans.length === 0 ? (
        <div className="glass-card empty-state">No active loans</div>
      ) : (
        <div className="listing-grid">
          {loans.map((l) => {
            const canRecall = now >= l.recallDate || address?.toLowerCase() === l.lender.toLowerCase();
            const daysLeft = Math.max(0, Math.floor((l.recallDate - now) / 86400));

            return (
              <div key={l.id} className="listing-card glass-card">
                <div className="listing-header">
                  <div className="listing-player">Player #{l.tokenId}</div>
                  <span className="listing-status active">On Loan</span>
                </div>

                <div className="listing-details">
                  <div>
                    <div className="listing-detail-label">Lender</div>
                    <div className="listing-detail-value">
                      {l.lender.slice(0, 6)}…{l.lender.slice(-4)}
                    </div>
                  </div>
                  <div>
                    <div className="listing-detail-label">Borrower</div>
                    <div className="listing-detail-value">
                      {l.borrower.slice(0, 6)}…{l.borrower.slice(-4)}
                    </div>
                  </div>
                  <div>
                    <div className="listing-detail-label">Loan Fee</div>
                    <div className="listing-detail-value">
                      {formatEther(l.fee)} $SENSI
                    </div>
                  </div>
                  <div>
                    <div className="listing-detail-label">Days Remaining</div>
                    <div className="listing-detail-value">{daysLeft}d</div>
                  </div>
                </div>

                {canRecall && (
                  <button
                    className="btn btn-danger"
                    onClick={() =>
                      recallLoan({
                        ...CONTRACTS.transferMarket,
                        functionName: "recallLoan",
                        args: [BigInt(l.id)],
                      })
                    }
                    style={{ width: "100%" }}
                  >
                    Recall Loan
                  </button>
                )}
              </div>
            );
          })}
        </div>
      )}
    </>
  );
}
