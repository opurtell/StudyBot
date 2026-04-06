import AdaptiveText from "./AdaptiveText";

interface MetricCardProps {
  value: string;
  label: string;
}

export default function MetricCard({ value, label }: MetricCardProps) {
  return (
    <div className="bg-surface-container p-4 border-l-4 border-primary">
      <AdaptiveText
        text={value}
        variant="headline"
        className="text-primary"
      />
      <span className="font-label text-label-sm text-on-surface-variant">{label}</span>
    </div>
  );
}
