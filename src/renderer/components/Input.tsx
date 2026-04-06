import { type InputHTMLAttributes, useId } from "react";

interface InputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "style"> {
  label?: string;
}

export default function Input({ label, className = "", id, ...rest }: InputProps) {
  const autoId = useId();
  const inputId = id || autoId;

  return (
    <div className="flex flex-col gap-1">
      {label && (
        <label
          htmlFor={inputId}
          className="font-label text-label-sm text-on-surface-variant uppercase tracking-wider"
        >
          {label}
        </label>
      )}
      <input
        id={inputId}
        className={`
          w-full
          bg-transparent
          border-0 border-b border-outline-variant/20
          text-on-surface font-body text-body-md
          py-2 px-0
          transition-all duration-200
          focus:border-primary focus:bg-surface-container-lowest/50
          focus:outline-none
          placeholder:text-on-surface-variant/40
          disabled:opacity-40 disabled:cursor-not-allowed
          ${className}
        `}
        {...rest}
      />
    </div>
  );
}