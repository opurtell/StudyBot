import type { ReactNode, HTMLAttributes } from "react";

interface CardProps extends Omit<HTMLAttributes<HTMLDivElement>, "style"> {
  children: ReactNode;
  onClick?: () => void;
  className?: string;
}

export default function Card({
  children,
  onClick,
  className = "",
  ...rest
}: CardProps) {
  const interactive = typeof onClick === "function";

  return (
    <div
      role={interactive ? "button" : undefined}
      tabIndex={interactive ? 0 : undefined}
      onClick={onClick}
      onKeyDown={
        interactive
          ? (e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                onClick();
              }
            }
          : undefined
      }
      className={`
        bg-surface-container-low p-6
        ${interactive ? "hover:bg-surface-container-lowest cursor-pointer" : ""}
        transition-colors duration-200
        ${className}
      `}
      {...rest}
    >
      {children}
    </div>
  );
}