import { useState, useEffect } from "react";
import { useTheme } from "../hooks/useTheme";
import { useBlacklist } from "../hooks/useBlacklist";
import { useSettings } from "../hooks/useSettings";
import { useService } from "../hooks/useService";
import BlacklistManager from "../components/BlacklistManager";
import ModelSelector from "../components/ModelSelector";
import ApiKeyInput from "../components/ApiKeyInput";
import Button from "../components/Button";
import Modal from "../components/Modal";
import type { ProviderKey, ModelRegistry } from "../types/api";
import PageStateNotice from "../components/PageStateNotice";
import { useBackendStatus, useBackendStatusActions } from "../hooks/useBackendStatus";
import { getErrorStateCopy } from "../lib/loadingState";

const PROVIDER_KEYS: ProviderKey[] = ["anthropic", "google", "zai", "openai"];

const PROVIDER_LABELS: Record<ProviderKey, string> = {
  anthropic: "Anthropic",
  google: "Google",
  zai: "Z.ai",
  openai: "OpenAI",
};

const TIER_ORDER: Array<"low" | "medium" | "high"> = ["low", "medium", "high"];
const TIER_LABELS: Record<"low" | "medium" | "high", string> = {
  low: "Low",
  medium: "Medium",
  high: "High",
};

const FALLBACK_REGISTRY: ModelRegistry = {
  anthropic: {
    low: "claude-haiku-4-5-20251001",
    medium: "claude-sonnet-4.6",
    high: "claude-opus-4.6",
  },
  google: {
    low: "gemini-3.1-flash-lite-preview",
    medium: "gemini-3-flash-preview",
    high: "gemini-2.5-pro",
  },
  zai: {
    low: "glm-4.7-flash",
    medium: "glm-4.7",
    high: "glm-5",
  },
  openai: {
    low: "gpt-5.4-nano",
    medium: "gpt-5.4-mini",
    high: "gpt-5.4",
  },
};

function getProviderForModel(
  registry: ModelRegistry,
  modelId: string
): ProviderKey | null {
  for (const provider of PROVIDER_KEYS) {
    if (Object.values(registry[provider]).includes(modelId)) {
      return provider;
    }
  }
  return null;
}

