import { SKILL_LABELS } from "@/lib/contracts";

interface SkillRadarProps {
  skills: number[];
  maxValue?: number;
  size?: number;
}

/**
 * Pure SVG 7-axis radar chart for SWOS player skills.
 * Each axis: PA, VE, HE, TA, CO, SP, FI
 */
export function SkillRadar({ skills, maxValue = 15, size = 140 }: SkillRadarProps) {
  const cx = size / 2;
  const cy = size / 2;
  const radius = size / 2 - 16;
  const numAxes = 7;
  const angleStep = (2 * Math.PI) / numAxes;
  const startAngle = -Math.PI / 2; // Start from top

  // Generate grid rings
  const rings = [0.25, 0.5, 0.75, 1.0];

  // Calculate point positions for a given set of values
  const getPolygonPoints = (values: number[]) =>
    values
      .map((v, i) => {
        const angle = startAngle + i * angleStep;
        const r = (v / maxValue) * radius;
        return `${cx + r * Math.cos(angle)},${cy + r * Math.sin(angle)}`;
      })
      .join(" ");

  // Axis line endpoints
  const axisLines = Array.from({ length: numAxes }, (_, i) => {
    const angle = startAngle + i * angleStep;
    return {
      x: cx + radius * Math.cos(angle),
      y: cy + radius * Math.sin(angle),
      labelX: cx + (radius + 12) * Math.cos(angle),
      labelY: cy + (radius + 12) * Math.sin(angle),
    };
  });

  return (
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      style={{ overflow: "visible" }}
    >
      {/* Grid rings */}
      {rings.map((ring) => (
        <polygon
          key={ring}
          points={Array.from({ length: numAxes }, (_, i) => {
            const angle = startAngle + i * angleStep;
            const r = ring * radius;
            return `${cx + r * Math.cos(angle)},${cy + r * Math.sin(angle)}`;
          }).join(" ")}
          fill="none"
          stroke="rgba(255,255,255,0.06)"
          strokeWidth="1"
        />
      ))}

      {/* Axis lines */}
      {axisLines.map((axis, i) => (
        <line
          key={i}
          x1={cx}
          y1={cy}
          x2={axis.x}
          y2={axis.y}
          stroke="rgba(255,255,255,0.06)"
          strokeWidth="1"
        />
      ))}

      {/* Data polygon */}
      <polygon
        points={getPolygonPoints(skills)}
        fill="rgba(0, 230, 118, 0.15)"
        stroke="#00e676"
        strokeWidth="2"
        strokeLinejoin="round"
      />

      {/* Data points */}
      {skills.map((v, i) => {
        const angle = startAngle + i * angleStep;
        const r = (v / maxValue) * radius;
        return (
          <circle
            key={i}
            cx={cx + r * Math.cos(angle)}
            cy={cy + r * Math.sin(angle)}
            r="3"
            fill="#00e676"
            stroke="#0a0c14"
            strokeWidth="1.5"
          />
        );
      })}

      {/* Labels */}
      {axisLines.map((axis, i) => (
        <text
          key={i}
          x={axis.labelX}
          y={axis.labelY}
          textAnchor="middle"
          dominantBaseline="middle"
          fill="rgba(255,255,255,0.4)"
          fontSize="9"
          fontFamily="JetBrains Mono, monospace"
          fontWeight="700"
        >
          {SKILL_LABELS[i]}
        </text>
      ))}
    </svg>
  );
}
