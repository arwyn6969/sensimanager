import { SWOSPlayerNFTABI } from "./abis/SWOSPlayerNFT";
import { SENSITokenABI } from "./abis/SENSIToken";
import { TransferMarketABI } from "./abis/TransferMarket";
import { LeagueManagerABI } from "./abis/LeagueManager";

// ── Contract Addresses (set via env vars or defaults) ──────────────────
// In production, set NEXT_PUBLIC_PLAYER_NFT_ADDRESS etc. in .env.local
// These are placeholder zero-addresses until deployment
const ZERO = "0x0000000000000000000000000000000000000000" as const;

export const CONTRACTS = {
  playerNFT: {
    address: (process.env.NEXT_PUBLIC_PLAYER_NFT_ADDRESS ?? ZERO) as `0x${string}`,
    abi: SWOSPlayerNFTABI,
  },
  sensiToken: {
    address: (process.env.NEXT_PUBLIC_SENSI_TOKEN_ADDRESS ?? ZERO) as `0x${string}`,
    abi: SENSITokenABI,
  },
  transferMarket: {
    address: (process.env.NEXT_PUBLIC_TRANSFER_MARKET_ADDRESS ?? ZERO) as `0x${string}`,
    abi: TransferMarketABI,
  },
  leagueManager: {
    address: (process.env.NEXT_PUBLIC_LEAGUE_MANAGER_ADDRESS ?? ZERO) as `0x${string}`,
    abi: LeagueManagerABI,
  },
} as const;

// ── Skill Labels (canonical SWOS order) ────────────────────────────────
export const SKILL_LABELS = ["PA", "VE", "HE", "TA", "CO", "SP", "FI"] as const;
export const SKILL_FULL_NAMES = [
  "Passing", "Velocity", "Heading", "Tackling", "Control", "Speed", "Finishing",
] as const;

// ── Season State Enum ──────────────────────────────────────────────────
export const SEASON_STATES = ["Registration", "Active", "Settled"] as const;

// ── Commentary Endpoint ────────────────────────────────────────────────
export const COMMENTARY_URL = process.env.NEXT_PUBLIC_COMMENTARY_URL ?? "http://localhost:8420";

export { SWOSPlayerNFTABI, SENSITokenABI, TransferMarketABI, LeagueManagerABI };