export default function Settings() {
  const { theme, setTheme } = useTheme();
  const blacklist = useBlacklist();
  const backendStatus = useBackendStatus();
  const { restart } = useBackendStatusActions();
  const {
    config,
    modelRegistry,
    loading,
    refreshing,
    saving,
    savingModels,
    error,
    save,
    saveModels,
    rerunPipeline,
    clearVectorStore,
    clearSourceType,
    clearMastery,
    vectorStoreStatus,
    cmgRefreshStatus,
    cmgRefreshLoading,
    startCmgRefresh,
    cmgManifest,
    rebuildIndex,
    rebuildRunning,
  } = useSettings();
  const {
    services: rawServices,
    activeService,
    setActiveService,
    loading: serviceLoading,
  } = useService();
  const services = Array.isArray(rawServices) ? rawServices : [];

  // Local state for qualifications editing
  const [localBaseQualification, setLocalBaseQualification] = useState<string>("");
  const [localEndorsements, setLocalEndorsements] = useState<string[]>([]);
  const [qualificationsSaving, setQualificationsSaving] = useState(false);

  const [quizModel, setQuizModel] = useState(config?.quiz_model ?? "claude-haiku-4-5-20251001");
  const [cleanModel, setCleanModel] = useState(config?.clean_model ?? "claude-opus-4.6");
  const [visionModel, setVisionModel] = useState(config?.vision_model ?? config?.clean_model ?? "claude-sonnet-4.6");
  const [apiKeys, setApiKeys] = useState<Record<ProviderKey, string>>({
    anthropic: config?.providers?.anthropic?.api_key ?? "",
    google: config?.providers?.google?.api_key ?? "",
    zai: config?.providers?.zai?.api_key ?? "",
    openai: config?.providers?.openai?.api_key ?? "",
  });
  const [activeProvider] = useState<ProviderKey>(
    (config?.active_provider as ProviderKey) ?? "anthropic"
  );

  // Merge with fallback to ensure all providers exist (handles stale localStorage cache)
  const activeRegistry: ModelRegistry = { ...FALLBACK_REGISTRY, ...modelRegistry };
  const [editedRegistry, setEditedRegistry] = useState<ModelRegistry>(activeRegistry);
  const [registryDirty, setRegistryDirty] = useState(false);
  const [registryUnavailable, setRegistryUnavailable] = useState(false);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [showClearMastery, setShowClearMastery] = useState(false);

  useEffect(() => {
    if (!config) return;
    setQuizModel(config.quiz_model);
    setCleanModel(config.clean_model);
    setVisionModel(config.vision_model ?? config.clean_model ?? "claude-sonnet-4.6");
    setApiKeys({
      anthropic: config.providers?.anthropic?.api_key ?? "",
      google: config.providers?.google?.api_key ?? "",
      zai: config.providers?.zai?.api_key ?? "",
      openai: config.providers?.openai?.api_key ?? "",
    });
  }, [config]);

  useEffect(() => {
    if (modelRegistry) {
      // Merge with fallback to ensure all providers exist (handles stale cache)
      const merged: ModelRegistry = { ...FALLBACK_REGISTRY, ...modelRegistry };
      setEditedRegistry(JSON.parse(JSON.stringify(merged)));
      setRegistryDirty(false);
      setRegistryUnavailable(false);
    } else if (!loading) {
      setRegistryUnavailable(true);
    }
  }, [modelRegistry, loading]);

  // Sync local qualification state from config
  useEffect(() => {
    if (!config) return;
    const cfg = config as unknown as Record<string, unknown>;
    if (typeof cfg.base_qualification === "string") {
      setLocalBaseQualification(cfg.base_qualification);
    }
    if (Array.isArray(cfg.endorsements)) {
      setLocalEndorsements(cfg.endorsements as string[]);
    }
  }, [config]);

  const handleSaveQualifications = async () => {
    if (!config) return;
    setQualificationsSaving(true);
    setSaveMessage(null);
    const saved = await save({
      ...config,
      base_qualification: localBaseQualification,
      endorsements: localEndorsements,
    });
    if (saved) {
      setSaveMessage("Qualifications Saved");
    }
    setQualificationsSaving(false);
  };

  const errorCopy = getErrorStateCopy(error, backendStatus, "configuration");

  if (loading && !config) {
    return <PageStateNotice loading title="Loading configuration" message="Preparing local settings and model selections." />;
  }

  if (error && !config) {
    return (
      <PageStateNotice
        title={errorCopy.title}
        message={errorCopy.message}
        actionLabel={
          backendStatus.state === "error" || backendStatus.state === "stopped"
            ? "Restart Backend"
            : "Retry"
        }
        onAction={() => {
          if (backendStatus.state === "error" || backendStatus.state === "stopped") {
            void restart();
            return;
          }
          window.location.reload();
        }}
      />
    );
  }

  const handleSave = async () => {
    if (!config) return;
    const nextProviders = {
      anthropic: {
        api_key: apiKeys.anthropic,
        default_model: config.providers?.anthropic?.default_model ?? "",
      },
      google: {
        api_key: apiKeys.google,
        default_model: config.providers?.google?.default_model ?? "",
      },
      zai: {
        api_key: apiKeys.zai,
        default_model: config.providers?.zai?.default_model ?? "",
      },
      openai: {
        api_key: apiKeys.openai,
        default_model: config.providers?.openai?.default_model ?? "",
      },
    };
    const quizProvider = getProviderForModel(activeRegistry, quizModel);
    if (quizProvider) {
      nextProviders[quizProvider].default_model = quizModel;
    }
    const cleanProvider = getProviderForModel(activeRegistry, cleanModel);
    if (cleanProvider) {
      nextProviders[cleanProvider].default_model = cleanModel;
    }
    const visionProvider = getProviderForModel(activeRegistry, visionModel);
    if (visionProvider) {
      nextProviders[visionProvider].default_model = visionModel;
    }

    const saved = await save({
      ...config,
      providers: {
        anthropic: nextProviders.anthropic,
        google: nextProviders.google,
        zai: nextProviders.zai,
        openai: nextProviders.openai,
      },
      active_provider: activeProvider,
      quiz_model: quizModel,
      clean_model: cleanModel,
      vision_model: visionModel,
      base_qualification: localBaseQualification || "AP",
      endorsements: localEndorsements,
    });
    if (saved) {
      setSaveMessage("Settings Saved");
    }
  };

  const handleRegistryFieldChange = (
    provider: ProviderKey,
    tier: "low" | "medium" | "high",
    value: string
  ) => {
    setEditedRegistry((prev) => ({
      ...prev,
      [provider]: { ...prev[provider], [tier]: value },
    }));
    setRegistryDirty(true);
    setSaveMessage(null);
  };

  const handleSaveModels = async () => {
    const saved = await saveModels(editedRegistry);
    if (saved) {
      setRegistryDirty(false);
      setSaveMessage("Settings Saved");
    }
  };

  return (
    <div className="space-y-12">
      <div>
        <span className="font-label text-label-sm text-on-surface-variant">
          Configuration
        </span>
        <h2 className="font-headline text-display-lg text-primary">
          Curator Settings
        </h2>
      </div>

      {error && (
        <p className="font-mono text-[10px] text-status-critical">
          {config ? `${errorCopy.title}. Showing the last loaded configuration.` : errorCopy.message}
        </p>
      )}
      {refreshing && config && (
        <p className="font-mono text-[10px] text-on-surface-variant">
          Refreshing configuration...
        </p>
      )}
      {saveMessage && !error && (
        <p className="font-mono text-[10px] text-emerald-700">{saveMessage}</p>
      )}

      {/* Active Service */}
      <section className="space-y-6">
        <h3 className="font-label text-label-sm text-on-surface-variant uppercase pb-2 border-b border-outline-variant/10">
          Active Service
        </h3>
        {serviceLoading ? (
          <p className="font-mono text-[10px] text-on-surface-variant">Loading services...</p>
        ) : (
          <div className="flex gap-2 flex-wrap">
            {services.map((svc) => (
              <button
                key={svc.id}
                onClick={() => {
                  setSaveMessage(null);
                  void setActiveService(svc.id);
                }}
                className={`px-4 py-2 font-label text-label-sm uppercase tracking-wider transition-colors ${
                  activeService?.id === svc.id
                    ? "bg-primary text-on-primary"
                    : "bg-surface-container-high text-on-surface-variant hover:bg-surface-container-highest"
                }`}
              >
                {svc.display_name}
              </button>
            ))}
          </div>
        )}
        {activeService && (
          <p className="font-mono text-[10px] text-on-surface-variant">
            Region: {activeService.region}
          </p>
        )}
      </section>

      {/* Qualifications */}
      {activeService && (
        <section className="space-y-6">
          <h3 className="font-label text-label-sm text-on-surface-variant uppercase pb-2 border-b border-outline-variant/10">
            Qualifications
          </h3>
          <div className="space-y-4">
            <div>
              <span className="font-label text-[10px] text-on-surface-variant uppercase tracking-widest">
                Base Qualification
              </span>
              <div className="flex gap-2 mt-2">
                {activeService.qualifications.bases.map((base) => (
                  <button
                    key={base.id}
                    onClick={() => {
                      setSaveMessage(null);
                      setLocalBaseQualification(base.id);
                    }}
                    className={`px-4 py-2 font-label text-label-sm uppercase tracking-wider transition-colors ${
                      localBaseQualification === base.id
                        ? "bg-primary text-on-primary"
                        : "bg-surface-container-high text-on-surface-variant hover:bg-surface-container-highest"
                    }`}
                  >
                    {base.display}
                  </button>
                ))}
              </div>
            </div>
            {activeService.qualifications.endorsements.length > 0 && (
              <div>
                <span className="font-label text-[10px] text-on-surface-variant uppercase tracking-widest">
                  Endorsements
                </span>
                <div className="mt-2 space-y-2">
                  {activeService.qualifications.endorsements
                    .filter((endo) => {
                      if (endo.requires_base.length === 0) return true;
                      return endo.requires_base.includes(localBaseQualification);
                    })
                    .map((endo) => (
                      <label key={endo.id} className="flex items-center gap-3 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={localEndorsements.includes(endo.id)}
                          onChange={(e) => {
                            setSaveMessage(null);
                            setLocalEndorsements((prev) =>
                              e.target.checked
                                ? [...prev, endo.id]
                                : prev.filter((id) => id !== endo.id)
                            );
                          }}
                          className="w-4 h-4 accent-primary"
                        />
                        <span className="font-label text-label-sm text-on-surface">
                          {endo.display}
                        </span>
                      </label>
                    ))}
                </div>
              </div>
            )}
            <Button
              variant="secondary"
              onClick={handleSaveQualifications}
              disabled={qualificationsSaving}
            >
              {qualificationsSaving ? "Saving..." : "Save Qualifications"}
            </Button>
          </div>
        </section>
      )}

      <section className="space-y-6">
        <h3 className="font-label text-label-sm text-on-surface-variant uppercase pb-2 border-b border-outline-variant/10">
          API Keys
        </h3>
        {PROVIDER_KEYS.map((key) => (
          <ApiKeyInput
            key={key}
            label={`${PROVIDER_LABELS[key]} API Key`}
            value={apiKeys[key]}
            onChange={(v) => {
              setSaveMessage(null);
              setApiKeys((prev) => ({ ...prev, [key]: v }));
            }}
          />
        ))}
      </section>

      <section className="space-y-6">
        <h3 className="font-label text-label-sm text-on-surface-variant uppercase pb-2 border-b border-outline-variant/10">
          Model Selection
        </h3>
        <ModelSelector
          label="Quiz Agent Model"
          value={quizModel}
          registry={activeRegistry}
          onChange={(value) => {
            setSaveMessage(null);
            setQuizModel(value);
          }}
        />
        <ModelSelector
          label="Cleaning Agent Model"
          value={cleanModel}
          registry={activeRegistry}
          onChange={(value) => {
            setSaveMessage(null);
            setCleanModel(value);
          }}
        />
        <ModelSelector
          label="Vision Model"
          value={visionModel}
          registry={activeRegistry}
          onChange={(value) => {
            setSaveMessage(null);
            setVisionModel(value);
          }}
        />
      </section>

      <section className="space-y-6">
        <div className="flex items-end justify-between pb-2 border-b border-outline-variant/10">
          <div>
            <h3 className="font-label text-label-sm text-on-surface-variant uppercase">
              Model Configuration
            </h3>
            <p className="font-mono text-[10px] text-on-surface-variant mt-1">
              {registryUnavailable
                ? "Backend unavailable — editing defaults. Restart backend to persist changes to .env."
                : "Edit model names below or modify .env directly. Changes write to .env on save."}
            </p>
          </div>
          {registryDirty && (
            <Button
              variant="secondary"
              onClick={handleSaveModels}
              disabled={savingModels || registryUnavailable}
            >
              {savingModels ? "Saving..." : "Save Models"}
            </Button>
          )}
        </div>

        <div className="space-y-8">
          {PROVIDER_KEYS.map((providerKey) => (
            <div key={providerKey} className="space-y-3">
              <span className="font-label text-label-sm text-on-surface uppercase tracking-wider">
                {PROVIDER_LABELS[providerKey]}
              </span>
              <div className="grid grid-cols-3 gap-4">
                {TIER_ORDER.map((tier) => (
                  <div key={tier} className="space-y-1">
                    <label className="font-mono text-[10px] text-on-surface-variant uppercase tracking-widest">
                      {TIER_LABELS[tier]}
                    </label>
                    <input
                      type="text"
                      value={editedRegistry[providerKey]?.[tier] ?? ""}
                      onChange={(e) =>
                        handleRegistryFieldChange(providerKey, tier, e.target.value)
                      }
                      className="w-full bg-surface-container-low border-0 border-b border-outline-variant/20 text-on-surface font-mono text-[11px] py-1.5 px-1 focus:border-primary focus:outline-none"
                      spellCheck={false}
                    />
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="space-y-6">
        <h3 className="font-label text-label-sm text-on-surface-variant uppercase pb-2 border-b border-outline-variant/10">
          Quiz Preferences
        </h3>
        <BlacklistManager
          items={blacklist.items}
          loading={blacklist.loading}
          onAdd={blacklist.add}
          onRemove={blacklist.remove}
        />
      </section>

      <section className="space-y-6">
        <h3 className="font-label text-label-sm text-on-surface-variant uppercase pb-2 border-b border-outline-variant/10">
          Appearance
        </h3>
        <div className="flex items-center gap-4">
          <span className="font-label text-label-sm text-on-surface-variant">Theme</span>
          <div className="flex gap-2">
            <button
              onClick={() => setTheme("light")}
              className={`px-4 py-2 font-label text-label-sm uppercase tracking-wider transition-colors ${
                theme === "light" ? "bg-primary text-on-primary" : "bg-surface-container-high text-on-surface-variant"
              }`}
            >
              Light
            </button>
            <button
              onClick={() => setTheme("dark")}
              className={`px-4 py-2 font-label text-label-sm uppercase tracking-wider transition-colors ${
                theme === "dark" ? "bg-primary text-on-primary" : "bg-surface-container-high text-on-surface-variant"
              }`}
            >
              Dark
            </button>
          </div>
        </div>
      </section>

      <section className="space-y-6">
        <h3 className="font-label text-label-sm text-on-surface-variant uppercase pb-2 border-b border-outline-variant/10">
          Indexed Data
        </h3>

        {/* Per-source rows */}
        <div className="space-y-3">
          {/* CMG row */}
          <div className="flex items-center justify-between">
            <div>
              <span className="font-label text-label-sm text-on-surface">Clinical Management Guidelines</span>
              <span className="font-mono text-[10px] text-on-surface-variant ml-2">
                {vectorStoreStatus?.cmg ?? "—"} chunks
              </span>
            </div>
            <div className="flex gap-2">
              <Button variant="secondary" onClick={rebuildIndex} disabled={rebuildRunning}>
                {rebuildRunning ? "Rebuilding\u2026" : "Rebuild Index"}
              </Button>
              <Button
                variant="secondary"
                onClick={startCmgRefresh}
                disabled={cmgRefreshStatus?.is_running || cmgRefreshLoading}
              >
                {cmgRefreshStatus?.is_running ? "Updating..." : "Update from Web"}
              </Button>
              <Button variant="tertiary" onClick={() => clearSourceType("cmg")}>
                Clear
              </Button>
            </div>
          </div>

          {/* CMG metadata */}
          {cmgManifest && (
            <p className="font-mono text-[10px] text-on-surface-variant pl-1">
              Bundled data captured: {new Date(cmgManifest.captured_at).toLocaleDateString("en-AU", { day: "numeric", month: "long", year: "numeric" })} — {cmgManifest.guideline_count} guidelines, {cmgManifest.medication_count} medications, {cmgManifest.clinical_skill_count} clinical skills
            </p>
          )}
          {cmgRefreshStatus?.last_successful_at && (
            <p className="font-mono text-[10px] text-on-surface-variant pl-1">
              Last web update: {new Date(cmgRefreshStatus.last_successful_at).toLocaleDateString("en-AU", { day: "numeric", month: "short", year: "numeric" })}
            </p>
          )}
          {cmgRefreshStatus?.summary && (
            <p className="font-mono text-[10px] text-on-surface-variant pl-1">
              {cmgRefreshStatus.summary.checked_item_count} checked · {cmgRefreshStatus.summary.new_count} new · {cmgRefreshStatus.summary.updated_count} updated · {cmgRefreshStatus.summary.error_count} errors
            </p>
          )}
          {cmgRefreshStatus?.is_running && (
            <p className="font-mono text-[10px] text-on-surface-variant pl-1">
              Updating from web...
            </p>
          )}
          {cmgRefreshStatus?.status === "failed" && cmgRefreshStatus.last_error && (
            <p className="font-mono text-[10px] text-status-critical pl-1">
              {cmgRefreshStatus.last_error}
            </p>
          )}

          {/* Reference Documents row */}
          <div className="flex items-center justify-between">
            <div>
              <span className="font-label text-label-sm text-on-surface">Reference Documents</span>
              <span className="font-mono text-[10px] text-on-surface-variant ml-2">
                {vectorStoreStatus?.ref_doc ?? "—"} chunks
              </span>
            </div>
            <Button variant="tertiary" onClick={() => clearSourceType("ref_doc")}>
              Clear
            </Button>
          </div>

          {/* CPD Study Documents row */}
          <div className="flex items-center justify-between">
            <div>
              <span className="font-label text-label-sm text-on-surface">CPD Study Documents</span>
              <span className="font-mono text-[10px] text-on-surface-variant ml-2">
                {vectorStoreStatus?.cpd_doc ?? "—"} chunks
              </span>
            </div>
            <Button variant="tertiary" onClick={() => clearSourceType("cpd_doc")}>
              Clear
            </Button>
          </div>

          {/* Personal Notes row */}
          <div className="flex items-center justify-between">
            <div>
              <span className="font-label text-label-sm text-on-surface">Personal Notes</span>
              <span className="font-mono text-[10px] text-on-surface-variant ml-2">
                {vectorStoreStatus?.notability_note ?? "—"} chunks
              </span>
            </div>
            <div className="flex gap-2">
              <Button variant="secondary" onClick={rerunPipeline}>
                Re-run Pipeline
              </Button>
              <Button variant="tertiary" onClick={() => clearSourceType("notability_note")}>
                Clear
              </Button>
            </div>
          </div>

          {/* Mastery data row */}
          <div className="flex items-center justify-between">
            <div>
              <span className="font-label text-label-sm text-on-surface">Mastery &amp; Quiz History</span>
              <span className="font-mono text-[10px] text-on-surface-variant ml-2">
                Quiz scores and progress tracking
              </span>
            </div>
            <Button variant="tertiary" onClick={() => setShowClearMastery(true)}>
              Clear
            </Button>
          </div>
        </div>

        {/* Nuclear clear */}
        <div>
          <Button variant="tertiary" onClick={clearVectorStore}>
            Clear All Indexed Data
          </Button>
          <p className="font-body text-[10px] text-on-surface-variant mt-1">
            Deletes the entire search index. Individual source types can be cleared above.
          </p>
        </div>

        {/* Per-doc retag (placeholder UI — API endpoint pending) */}
        <div>
          <h4 className="font-label text-[10px] text-on-surface-variant uppercase tracking-widest mb-3">
            Per-Document Service Tagging
          </h4>
          <p className="font-mono text-[10px] text-on-surface-variant mb-4">
            Assign service and scope to structured documents. Changes will apply once the retag endpoint is available.
          </p>
          <div className="space-y-2">
            {/* Placeholder rows for demonstration */}
            {[
              { name: "ACTAS Policies and procedures.md", service: activeService?.display_name ?? "—", scope: "general" },
              { name: "Reference Info ACTAS CMGs.md", service: activeService?.display_name ?? "—", scope: "general" },
              { name: "ECGs.md", service: activeService?.display_name ?? "—", scope: "service-specific" },
              { name: "Finals Study.md", service: activeService?.display_name ?? "—", scope: "service-specific" },
            ].map((doc) => (
              <div
                key={doc.name}
                className="flex items-center gap-4 bg-surface-container-low p-3"
              >
                <span className="font-mono text-[10px] text-on-surface flex-1 truncate">
                  {doc.name}
                </span>
                <select
                  defaultValue={doc.service}
                  className="bg-surface-container-lowest text-on-surface font-mono text-[10px] px-2 py-1"
                >
                  <option value="general">General</option>
                  {services.map((svc) => (
                    <option key={svc.id} value={svc.display_name}>
                      {svc.display_name}
                    </option>
                  ))}
                </select>
                <select
                  defaultValue={doc.scope}
                  className="bg-surface-container-lowest text-on-surface font-mono text-[10px] px-2 py-1"
                >
                  <option value="service-specific">Service-specific</option>
                  <option value="general">General</option>
                </select>
              </div>
            ))}
          </div>
        </div>
      </section>

      <div className="pt-4">
        <Button onClick={handleSave} disabled={saving}>
          {saving ? "Saving..." : "Save Configuration"}
        </Button>
      </div>

      <Modal isOpen={showClearMastery} onClose={() => setShowClearMastery(false)}>
        <div className="space-y-4">
          <h3 className="font-headline text-title-lg text-primary">
            Clear Mastery &amp; Quiz History
          </h3>
          <p className="font-body text-body-sm text-on-surface-variant">
            This will permanently delete all quiz history and reset mastery scores to zero. This cannot be undone.
          </p>
          <div className="flex gap-3 justify-end">
            <Button variant="secondary" onClick={() => setShowClearMastery(false)}>
              Cancel
            </Button>
            <Button
              variant="primary"
              onClick={async () => {
                await clearMastery();
                setShowClearMastery(false);
              }}
            >
              Clear Mastery
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
