import type { CategoryMastery } from "../types/api";
import AdaptiveText from "./AdaptiveText";

interface KnowledgeHeatmapProps {
  categories: CategoryMastery[];
  onCategoryClick?: (category: string) => void;
}

function getStatusDot(percent: number): string {
  if (percent >= 85) return "bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.4)]";
  if (percent >= 60) return "bg-emerald-500/60";
  if (percent >= 40) return "bg-amber-400";
  return "bg-rose-300";
}

function getBarColour(percent: number): string {
  if (percent >= 85) return "bg-emerald-500";
  if (percent >= 60) return "bg-emerald-500/60";
  if (percent >= 40) return "bg-amber-400";
  return "bg-rose-300";
}

export default function KnowledgeHeatmap({ categories, onCategoryClick }: KnowledgeHeatmapProps) {
  return (
    <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
      {categories.map((cat, i) => (
        <div
          key={cat.category}
          className={`bg-surface-container-low p-6 h-48 flex flex-col justify-between ${
            onCategoryClick
              ? "cursor-pointer hover:bg-surface-container transition-colors"
              : ""
          }`}
          onClick={onCategoryClick ? () => onCategoryClick(cat.category) : undefined}
          role={onCategoryClick ? "button" : undefined}
          tabIndex={onCategoryClick ? 0 : undefined}
        >
          <div className="flex items-center justify-between">
            <span className="font-mono text-[10px] text-on-surface-variant">
              {String(i + 1).padStart(2, "0")}.00
            </span>
            <div className={`w-2 h-2 rounded-full ${getStatusDot(cat.mastery_percent)}`} />
          </div>
          <div>
            <AdaptiveText
              text={cat.category}
              variant="headline"
              className="text-on-surface"
            />
            <span className="font-label text-label-sm text-on-surface-variant">
              {Math.round(cat.mastery_percent)}% Mastery
            </span>
          </div>
          <div
            className="h-1 w-full bg-outline-variant/20"
            role="progressbar"
            aria-valuenow={cat.mastery_percent}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label={`${cat.category} mastery`}
          >
            <div
              className={`h-full ${getBarColour(cat.mastery_percent)} transition-all duration-500`}
              style={{ width: `${cat.mastery_percent}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}
