import type { ReactNode } from "react";

interface TagProps {
  children: ReactNode;
  className?: string;
}

export default function Tag({ children, className = "" }: TagProps) {
  return (
    <span
      className={`
        inline-block px-2 py-1
        bg-surface-container-highest
        font-label text-[9px] uppercase tracking-widest
        text-on-surface-variant
        ${className}
      `}
    >
      {children}
    </span>
  );
}