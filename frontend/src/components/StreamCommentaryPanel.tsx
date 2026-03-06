"use client";

import { classifyEventLine, extractMinute } from "@/lib/stream";

interface StreamCommentaryPanelProps {
  lines: string[];
  title?: string;
  summary?: string[];
  emptyCopy?: string;
  limit?: number;
}

export function StreamCommentaryPanel({
  lines,
  title = "Match Commentary",
  summary = [],
  emptyCopy = "Commentary will appear when the stream runner starts feeding events.",
  limit = 10,
}: StreamCommentaryPanelProps) {
  const visibleLines = lines.slice(-limit).reverse();

  return (
    <section className="glass-card broadcast-panel">
      <div className="panel-header">
        <div>
          <div className="panel-kicker">Live Feed</div>
          <h2 className="panel-title-lg">{title}</h2>
        </div>
      </div>

      {summary.length > 0 && (
        <div className="summary-chip-row">
          {summary.map((item) => (
            <span key={item} className="summary-chip">
              {item}
            </span>
          ))}
        </div>
      )}

      {visibleLines.length === 0 ? (
        <div className="empty-state empty-state-left">{emptyCopy}</div>
      ) : (
        <div className="broadcast-event-list">
          {visibleLines.map((line, index) => {
            const tone = classifyEventLine(line);
            const minute = extractMinute(line);

            return (
              <article
                key={`${line}-${index}`}
                className={`broadcast-event-card tone-${tone}`}
              >
                <div className="broadcast-event-badge">
                  {minute ?? (index === 0 ? "Now" : tone.toUpperCase())}
                </div>
                <div className="broadcast-event-copy">{line}</div>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
