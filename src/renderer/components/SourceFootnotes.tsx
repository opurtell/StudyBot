interface SourceFootnotesProps {
  citations: string[];
}

export default function SourceFootnotes({ citations }: SourceFootnotesProps) {
  return (
    <div className="flex flex-wrap gap-4">
      {citations.map((cite, i) => (
        <span
          key={i}
          className="font-mono text-[10px] text-on-surface-variant border-b border-dotted border-outline-variant/30 hover:text-primary hover:border-primary transition-colors cursor-pointer"
        >
          [{i + 1}] {cite}
        </span>
      ))}
    </div>
  );
}
