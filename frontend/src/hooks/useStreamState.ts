"use client";

import { useEffect, useState } from "react";

import { STREAM_URL } from "@/lib/contracts";
import {
  makeStreamRuntimePath,
  makeStreamUrl,
  type StreamEvents,
  type StreamScoreboard,
  type StreamTablePayload,
  type StreamTableRow,
} from "@/lib/stream";

interface StreamState {
  scoreboard: StreamScoreboard | null;
  events: StreamEvents | null;
  table: StreamTableRow[];
  connection: "live" | "offline";
  lastUpdated: number | null;
}

const INITIAL_STATE: StreamState = {
  scoreboard: null,
  events: null,
  table: [],
  connection: "offline",
  lastUpdated: null,
};

async function readJson<T>(path: string): Promise<T | null> {
  try {
    const response = await fetch(makeStreamUrl(STREAM_URL, path), {
      cache: "no-store",
    });
    if (!response.ok) {
      return null;
    }
    return (await response.json()) as T;
  } catch {
    return null;
  }
}

function normalizeTablePayload(
  payload: StreamTableRow[] | StreamTablePayload | null,
): StreamTableRow[] {
  if (!payload) {
    return [];
  }
  if (Array.isArray(payload)) {
    return payload;
  }
  return payload.rows ?? [];
}

export function useStreamState(intervalMs = 2000): StreamState {
  const [state, setState] = useState<StreamState>(INITIAL_STATE);

  useEffect(() => {
    let cancelled = false;

    const poll = async () => {
      const [scoreboard, events, table] = await Promise.all([
        readJson<StreamScoreboard>(makeStreamRuntimePath("scoreboard.json")),
        readJson<StreamEvents>(makeStreamRuntimePath("events.json")),
        readJson<StreamTableRow[] | StreamTablePayload>(makeStreamRuntimePath("table.json")),
      ]);

      if (cancelled) {
        return;
      }

      const normalizedTable = normalizeTablePayload(table);
      const hasPayload = Boolean(scoreboard || events || normalizedTable.length > 0);
      const now = Date.now();

      setState((current) => ({
        scoreboard: scoreboard ?? current.scoreboard,
        events: events ?? current.events,
        table: normalizedTable.length > 0 ? normalizedTable : current.table,
        connection:
          hasPayload ||
          (current.lastUpdated !== null && now - current.lastUpdated < intervalMs * 3)
            ? "live"
            : "offline",
        lastUpdated: hasPayload ? now : current.lastUpdated,
      }));
    };

    poll();
    const intervalId = window.setInterval(poll, intervalMs);

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [intervalMs]);

  return state;
}
