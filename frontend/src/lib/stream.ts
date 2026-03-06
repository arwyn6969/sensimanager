export interface StreamScoreboard {
  home_team: string;
  away_team: string;
  home_goals: number;
  away_goals: number;
  minute: number;
  status: string;
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
  meta?: Record<string, string | number>;
}

export const STREAM_RUNTIME_DIR = "runtime";

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
