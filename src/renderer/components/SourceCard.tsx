import AdaptiveText from "./AdaptiveText";

interface SourceCardProps {
  name: string;
  type: string;
  id: string;
  progress: number;
  statusText: string;
  detail: string;
}

function progressColour(pct: number): string {
  if (pct >= 100) return "bg-primary";
  if (pct >= 50) return "bg-secondary";
  return "bg-tertiary-fixed";
}

export default function SourceCard({ name, type, id, progress, statusText, detail }: SourceCardProps) {
  return (
    <div className="bg-surface-container-lowest p-6 hover:bg-white transition-colors">
      <div className="flex items-start gap-4">
        <div className="w-12 h-16 bg-surface-container-high flex items-center justify-center shrink-0">
          <span className="material-symbols-outlined text-primary">description</span>
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between mb-1">
            <span className="font-label text-[9px] uppercase tracking-widest text-on-surface-variant">
              {type}
            </span>
            <span className="font-mono text-[10px] text-on-surface-variant">{id}</span>
          </div>
          <AdaptiveText
            text={name}
            variant="title"
            className="text-on-surface"
          />
          <div className="h-1 w-full bg-outline-variant/20 mt-3 mb-2">
            <div
              className={`h-full ${progressColour(progress)} transition-all duration-500`}
              style={{ width: `${progress}%` }}
            />
          </div>
          <div className="flex items-center justify-between">
            <span className="font-mono text-[10px] text-on-surface-variant">{statusText}</span>
            <span className="font-mono text-[10px] text-on-surface-variant">{detail}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
