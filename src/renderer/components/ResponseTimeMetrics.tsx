interface ResponseTimeMetricsProps {
  elapsedSeconds: number;
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

function delayLabel(seconds: number): { text: string; className: string } {
  if (seconds <= 30) {
    return { text: "Under 30 seconds", className: "bg-primary/20 text-primary" };
  }
  if (seconds <= 90) {
    return { text: "30–90 seconds", className: "bg-secondary/20 text-secondary" };
  }
  return { text: "Over 90 seconds", className: "bg-rose-300/20 text-rose-700" };
}

export default function ResponseTimeMetrics({ elapsedSeconds }: ResponseTimeMetricsProps) {
  const delay = delayLabel(elapsedSeconds);

  return (
    <div className="flex items-center gap-6 mb-8">
      <div>
        <p className="font-mono text-[10px] text-on-surface-variant mb-1">
          RESPONSE TIME
        </p>
        <p className="font-headline text-headline-md text-on-surface">
          {formatTime(elapsedSeconds)}
        </p>
      </div>
      <span className={`inline-block px-3 py-1 font-label text-label-sm uppercase tracking-wider ${delay.className}`}>
        {delay.text}
      </span>
      {elapsedSeconds > 90 && (
        <p className="font-body text-body-md text-on-surface-variant italic">
          Response time exceeded 90 seconds.
        </p>
      )}
    </div>
  );
}
