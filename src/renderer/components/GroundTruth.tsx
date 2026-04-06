import MarkdownRenderer from "./MarkdownRenderer";

interface GroundTruthProps {
  quote: string;
  citation: string;
}

export default function GroundTruth({ quote, citation }: GroundTruthProps) {
  return (
    <div className="bg-surface-container-lowest border-l border-t border-outline-variant/20 p-6 relative">
      <span
        className="absolute top-2 right-4 font-mono text-[10px] text-on-surface-variant/20"
        style={{ writingMode: "vertical-rl", transform: "rotate(180deg)" }}
      >
        REFERENCE
      </span>
      <div className="bg-tertiary-fixed/10 p-6 border-l-2 border-tertiary-fixed">
        <MarkdownRenderer content={quote} className="italic" />
      </div>
      <p className="font-mono text-[10px] text-on-surface-variant mt-4">
        {citation}
      </p>
    </div>
  );
}
