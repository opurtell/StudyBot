import ReactMarkdown from "react-markdown";

interface MarkdownRendererProps {
  content: string;
  className?: string;
}

/**
 * Reusable Markdown renderer component that applies The Archival Protocol design tokens.
 * Used for clinical guidelines, quiz sources, and AI evaluation feedback.
 */
export default function MarkdownRenderer({ content, className = "" }: MarkdownRendererProps) {
  return (
    <div
      className={`prose prose-sm max-w-none font-body text-on-surface
        [&_h1]:font-headline [&_h1]:text-title-lg [&_h1]:text-primary [&_h1]:mt-8 [&_h1]:mb-3
        [&_h2]:font-headline [&_h2]:text-body-lg [&_h2]:text-primary [&_h2]:mt-6 [&_h2]:mb-2
        [&_h3]:font-headline [&_h3]:text-body-lg [&_h3]:text-primary [&_h3]:mt-5 [&_h3]:mb-2
        [&_h4]:font-headline [&_h4]:text-body-lg [&_h4]:text-primary [&_h4]:mt-5 [&_h4]:mb-2
        [&_h5]:font-label [&_h5]:text-label-lg [&_h5]:text-on-surface-variant [&_h5]:mt-4 [&_h5]:mb-1
        [&_h6]:font-label [&_h6]:text-label-md [&_h6]:text-on-surface-variant [&_h6]:mt-3 [&_h6]:mb-1
        [&_p]:text-body-md [&_p]:text-on-surface [&_p]:leading-relaxed [&_p]:my-1
        [&_ul]:list-disc [&_ul]:pl-6 [&_ul]:my-2 [&_ul]:space-y-1
        [&_ol]:list-decimal [&_ol]:pl-6 [&_ol]:my-2 [&_ol]:space-y-1
        [&_li]:text-body-md [&_li]:text-on-surface [&_li]:leading-relaxed
        [&_strong]:font-bold [&_strong]:text-on-surface
        [&_em]:italic [&_em]:text-on-surface-variant
        [&_hr]:border-outline-variant/20 [&_hr]:my-4
        [&_code]:font-mono [&_code]:text-[10px] [&_code]:bg-surface-container [&_code]:px-1.5 [&_code]:py-0.5
        ${className}
      `}
    >
      <ReactMarkdown>{content}</ReactMarkdown>
    </div>
  );
}
