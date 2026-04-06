interface MasteryIndicatorProps {
  percentage: number;
  label?: string;
}

function getStatusColour(percentage: number): string {
  if (percentage >= 85) return "bg-status-success";
  if (percentage >= 60) return "bg-status-caution";
  return "bg-status-critical";
}

function getGlowColour(percentage: number): string {
  if (percentage >= 85) return "shadow-[0_0_8px_rgba(16,185,129,0.4)]";
  return "";
}

export default function MasteryIndicator({
  percentage,
  label,
}: MasteryIndicatorProps) {
  const clamped = Math.max(0, Math.min(100, percentage));
  const statusColour = getStatusColour(clamped);
  const glowColour = getGlowColour(clamped);

  return (
    <div className="space-y-1">
      {label && (
        <p className="font-label text-label-sm text-on-surface-variant">
          {label}
        </p>
      )}
      <div className="flex items-center gap-2">
        <div
          className={`w-2 h-2 rounded-full ${statusColour} ${glowColour}`}
        />
        <span className="font-label text-label-sm text-on-surface-variant">
          {clamped}% Mastery
        </span>
      </div>
      <div className="h-1 w-full bg-outline-variant/20">
        <div
          className={`h-full ${statusColour} transition-all duration-500`}
          style={{ width: `${clamped}%` }}
        />
      </div>
    </div>
  );
}