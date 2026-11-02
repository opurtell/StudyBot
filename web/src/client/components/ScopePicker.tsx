import type { ScopeChoice, ScopeLevel } from "../lib/scopeView";

const LEVELS: { value: ScopeLevel; label: string }[] = [
  { value: "all", label: "Everything" },
  { value: "ap", label: "AP" },
  { value: "icp", label: "ICP" },
];

export function ScopePicker({
  choice,
  onChange,
  legend = "Show content for",
  label = "Show",
}: {
  choice: ScopeChoice;
  onChange: (next: ScopeChoice) => void;
  legend?: string;
  label?: string;
}) {
  return (
    <fieldset className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-sm bg-surface-container-low p-3">
      <legend className="sr-only">{legend}</legend>
      <span className="text-xs font-medium uppercase tracking-widest text-on-surface-variant" aria-hidden="true">
        {label}
      </span>
      <div className="flex gap-1" role="radiogroup" aria-label="Scope of practice">
        {LEVELS.map((level) => (
          <button
            key={level.value}
            type="button"
            role="radio"
            aria-checked={choice.level === level.value}
            onClick={() => onChange({ ...choice, level: level.value })}
            className={`min-h-10 rounded-sm px-3 py-2 text-sm font-medium ${
              choice.level === level.value ? "bg-primary text-on-primary" : "hover:bg-surface-container"
            }`}
          >
            {level.label}
          </button>
        ))}
      </div>
      {choice.level !== "all" && (
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={choice.pacer} onChange={(e) => onChange({ ...choice, pacer: e.target.checked })} />
          PACER
        </label>
      )}
    </fieldset>
  );
}
