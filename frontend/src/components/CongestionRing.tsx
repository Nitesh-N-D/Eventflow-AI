import { cn, congestionColor } from "../lib/utils";

interface Props { score: number; size?: number; showLabel?: boolean; }

export default function CongestionRing({ score, size = 80, showLabel = true }: Props) {
  const radius = 40;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;
  const strokeColor =
    score >= 80 ? "#dc2626" : score >= 60 ? "#ef4444" : score >= 35 ? "#f59e0b" : "#10b981";

  return (
    <div className="flex flex-col items-center gap-2">
      <svg width={size} height={size} viewBox="0 0 100 100" className="-rotate-90">
        <circle cx="50" cy="50" r={radius} fill="none" stroke="#1e2d45" strokeWidth="8" />
        <circle
          cx="50" cy="50" r={radius} fill="none"
          stroke={strokeColor} strokeWidth="8"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          style={{ transition: "stroke-dashoffset 1.2s ease-out" }}
        />
      </svg>
      {showLabel && (
        <div className="text-center -mt-1">
          <p className={cn("text-2xl font-bold mono", congestionColor(score))}>{score}</p>
          <p className="text-[10px] text-muted">/ 100</p>
        </div>
      )}
    </div>
  );
}
