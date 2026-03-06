"use client";

import { useEffect, useState } from "react";

import { STREAM_URL } from "@/lib/contracts";
import {
  makeStreamRuntimePath,
  makeStreamUrl,
  newestStreamTimestamp,
  resolveStreamConnection,
  STREAM_STALE_AFTER_MS,
  type StreamConnection,
  type StreamEvents,
  type StreamScoreboard,
  type StreamTablePayload,
  type StreamTableRow,
} from "@/lib/stream";

interface StreamState {
  scoreboard: StreamScoreboard | null;
  events: StreamEvents | null;
  table: StreamTableRow[];
  connection: StreamConnection;
  lastUpdated: number | null;
  sessionId: string | null;
}

const INITIAL_STATE: StreamState = {
  scoreboard: null,
  events: null,
  table: [],
  connection: "offline",
  lastUpdated: null,
  sessionId: null,
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
): { rows: StreamTableRow[]; meta: StreamTablePayload["meta"] | null } {
  if (!payload) {
    return { rows: [], meta: null };
  }
  if (Array.isArray(payload)) {
    return { rows: payload, meta: null };
  }
  return { rows: payload.rows ?? [], meta: payload.meta ?? null };
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

      const { rows: normalizedTable, meta: tableMeta } = normalizeTablePayload(table);
      const now = Date.now();

      setState((current) => {
        const nextScoreboard = scoreboard ?? current.scoreboard;
        const nextEvents = events ?? current.events;
        const nextTable = normalizedTable.length > 0 ? normalizedTable : current.table;
        const hasPayload = Boolean(nextScoreboard || nextEvents || nextTable.length > 0);
        const lastUpdated =
          newestStreamTimestamp(
            scoreboard?.updated_at,
            events?.updated_at,
            tableMeta?.updated_at,
            current.scoreboard?.updated_at,
            current.events?.updated_at,
          ) ?? current.lastUpdated;
        const connection = hasPayload
          ? resolveStreamConnection(lastUpdated, now, STREAM_STALE_AFTER_MS)
          : "offline";

        return {
          scoreboard: nextScoreboard,
          events: nextEvents,
          table: nextTable,
          connection,
          lastUpdated: hasPayload ? lastUpdated : null,
          sessionId:
            scoreboard?.session_id ??
            events?.session_id ??
            tableMeta?.session_id ??
            current.sessionId,
        };
      });
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
