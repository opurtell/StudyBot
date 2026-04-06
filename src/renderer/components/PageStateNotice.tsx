import Button from "./Button";

interface PageStateNoticeProps {
  title: string;
  message: string;
  actionLabel?: string;
  onAction?: () => void;
}

export default function PageStateNotice({
  title,
  message,
  actionLabel,
  onAction,
}: PageStateNoticeProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-4 py-16 text-center">
      <div className="space-y-2 max-w-xl">
        <p className="font-headline text-title-lg text-primary">{title}</p>
        <p className="font-body text-body-md text-on-surface-variant">{message}</p>
      </div>
      {actionLabel && onAction && (
        <Button onClick={onAction} variant="primary">
          {actionLabel}
        </Button>
      )}
    </div>
  );
}
