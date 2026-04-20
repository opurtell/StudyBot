import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { apiGet } from "../lib/apiClient";
import { useSettingsContext } from "./SettingsProvider";
import type { Service } from "../types/api";

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
  const [services, setServices] = useState<Service[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let retries = 0;
    const maxRetries = 10;

    function attemptFetch() {
      if (cancelled) return;
      apiGet<Service[]>("/services")
        .then((data) => {
          if (!cancelled) {
            setServices(Array.isArray(data) ? data : []);
            setLoading(false);
            setError(null);
          }
        })
        .catch((err: unknown) => {
          if (cancelled) return;
          retries++;
          if (retries < maxRetries) {
            setTimeout(attemptFetch, 3000);
          } else {
            const message =
              err instanceof Error ? err.message : "Failed to load services";
            setError(message);
            setLoading(false);
          }
        });
    }

    attemptFetch();
    return () => {
      cancelled = true;
    };
  }, []);

  const activeService = useMemo(() => {
    const activeId = config?.active_service;
    if (!activeId) return services[0] ?? null;
    return services.find((s) => s.id === activeId) ?? services[0] ?? null;
  }, [services, config]);

  const baseQualification = useMemo(() => {
    const baseId = config?.base_qualification;
    if (!baseId || !activeService) return "";
    const base = activeService.qualifications.bases.find(
      (b) => b.id === baseId
    );
    return base?.display ?? activeService.qualifications.bases[0]?.display ?? "";
  }, [activeService, config]);

  const endorsements = useMemo(() => {
    const raw = config?.endorsements;
    return Array.isArray(raw) ? raw : [];
  }, [config]);

  const setActiveService = useCallback(
    async (id: string) => {
      if (!config) return;
      await save({ ...config, active_service: id });
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
