import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { api, type UserSettings } from "./api";
import { useSession } from "./session";

export interface Preferences {
  qualification: "ap" | "icp" | null;
  pacer: boolean;
  excludedSections: string[];
  excludedDocuments: string[];
}

const SCOPE_KEY = "scope-view";
const EXCLUDED_KEY = "excluded-topics";

export const DEFAULT_PREFERENCES: Preferences = { qualification: null, pacer: false, excludedSections: [], excludedDocuments: [] };

function strings(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((v): v is string => typeof v === "string") : [];
}

export function loadLocalPreferences(): Preferences {
  const prefs = { ...DEFAULT_PREFERENCES };
  try {
    const scope = JSON.parse(localStorage.getItem(SCOPE_KEY) ?? "null") as { level?: unknown; pacer?: unknown } | null;
    if (scope && (scope.level === "ap" || scope.level === "icp")) {
      prefs.qualification = scope.level;
      prefs.pacer = scope.pacer === true;
    }
    const excluded = JSON.parse(localStorage.getItem(EXCLUDED_KEY) ?? "null") as { sections?: unknown; documents?: unknown } | null;
    if (excluded) {
      prefs.excludedSections = strings(excluded.sections);
      prefs.excludedDocuments = strings(excluded.documents);
    }
  } catch {
    return prefs;
  }
  return prefs;
}

function saveLocal(prefs: Preferences) {
  try {
    localStorage.setItem(SCOPE_KEY, JSON.stringify({ level: prefs.qualification ?? "all", pacer: prefs.qualification ? prefs.pacer : false }));
    localStorage.setItem(EXCLUDED_KEY, JSON.stringify({ sections: prefs.excludedSections, documents: prefs.excludedDocuments }));
  } catch {
    return;
  }
}

function fromSettings(s: UserSettings): Preferences {
  return {
    qualification: s.qualification,
    pacer: s.pacer,
    excludedSections: s.excludedSections,
    excludedDocuments: s.excludedDocuments,
  };
}

function isDefault(p: Preferences): boolean {
  return p.qualification === null && !p.pacer && p.excludedSections.length === 0 && p.excludedDocuments.length === 0;
}

interface PreferencesState {
  prefs: Preferences;
  update: (next: Preferences) => void;
  syncError: string | null;
}

const PreferencesContext = createContext<PreferencesState | null>(null);

export function PreferencesProvider({ children }: { children: ReactNode }) {
  const { me } = useSession();
  const [local, setLocal] = useState<Preferences>(loadLocalPreferences);
  const [edited, setEdited] = useState<Preferences | null>(null);
  const [syncError, setSyncError] = useState<string | null>(null);
  const account = me?.signedIn ? me.email : null;
  const adopted = useRef<string | null>(null);

  useEffect(() => {
    setEdited(null);
    setSyncError(null);
  }, [account]);

  useEffect(() => {
    if (!me?.signedIn || me.settings?.saved !== false || adopted.current === me.email) return;
    adopted.current = me.email;
    const current = loadLocalPreferences();
    if (isDefault(current)) return;
    setEdited(current);
    api.saveSettings(current).catch(() => setSyncError("Couldn't save your settings to your account."));
  }, [me]);

  const server = me?.signedIn && me.settings?.saved ? fromSettings(me.settings) : null;
  const prefs = me?.signedIn ? (edited ?? server ?? local) : local;

  const update = useCallback(
    (next: Preferences) => {
      setLocal(next);
      saveLocal(next);
      if (me?.signedIn) {
        setEdited(next);
        api
          .saveSettings(next)
          .then(() => setSyncError(null))
          .catch(() => setSyncError("Couldn't save your settings to your account. They're kept on this device for now."));
      }
    },
    [me],
  );

  const value = useMemo(() => ({ prefs, update, syncError }), [prefs, update, syncError]);
  return <PreferencesContext.Provider value={value}>{children}</PreferencesContext.Provider>;
}

export function usePreferences(): PreferencesState {
  const ctx = useContext(PreferencesContext);
  if (!ctx) throw new Error("usePreferences must be used inside PreferencesProvider");
  return ctx;
}
