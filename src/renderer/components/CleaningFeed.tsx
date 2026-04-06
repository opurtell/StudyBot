interface CleaningFeedItem {
  status: "active" | "complete" | "waiting";
  label: string;
  preview: string;
  detail?: string | null;
}

interface CleaningFeedProps {
  items: CleaningFeedItem[];
  visible: boolean;
  onToggle: () => void;
}

function dotColour(status: CleaningFeedItem["status"]): string {
  switch (status) {
    case "active": return "bg-secondary";
    case "complete": return "bg-primary";
    case "waiting": return "bg-on-surface-variant/30";
  }
}

export default function CleaningFeed({ items, visible, onToggle }: CleaningFeedProps) {
  return (
    <div className="bg-surface-container-low border border-outline-variant/10 p-6">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <span className="material-symbols-outlined text-sm text-on-surface-variant">
            auto_fix
          </span>
          <h3 className="font-label text-label-sm text-on-surface-variant uppercase">
            OCR Cleaning Status
          </h3>
        </div>
        <button
          onClick={onToggle}
          className="text-on-surface-variant hover:text-primary transition-colors"
          aria-label={visible ? "Hide cleaning feed" : "Show cleaning feed"}
        >
          <span className="material-symbols-outlined text-sm">
            {visible ? "visibility" : "visibility_off"}
          </span>
        </button>
      </div>
      {visible && (
        <div className="space-y-6">
          {items.map((item, i) => (
            <div key={i} className="space-y-2">
              <div className="flex items-center gap-2">
                <div className={`w-2 h-2 rounded-full ${dotColour(item.status)}`} />
                <span className="font-label text-label-sm text-on-surface-variant">{item.label}</span>
              </div>
              <p className="font-body text-body-md text-on-surface-variant italic pl-4">
                {item.preview}
              </p>
              {item.detail && (
                <p className="font-mono text-[10px] text-on-surface-variant pl-4">
                  {item.detail}
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
