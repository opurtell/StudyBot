import { useEffect, useEffectEvent } from "react";

export interface Shortcut {
  key: string;
  action: () => void;
  enabled?: boolean;
  alt?: boolean;
  allowInEditable?: boolean;
}

function isEditable(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  if (target.isContentEditable) return true;
  return ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName);
}

function isControl(target: EventTarget | null): boolean {
  return target instanceof HTMLElement && ["BUTTON", "A", "SUMMARY"].includes(target.tagName);
}

function matches(event: KeyboardEvent, shortcut: Shortcut): boolean {
  if (event.metaKey || event.ctrlKey) return false;
  if (Boolean(shortcut.alt) !== event.altKey) return false;
  if (shortcut.alt) return event.code === `Key${shortcut.key.toUpperCase()}`;
  return event.key.toLowerCase() === shortcut.key.toLowerCase();
}

export function useShortcuts(shortcuts: Shortcut[]) {
  const onKeyDown = useEffectEvent((event: KeyboardEvent) => {
    if (event.isComposing || event.repeat || event.defaultPrevented) return;
    const editable = isEditable(event.target);
    for (const shortcut of shortcuts) {
      if (shortcut.enabled === false) continue;
      if (editable && !shortcut.allowInEditable) continue;
      if (shortcut.key === "Enter" && (event.shiftKey || isControl(event.target))) continue;
      if (!matches(event, shortcut)) continue;
      event.preventDefault();
      shortcut.action();
      return;
    }
  });

  useEffect(() => {
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);
}
