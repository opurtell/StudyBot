import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { apiGet, apiPost, apiPut, getApiErrorMessage } from "../lib/apiClient";
import { useCachedResource } from "../hooks/useCachedResource";
import { useResourceCacheStore } from "./ResourceCacheProvider";
import type { CmgManifest, CmgRefreshStatus, ModelRegistry, SettingsConfig } from "../types/api";

interface SettingsContextValue {
  config: SettingsConfig | null;
  modelRegistry: ModelRegistry | null;
  loading: boolean;
  refreshing: boolean;
  saving: boolean;
  savingModels: boolean;
  error: string | null;
  save: (cfg: SettingsConfig) => Promise<boolean>;
  saveModels: (registry: ModelRegistry) => Promise<boolean>;
  rerunPipeline: () => Promise<void>;
  clearVectorStore: () => Promise<void>;
  cmgRefreshStatus: CmgRefreshStatus | null;
  cmgRefreshLoading: boolean;
  startCmgRefresh: () => Promise<void>;
  cmgManifest: CmgManifest | null;
  rebuildIndex: () => Promise<void>;
  refetch: () => Promise<void>;
}

const SETTINGS_KEY = "/settings";
const MODELS_KEY = "/settings/models";

const SettingsContext = createContext<SettingsContextValue | null>(null);

export function SettingsProvider({ children }: { children: ReactNode }) {
  const store = useResourceCacheStore();
  const [saving, setSaving] = useState(false);
  const [savingModels, setSavingModels] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const configResource = useCachedResource<SettingsConfig>(SETTINGS_KEY, (signal) =>
    apiGet<SettingsConfig>(SETTINGS_KEY, { signal })
  );
  const modelsResource = useCachedResource<ModelRegistry>(MODELS_KEY, (signal) =>
    apiGet<ModelRegistry>(MODELS_KEY, { signal })
  );

  const save = useCallback(
    async (cfg: SettingsConfig) => {
      setSaving(true);
      setActionError(null);
      try {
        const saved = await apiPut("/settings", cfg);
        if (saved === null) {
          return false;
        }
        store.setData(SETTINGS_KEY, cfg);
        return true;
      } catch (error) {
        setActionError(getApiErrorMessage(error, "Failed to save settings"));
        return false;
      } finally {
        setSaving(false);
      }
    },
    [store]
  );

  const saveModels = useCallback(
    async (registry: ModelRegistry) => {
      setSavingModels(true);
      setActionError(null);
      try {
        const saved = await apiPut("/settings/models", registry);
        if (saved === null) {
          return false;
        }
        store.setData(MODELS_KEY, registry);
        return true;
      } catch (error) {
        setActionError(getApiErrorMessage(error, "Failed to save model configuration"));
        return false;
      } finally {
        setSavingModels(false);
      }
    },
    [store]
  );

  const rerunPipeline = useCallback(async () => {
    setActionError(null);
    try {
      await apiPost("/settings/pipeline/rerun");
    } catch (error) {
      setActionError(getApiErrorMessage(error, "Failed to start pipeline"));
    }
  }, []);

  const clearVectorStore = useCallback(async () => {
    setActionError(null);
    try {
      await apiPost("/settings/vector-store/clear");
    } catch (error) {
      setActionError(getApiErrorMessage(error, "Failed to clear vector store"));
    }
  }, []);

  const [cmgRefreshStatus, setCmgRefreshStatus] = useState<CmgRefreshStatus | null>(null);
  const [cmgRefreshLoading, setCmgRefreshLoading] = useState(false);
  const cmgPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchCmgStatus = useCallback(async () => {
    try {
      const data = await apiGet<CmgRefreshStatus>("/settings/cmg-refresh");
      setCmgRefreshStatus(data);
    } catch {
      setCmgRefreshLoading(false);
    }
  }, []);

  useEffect(() => {
    setCmgRefreshLoading(true);
    fetchCmgStatus().finally(() => setCmgRefreshLoading(false));

    return () => {
      if (cmgPollRef.current !== null) {
        clearInterval(cmgPollRef.current);
        cmgPollRef.current = null;
      }
    };
  }, [fetchCmgStatus]);

  useEffect(() => {
    if (cmgRefreshStatus?.is_running) {
      if (cmgPollRef.current !== null) return;
      cmgPollRef.current = setInterval(() => {
        fetchCmgStatus();
      }, 5000);
    } else {
      if (cmgPollRef.current !== null) {
        clearInterval(cmgPollRef.current);
        cmgPollRef.current = null;
      }
    }
  }, [cmgRefreshStatus?.is_running, fetchCmgStatus]);

  const startCmgRefresh = useCallback(async () => {
    setActionError(null);
    try {
      await apiPost("/settings/cmg-refresh/run");
      setCmgRefreshStatus((prev) =>
        prev? { ...prev, status: "running", is_running: true } : prev
      );
    } catch (error) {
      setActionError(getApiErrorMessage(error, "Failed to start CMG refresh"));
    }
  }, []);

  const [cmgManifest, setCmgManifest] = useState<CmgManifest | null>(null);

  useEffect(() => {
    apiGet<CmgManifest>("/settings/cmg-manifest")
      .then(setCmgManifest)
      .catch(() => setCmgManifest(null));
  }, [cmgRefreshStatus?.last_successful_at]);

  const rebuildIndex = useCallback(async () => {
    setActionError(null);
    try {
      await apiPost("/settings/cmg-rebuild");
    } catch (error) {
      setActionError(getApiErrorMessage(error, "Failed to rebuild CMG index"));
    }
  }, []);

  const refetch = useCallback(async () => {
    setActionError(null);
    await Promise.all([configResource.refetch(), modelsResource.refetch()]);
  }, [configResource, modelsResource]);

  const value = useMemo<SettingsContextValue>(
    () => ({
      config: configResource.data,
      modelRegistry: modelsResource.data,
      loading:
        (!configResource.loaded && configResource.loading) ||
        (!modelsResource.loaded && modelsResource.loading),
      refreshing: configResource.refreshing || modelsResource.refreshing,
      saving,
      savingModels,
      error: actionError ?? configResource.error ?? modelsResource.error,
      save,
      saveModels,
      rerunPipeline,
      clearVectorStore,
      cmgRefreshStatus,
      cmgRefreshLoading,
      startCmgRefresh,
      cmgManifest,
      rebuildIndex,
      refetch,
    }),
    [
      actionError,
      clearVectorStore,
      cmgManifest,
      cmgRefreshLoading,
      cmgRefreshStatus,
      configResource,
      modelsResource,
      rebuildIndex,
      refetch,
      rerunPipeline,
      save,
      saveModels,
      saving,
      savingModels,
      startCmgRefresh,
    ]
  );

  return <SettingsContext.Provider value={value}>{children}</SettingsContext.Provider>;
}

export function useSettingsContext() {
  const context = useContext(SettingsContext);
  if (!context) {
    throw new Error("useSettingsContext must be used within a SettingsProvider");
  }
  return context;
}
