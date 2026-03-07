"use client";

import type { StreamLeaderEntry, StreamLeaders } from "@/lib/stream";

interface SeasonLeadersPanelProps {
  leaders: StreamLeaders | null;
}

interface LeaderSection {
  id: string;
  title: string;
  entries: StreamLeaderEntry[];
  suffix?: string;
  signed?: boolean;
}

function formatLeaderValue(
  value: number,
  options?: {
    suffix?: string;
    signed?: boolean;
  },
): string {
  const suffix = options?.suffix ?? "";
  const signed = options?.signed ?? false;
  const prefix = signed && value > 0 ? "+" : "";
  return `${prefix}${value}${suffix}`;
}

export function SeasonLeadersPanel({ leaders }: SeasonLeadersPanelProps) {
  const sections: LeaderSection[] = [
    {
      id: "goals",
      title: "Top Scorers",
      entries: leaders?.top_scorers ?? [],
    },
    {
      id: "assists",
      title: "Assists",
      entries: leaders?.top_assists ?? [],
    },
    {
      id: "clean-sheets",
      title: "Clean Sheets",
      entries: leaders?.top_clean_sheets ?? [],
    },
    {
      id: "form",
      title: "Form Leaders",
      entries: leaders?.form_leaders ?? [],
      signed: true,
    },
  ];

  const hasEntries = sections.some((section) => section.entries.length > 0);

  return (
    <section className="glass-card broadcast-panel">
      <div className="panel-header">
        <div>
          <div className="panel-kicker">Season Leaders</div>
          <h2 className="panel-title-lg">Who Is Driving The Campaign</h2>
          <p className="panel-copy">
            This desk should explain which players are bending the season, not just which clubs sit on top.
          </p>
        </div>
      </div>

      {hasEntries ? (
        <div className="leader-grid">
          {sections.map((section) => (
            <article key={section.id} className="leader-card">
              <div className="leader-card-title">{section.title}</div>
              {section.entries.length > 0 ? (
                <ol className="leader-list">
                  {section.entries.map((entry, index) => (
                    <li key={`${section.id}-${entry.display_name}-${entry.team}`}>
                      <span className="leader-rank">{index + 1}</span>
                      <div className="leader-copy">
                        <strong>{entry.display_name}</strong>
                        <span>{entry.team} · {entry.position}</span>
                      </div>
                      <span className="leader-value">
                        {formatLeaderValue(entry.value, {
                          suffix: section.suffix,
                          signed: section.signed,
                        })}
                      </span>
                    </li>
                  ))}
                </ol>
              ) : (
                <div className="empty-state empty-state-left">
                  No signal yet for this leaderboard.
                </div>
              )}
            </article>
          ))}
        </div>
      ) : (
        <div className="empty-state empty-state-left">
          Season leader tables will populate after the first streamed fixtures settle.
        </div>
      )}
    </section>
  );
}
