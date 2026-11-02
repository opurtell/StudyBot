export function ScopePicker<L extends string>({
  level,
  pacer,
  options,
  onChange,
  legend = "Show content for",
  label = "Show",
}: {
  level: L | null;
  pacer: boolean;
  options: { value: L; label: string }[];
  onChange: (next: { level: L; pacer: boolean }) => void;
  legend?: string;
  label?: string;
}) {
  return (
    <fieldset className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-sm bg-surface-container-low p-3">
      <legend className="sr-only">{legend}</legend>
      <span className="text-xs font-medium uppercase tracking-widest text-on-surface-variant" aria-hidden="true">
        {label}
      </span>
      <div className="flex gap-1" role="radiogroup" aria-label={legend}>
        {options.map((option) => (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={level === option.value}
            onClick={() => onChange({ level: option.value, pacer })}
            className={`min-h-10 rounded-sm px-3 py-2 text-sm font-medium ${
              level === option.value ? "bg-primary text-on-primary" : "hover:bg-surface-container"
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>
      {level !== null && (
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={pacer} onChange={(e) => onChange({ level, pacer: e.target.checked })} />
          PACER
        </label>
      )}
    </fieldset>
  );
}
