import { useRef, useEffect } from "react";

interface AnswerInputProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit?: () => void;
  disabled?: boolean;
  placeholder?: string;
}

export default function AnswerInput({
  value,
  onChange,
  onSubmit,
  disabled = false,
  placeholder = "Enter your clinical observations here...",
}: AnswerInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.focus();
    }
  }, []);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  }, [value]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      onSubmit?.();
    }
  };

  return (
    <textarea
      ref={textareaRef}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      onKeyDown={handleKeyDown}
      aria-keyshortcuts="Enter Meta+Enter Control+Enter Shift+Enter"
      disabled={disabled}
      placeholder={placeholder}
      className="w-full h-64 bg-transparent ruled-paper text-on-surface font-body text-body-md pt-8 pb-4 px-0 resize-none focus:outline-none placeholder:text-on-surface-variant/40 disabled:opacity-40"
      style={{
        backgroundPosition: "0 1.6rem",
      }}
    />
  );
}
