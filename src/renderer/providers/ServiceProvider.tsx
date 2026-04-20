import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { apiGet, apiPut } from "../lib/apiClient";
import { useBackendStatus } from "../hooks/useBackendStatus";
import { useSettingsContext } from "./SettingsProvider";
import type { Service, SettingsConfig } from "../types/api";

export interface ServiceContextType {
  services: Service[];
  activeService: Service | null;
  baseQualification: string;
  endorsements: string[];
  setActiveService: (id: string) => Promise<void>;
  loading: boolean;
  error: string | null;
}

export const ServiceContext = createContext<ServiceContextType | null>(null);

export function ServiceProvider({ children }: { children: ReactNode }) {
  const { config, save } = useSettingsContext();
  const backendStatus = useBackendStatus();
  const [services, setServices] = useState<Service[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (backendStatus.state !== "ready") return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    apiGet<Service[]>("/services")
      .then((data) => {
        if (!cancelled) {
          setServices(data);
          setLoading(false);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          const message =
            err instanceof Error ? err.message : "Failed to load services";
          setError(message);
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [backendStatus.state]);

  const activeService = useMemo(() => {
    const activeId = (config as SettingsConfig & { active_service?: string } | null)?.active_service;
    if (!activeId) return services[0] ?? null;
    return services.find((s) => s.id === activeId) ?? services[0] ?? null;
  }, [services, config]);

  const baseQualification = useMemo(() => {
    const baseId = (config as SettingsConfig & { base_qualification?: string } | null)?.base_qualification;
    if (!baseId || !activeService) return "";
    const base = activeService.qualifications.bases.find(
      (b) => b.id === baseId
    );
    return base?.display ?? activeService.qualifications.bases[0]?.display ?? "";
  }, [activeService, config]);

  const endorsements = useMemo(() => {
    const raw = (config as SettingsConfig & { endorsements?: string[] } | null)?.endorsements;
    return Array.isArray(raw) ? raw : [];
  }, [config]);

  const setActiveService = useCallback(
    async (id: string) => {
      if (!config) return;
      const updated = { ...config, active_service: id } as SettingsConfig & {
        active_service: string;
      };
      await save(updated);
    },
    [config, save]
  );

  const value = useMemo<ServiceContextType>(
    () => ({
      services,
      activeService,
      baseQualification,
      endorsements,
      setActiveService,
      loading,
      error,
    }),
    [services, activeService, baseQualification, endorsements, setActiveService, loading, error]
  );

  return (
    <ServiceContext.Provider value={value}>{children}</ServiceContext.Provider>
  );
}
