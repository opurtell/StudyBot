interface ProgressBarProps {
  percent: number;
  label?: string;
}

export default function ProgressBar({ percent, label }: ProgressBarProps) {
  return (
    <div
      className="fixed top-0 left-0 right-0 h-1 bg-surface-container-highest/30 z-50"
      role="progressbar"
      aria-valuenow={Math.round(percent)}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={label ?? "Session progress"}
    >
      <div
        className="h-full bg-tertiary-fixed shadow-[0_0_8px_rgba(223,236,96,0.6)] transition-all duration-300"
        style={{ width: `${Math.min(100, Math.max(0, percent))}%` }}
      />
    </div>
  );
}
