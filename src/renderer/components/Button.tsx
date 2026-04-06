import { type ButtonHTMLAttributes, type ReactNode } from "react";

type ButtonVariant = "primary" | "secondary" | "tertiary";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  children: ReactNode;
}

const variantClasses: Record<ButtonVariant, string> = {
  primary:
    "bg-primary text-on-primary hover:opacity-90 active:opacity-80",
  secondary:
    "bg-surface-container-high text-on-surface hover:bg-surface-container-highest active:bg-surface-container",
  tertiary:
    "bg-transparent text-primary hover:bg-tertiary-fixed/20 active:bg-tertiary-fixed/10",
};

export default function Button({
  variant = "primary",
  children,
  className = "",
  disabled,
  ...rest
}: ButtonProps) {
  return (
    <button
      className={`
        inline-flex items-center gap-2
        font-label text-label-sm uppercase tracking-wider
        py-3 px-6 rounded transition-all duration-200
        disabled:opacity-40 disabled:cursor-not-allowed
        ${variantClasses[variant]}
        ${className}
      `}
      disabled={disabled}
      {...rest}
    >
      {children}
    </button>
  );
}