import { useId } from "react";
import type { ModelRegistry, ProviderKey } from "../types/api";

interface ModelSelectorProps {
  label: string;
  value: string;
  registry: ModelRegistry;
  onChange: (value: string) => void;
}

const PROVIDER_LABELS: Record<ProviderKey, string> = {
  anthropic: "Anthropic",
  google: "Google",
  zai: "Z.ai",
  openai: "OpenAI",
};

const TIER_LABELS: Record<"low" | "medium" | "high", string> = {
  low: "Low",
  medium: "Medium",
  high: "High",
};

const PROVIDER_ORDER: ProviderKey[] = ["anthropic", "google", "zai", "openai"];
const TIER_ORDER: Array<"low" | "medium" | "high"> = ["low", "medium", "high"];

export default function ModelSelector({ label, value, registry, onChange }: ModelSelectorProps) {
  const selectId = useId();

  return (
    <div className="space-y-2">
      <label htmlFor={selectId} className="font-label text-label-sm text-on-surface-variant uppercase">
        {label}
      </label>
      <select
        id={selectId}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full bg-surface-container-low border-0 border-b border-outline-variant/20 text-on-surface font-body text-body-md py-2 px-1 focus:border-primary focus:outline-none"
      >
        {PROVIDER_ORDER.map((providerKey) => {
          const tiers = registry[providerKey];
          return (
            <optgroup key={providerKey} label={PROVIDER_LABELS[providerKey]}>
              {TIER_ORDER.map((tier) => {
                const modelId = tiers[tier];
                return (
                  <option key={`${providerKey}-${tier}`} value={modelId}>
                    {TIER_LABELS[tier]} — {modelId}
                  </option>
                );
              })}
            </optgroup>
          );
        })}
      </select>
    </div>
  );
}
