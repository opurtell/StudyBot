import { useEffect, useEffectEvent } from "react";

export interface QuizShortcutDefinition {
  key: string;
  action: () => void;
  enabled?: boolean;
  meta?: boolean;
  shift?: boolean;
  alt?: boolean;
  allowInEditable?: boolean;
}

function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) {
    return false;
  }

  if (target.isContentEditable) {
    return true;
  }

  const tagName = target.tagName.toLowerCase();
  return tagName === "input" || tagName === "textarea" || tagName === "select";
}

function matchesShortcut(event: KeyboardEvent, shortcut: QuizShortcutDefinition): boolean {
  const wantsMeta = Boolean(shortcut.meta);
  const wantsShift = Boolean(shortcut.shift);
  const wantsAlt = Boolean(shortcut.alt);
  const hasMeta = event.metaKey || event.ctrlKey;

  return (
    event.key.toLowerCase() === shortcut.key.toLowerCase() &&
    hasMeta === wantsMeta &&
    event.shiftKey === wantsShift &&
    event.altKey === wantsAlt
  );
}

export function useQuizShortcuts(shortcuts: QuizShortcutDefinition[]) {
  const handleKeyDown = useEffectEvent((event: KeyboardEvent) => {
    if (event.isComposing || event.repeat) {
      return;
    }

    const editable = isEditableTarget(event.target);

    for (const shortcut of shortcuts) {
      if (shortcut.enabled === false) {
        continue;
      }

      if (!shortcut.allowInEditable && editable) {
        continue;
      }

      if (!matchesShortcut(event, shortcut)) {
        continue;
      }

      event.preventDefault();
      shortcut.action();
      return;
    }
  });

  useEffect(() => {
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);
}
