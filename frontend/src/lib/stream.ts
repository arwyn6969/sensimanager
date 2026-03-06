export interface StreamScoreboard {
  home_team: string;
  away_team: string;
  home_goals: number;
  away_goals: number;
  minute: number;
  status: string;
  session_id?: string;
  updated_at?: string;
  competition?: string;
  season_id?: string;
  matchday?: number;
  weather?: string;
  referee_strictness?: number;
  home_formation?: string;
  away_formation?: string;
  home_style?: string;
  away_style?: string;
  match_narrative?: string;
  pressure_note?: string;
  pressure_tone?: string;
  home_xg?: number;
  away_xg?: number;
  story?: string;
  source?: string;
  leader?: string;
  leader_points?: number;
}

export interface StreamEvents {
  count: number;
  lines: string[];
  session_id?: string;
  updated_at?: string;
  events?: StreamEventEntry[];
  latest?: StreamEventEntry | null;
  summary?: StreamSummary;
}

export interface StreamTableRow {
  team: string;
  played: number;
  wins: number;
  draws: number;
  losses: number;
  gf: number;
  ga: number;
  gd: number;
  points: number;
}

export interface StreamEventEntry {
  minute: number;
  phase: string;
  text: string;
  event_type: string;
  team?: string | null;
  home_goals: number;
  away_goals: number;
}

export interface StreamSummary {
  xg?: string;
  motm?: string;
  weather?: string;
  referee_strictness?: number;
  winner?: string;
}

export interface StreamTablePayload {
  rows: StreamTableRow[];
  meta?: Record<string, string | number | undefined> & {
    session_id?: string;
    updated_at?: string;
  };
}

export const STREAM_RUNTIME_DIR = "runtime";
export const STREAM_STALE_AFTER_MS = 8_000;
export type StreamConnection = "live" | "stale" | "offline";

export function makeStreamUrl(baseUrl: string, path: string): string {
  const cleanBase = baseUrl.replace(/\/$/, "");
  const cleanPath = path.replace(/^\//, "");
  return `${cleanBase}/${cleanPath}`;
}

export function makeStreamRuntimePath(path: string): string {
  const cleanPath = path.replace(/^\//, "");
  return `${STREAM_RUNTIME_DIR}/${cleanPath}`;
}

export function normalizeEventLines(lines: string[]): string[] {
  return lines.filter((line) => line.trim());
}

export function classifyEventLine(line: string): "goal" | "card" | "injury" | "chance" | "summary" | "note" {
  const lower = line.toLowerCase();
  if (lower.includes("goal") || lower.includes("it's in") || lower.includes("⚽")) {
    return "goal";
  }
  if (
    lower.includes("card") ||
    lower.includes("booked") ||
    lower.includes("🟨") ||
    lower.includes("🟥")
  ) {
    return "card";
  }
  if (lower.includes("injur") || lower.includes("🏥")) {
    return "injury";
  }
  if (
    lower.includes("chance") ||
    lower.includes("save") ||
    lower.includes("denied") ||
    lower.includes("wide") ||
    lower.includes("bar") ||
    lower.includes("post") ||
    lower.includes("wasteful") ||
    lower.includes("opening") ||
    lower.includes("threatens") ||
    lower.includes("🧤")
  ) {
    return "chance";
  }
  if (
    lower.startsWith("xg:") ||
    lower.startsWith("⭐") ||
    lower.includes("half time") ||
    lower.includes("full time") ||
    lower.includes("ends all square")
  ) {
    return "summary";
  }
  return "note";
}

export function extractMinute(line: string): string | null {
  const match = line.match(/(\d{1,3})'\)?/);
  if (!match) return null;
  return `${match[1]}'`;
}

export function findSummaryLine(lines: string[], prefix: string): string | null {
  return [...lines].reverse().find((line) => line.startsWith(prefix)) ?? null;
}

export function latestNarrativeLine(lines: string[]): string | null {
  return (
    [...lines]
      .reverse()
      .find((line) => {
        const type = classifyEventLine(line);
        return type === "goal" || type === "injury" || type === "note";
      }) ?? null
  );
}

export function parseStreamTimestamp(value?: string | null): number | null {
  if (!value) return null;
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export function newestStreamTimestamp(...values: Array<string | null | undefined>): number | null {
  const parsed = values
    .map((value) => parseStreamTimestamp(value))
    .filter((value): value is number => value !== null);

  if (parsed.length === 0) {
    return null;
  }

  return Math.max(...parsed);
}

export function resolveStreamConnection(
  updatedAt: number | null,
  now = Date.now(),
  staleAfterMs = STREAM_STALE_AFTER_MS,
): StreamConnection {
  if (updatedAt === null) {
    return "offline";
  }
  return now - updatedAt > staleAfterMs ? "stale" : "live";
}

export function formatConnectionLabel(connection: StreamConnection): string {
  switch (connection) {
    case "live":
      return "Feed Connected";
    case "stale":
      return "Feed Stale";
    default:
      return "Feed Offline";
  }
}

export function formatFeedFreshness(
  updatedAt: number | null,
  connection: StreamConnection,
  now = Date.now(),
): string {
  if (updatedAt === null) {
    return connection === "offline" ? "waiting for stream" : "timestamp unavailable";
  }

  const ageSeconds = Math.max(0, Math.round((now - updatedAt) / 1000));
  if (connection === "stale") {
    return `stale · ${ageSeconds}s old`;
  }
  if (connection === "offline") {
    return `offline · last update ${ageSeconds}s ago`;
  }
  return ageSeconds <= 1 ? "updated just now" : `${ageSeconds}s behind`;
}

export function formatStatusLabel(status?: string): string {
  switch ((status ?? "").toLowerCase()) {
    case "live":
      return "Live Match";
    case "prematch":
      return "Kickoff Soon";
    case "halftime":
    case "ht":
      return "Half Time";
    case "fulltime":
    case "ft":
      return "Full Time";
    default:
      return "Awaiting Feed";
  }
}

export function formatClock(scoreboard?: StreamScoreboard | null): string {
  if (!scoreboard) return "00'";
  const status = scoreboard.status.toLowerCase();
  if (status === "prematch") return "PRE";
  if (status === "fulltime" || status === "ft") return "FT";
  if (status === "halftime" || status === "ht") return "HT";
  return `${scoreboard.minute}'`;
}
