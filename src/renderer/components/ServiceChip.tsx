import { useService } from "../hooks/useService";

export function ServiceChip() {
  const { activeService, baseQualification } = useService();
  if (!activeService) return null;
  return (
    <div className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-[var(--surface-container)]">
      <span
        className="text-sm font-medium"
        style={{ color: activeService.accent_colour }}
      >
        {activeService.display_name}
      </span>
      {baseQualification && (
        <span className="text-xs text-[var(--on-surface-variant)]">
          {baseQualification}
        </span>
      )}
    </div>
  );
}
