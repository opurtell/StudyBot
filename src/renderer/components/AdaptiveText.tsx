interface AdaptiveTextProps {
  text: string;
  variant?: "headline" | "title" | "display";
  className?: string;
  allowWrap?: boolean;
}

/**
 * A component that scales text size based on character count
 * to ensure phrases fit gracefully within cards and containers.
 */
export default function AdaptiveText({
  text,
  variant = "headline",
  className = "",
  allowWrap = true,
}: AdaptiveTextProps) {
  const len = text.length;

  const getResponsiveClass = () => {
    if (variant === "display") {
      if (len > 25) return "text-display-sm";
      return "text-display-lg";
    }

    if (variant === "headline") {
      if (len > 35) return "text-title-lg";
      if (len > 22) return "text-headline-sm";
      return "text-headline-md";
    }

    if (variant === "title") {
      if (len > 45) return "text-body-md";
      if (len > 28) return "text-title-md";
      return "text-title-lg";
    }

    return "";
  };

  // Note: font-title is actually Space Grotesk in our config (title-lg uses it)
  // Wait, our config uses 'headline' for Newsreader and 'body'/'label' for Space Grotesk.
  // 'title-lg' doesn't have a specific font-family assigned in the JS object, 
  // but it's typically used with 'font-headline' for editorial or 'font-body' for technical.
  // I'll stick to 'font-headline' for display/headline and 'font-body' for title/body.

  const fontFamily = (variant === "headline" || variant === "display") ? "font-headline" : "font-body";

  return (
    <span
      className={`
        ${fontFamily}
        ${getResponsiveClass()}
        ${allowWrap ? "break-words" : "truncate"}
        inline-block w-full
        ${className}
      `}
      title={text}
    >
      {text}
    </span>
  );
}
