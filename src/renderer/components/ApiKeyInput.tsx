import { useId, useState } from "react";

interface ApiKeyInputProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
}

export default function ApiKeyInput({ label, value, onChange }: ApiKeyInputProps) {
  const [visible, setVisible] = useState(false);
  const inputId = useId();

  return (
    <div className="space-y-2">
      <label htmlFor={inputId} className="font-label text-label-sm text-on-surface-variant uppercase">
        {label}
      </label>
      <div className="flex gap-2">
        <input
          id={inputId}
          type={visible ? "text" : "password"}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="flex-1 bg-transparent border-0 border-b border-outline-variant/20 text-on-surface font-body text-body-md py-2 focus:border-primary focus:outline-none"
        />
        <button
          onClick={() => setVisible(!visible)}
          className="text-on-surface-variant hover:text-primary transition-colors px-2"
          aria-label={visible ? "Hide API key" : "Show API key"}
        >
          <span className="material-symbols-outlined text-sm">
            {visible ? "visibility_off" : "visibility"}
          </span>
        </button>
      </div>
    </div>
  );
}
