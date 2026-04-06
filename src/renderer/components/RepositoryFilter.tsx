interface RepositoryFilterProps {
  activeType: string;
  onTypeChange: (type: string) => void;
}

const TYPES = [
  { value: "all", label: "All Sources" },
  { value: "primary", label: "Primary / Regulatory" },
  { value: "reference", label: "Reference / Policies" },
  { value: "study", label: "Study / Clinical Notes" },
  { value: "field", label: "Field Notes / OCR" },
];

export default function RepositoryFilter({ activeType, onTypeChange }: RepositoryFilterProps) {
  return (
    <div className="flex items-center gap-2">
      {TYPES.map((t) => (
        <button
          key={t.value}
          onClick={() => onTypeChange(t.value)}
          className={`px-3 py-1 font-label text-[9px] uppercase tracking-widest transition-colors ${
            activeType === t.value
              ? "bg-primary text-on-primary"
              : "bg-surface-container-high text-on-surface-variant hover:bg-surface-container-highest"
          }`}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}
