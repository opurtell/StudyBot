import { useState, useMemo, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import MarkdownRenderer from "../components/MarkdownRenderer";
import { useApi } from "../hooks/useApi";
import { useSettings } from "../hooks/useSettings";
import Card from "../components/Card";
import AdaptiveText from "../components/AdaptiveText";
import PageStateNotice from "../components/PageStateNotice";
import type { GuidelineSummary, GuidelineDetail } from "../types/api";
import { useBackendStatus, useBackendStatusActions } from "../hooks/useBackendStatus";
import { getErrorStateCopy } from "../lib/loadingState";
import { useBackgroundProcesses } from "../providers/BackgroundProcessProvider";

const SECTION_ORDER = [
  "Cardiac",
  "Respiratory",
  "Airway Management",
  "Neurology",
  "Trauma",
  "Medicine",
  "Medical",
  "Pain Management",
  "Toxicology",
  "Environmental",
  "Obstetric",
  "Behavioural",
  "HAZMAT",
  "Palliative Care",
  "General Care",
  "Clinical Skill",
  "Other",
];

const TYPE_FILTERS = [
  { key: "all", label: "All" },
  { key: "cmg", label: "CMG" },
  { key: "med", label: "Medication" },
  { key: "csm", label: "Clinical Skill" },
] as const;

const TYPE_TAG_COLOUR: Record<string, string> = {
  cmg: "bg-primary/15 text-primary",
  med: "bg-tertiary-fixed/20 text-on-surface",
  csm: "bg-on-surface-variant/10 text-on-surface-variant",
};

export default function Guidelines() {
  const navigate = useNavigate();
  const { config } = useSettings();
  const { data: guidelines, loading, error, refetch } = useApi<GuidelineSummary[]>("/guidelines");
  const backendStatus = useBackendStatus();
  const { restart } = useBackendStatusActions();
  const { isSeeding } = useBackgroundProcesses();

  const [selectedType, setSelectedType] = useState<string>("all");
  const [selectedSection, setSelectedSection] = useState<string>("all");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [scopePickerOpen, setScopePickerOpen] = useState(false);

  const { data: detail } = useApi<GuidelineDetail>(
    selectedId ? `/guidelines/${selectedId}` : ""
  );
  const errorCopy = getErrorStateCopy(error, backendStatus, "guidelines");

  // Track previous seeding state to detect completion
  const wasSeedingRef = useRef(false);
  useEffect(() => {
    if (wasSeedingRef.current && !isSeeding) {
      // Seeding just completed — refetch guidelines
      void refetch();
    }
    wasSeedingRef.current = isSeeding;
  }, [isSeeding, refetch]);

  const filtered = useMemo(() => {
    if (!guidelines) return [];
    return guidelines.filter((g) => {
      // Filter by skill level if user is AP
      if (config?.skill_level === "AP" && g.is_icp_only) return false;
      
      if (selectedType !== "all" && g.source_type !== selectedType) return false;
      if (selectedSection !== "all" && g.section !== selectedSection) return false;
      return true;
    });
  }, [guidelines, selectedType, selectedSection, config?.skill_level]);

  const sections = useMemo(() => {
    const present = new Set(filtered.map((g) => g.section));
    const ordered = SECTION_ORDER.filter((s) => present.has(s));
    for (const s of Array.from(present).sort()) {
      if (!ordered.includes(s)) ordered.push(s);
    }
    return ordered;
  }, [filtered]);

  const grouped = useMemo(() => {
    const map = new Map<string, GuidelineSummary[]>();
    for (const g of filtered) {
      const arr = map.get(g.section) || [];
      arr.push(g);
      map.set(g.section, arr);
    }
    return map;
  }, [filtered]);

  const allSections = useMemo(() => {
    if (!guidelines) return [];
    const s = new Set(guidelines.map((g) => g.section));
    return Array.from(s).sort();
  }, [guidelines]);

  function handleStartRevision(scope: "guideline" | "section" | "all") {
    navigate("/quiz", {
      state: {
        scope,
        guidelineId: selectedId,
        section: detail?.section,
      },
    });
  }

  return (
    <div>
      <div className="mb-8">
        <span className="font-label text-label-sm text-on-surface-variant">
          Clinical Reference
        </span>
        <h2 className="font-headline text-display-lg text-primary">
          Clinical Guidelines
        </h2>
        <p className="font-body text-body-md text-on-surface-variant mt-1">
          Browse CMGs, medicine monographs, and clinical skills from ACTAS guidelines.
        </p>
      </div>

      {loading && !guidelines && (
        <PageStateNotice
          title={isSeeding ? "Indexing clinical guidelines" : "Loading guidelines"}
          message={isSeeding ? "Building search index from bundled CMG data. This may take a moment on first launch." : "Preparing the ACTAS guideline index."}
        />
      )}

      {!loading && !error && guidelines && guidelines.length === 0 && isSeeding && (
        <PageStateNotice
          title="Indexing clinical guidelines"
          message="Building search index from bundled CMG data. This may take a moment on first launch."
        />
      )}

      {error && !guidelines && (
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
            void refetch();
          }}
        />
      )}

      {guidelines && (
        <>
          {(loading || error) && (
            <div className="flex items-center justify-between mb-4 gap-4">
              <span className={`font-mono text-[10px] ${error ? "text-status-critical" : "text-on-surface-variant"}`}>
                {error
                  ? `${errorCopy.title}. Showing the last loaded guideline index.`
                  : "Refreshing guideline index..."}
              </span>
              <button
                onClick={() => void refetch()}
                className="font-label text-[10px] uppercase tracking-widest text-primary"
              >
                Refresh
              </button>
            </div>
          )}
          <div className="flex items-center gap-4 mb-8 flex-wrap">
            <div className="flex gap-2">
              {TYPE_FILTERS.map((tf) => (
                <button
                  key={tf.key}
                  onClick={() => setSelectedType(tf.key)}
                  className={`px-3 py-1.5 font-label text-[10px] uppercase tracking-widest transition-colors ${
                    selectedType === tf.key
                      ? "bg-primary text-on-primary"
                      : "bg-surface-container-low text-on-surface-variant hover:bg-surface-container-lowest"
                  }`}
                >
                  {tf.label}
                </button>
              ))}
            </div>

            <select
              value={selectedSection}
              onChange={(e) => setSelectedSection(e.target.value)}
              className="bg-surface-container-low text-on-surface font-label text-[10px] uppercase tracking-widest px-3 py-1.5 appearance-none cursor-pointer"
            >
              <option value="all">All Sections</option>
              {allSections.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>

            <span className="font-mono text-[10px] text-on-surface-variant ml-auto">
              {filtered.length} guidelines
            </span>
          </div>

          {guidelines.length === 0 && (
            <PageStateNotice
              title="No guidelines available"
              message="Run the CMG refresh or pipeline import to rebuild the local guideline index."
            />
          )}

          {guidelines.length > 0 && sections.length === 0 && (
            <PageStateNotice
              title="No matching guidelines"
              message="Adjust the current filters to widen the guideline list."
            />
          )}

          {sections.map((section) => (
            <div key={section} className="mb-10">
              <h3 className="font-headline text-title-lg text-on-surface-variant mb-4">
                {section}
              </h3>
              <div className="grid grid-cols-3 gap-4">
                {(grouped.get(section) || []).map((g) => (
                  <Card
                    key={g.id}
                    onClick={() => {
                      setSelectedId(g.id);
                      setScopePickerOpen(false);
                    }}
                  >
                    <div className="flex items-start justify-between mb-2">
                      <span className="font-mono text-[10px] text-on-surface-variant">
                        CMG {g.cmg_number}
                      </span>
                      <span
                        className={`font-label text-[9px] uppercase tracking-widest px-2 py-0.5 rounded-sm ${
                          TYPE_TAG_COLOUR[g.source_type] || ""
                        }`}
                      >
                        {g.source_type === "csm"
                          ? "Skill"
                          : g.source_type === "med"
                          ? "Med"
                          : "CMG"}
                      </span>
                      {g.is_icp_only && (
                        <span className="font-label text-[9px] uppercase tracking-widest px-2 py-0.5 rounded-sm bg-status-critical/10 text-status-critical ml-1">
                          ICP
                        </span>
                      )}
                    </div>
                    <AdaptiveText
                      text={g.title}
                      variant="headline"
                      className="text-primary mt-1"
                    />
                  </Card>
                ))}
              </div>
            </div>
          ))}
        </>
      )}

      {selectedId && detail && (
        <>
          <div
            className="fixed inset-0 bg-on-surface/20 z-40"
            onClick={() => {
              setSelectedId(null);
              setScopePickerOpen(false);
            }}
          />
          <div className="fixed right-0 top-0 h-screen w-[40%] min-w-[480px] bg-surface-container-low z-50 flex flex-col overflow-hidden shadow-2xl">
            <div className="p-8 pb-4 flex items-start justify-between">
              <div>
                <span className="font-mono text-[10px] text-on-surface-variant">
                  CMG {detail.cmg_number}
                </span>
                <h2 className="font-headline text-title-xl text-primary mt-1">
                  {detail.title}
                </h2>
                <span className="font-label text-[10px] uppercase tracking-widest text-on-surface-variant mt-1 block">
                  {detail.section}
                  {detail.is_icp_only && (
                    <span className="ml-2 text-status-critical">| ICP ONLY</span>
                  )}
                </span>
              </div>
              <button
                onClick={() => {
                  setSelectedId(null);
                  setScopePickerOpen(false);
                }}
                className="text-on-surface-variant hover:text-primary transition-colors p-1"
                aria-label="Close"
              >
                <span className="material-symbols-outlined">close</span>
              </button>
            </div>

            <div className="flex-1 overflow-y-auto px-8 pb-8">
              <MarkdownRenderer content={detail.content_markdown} />

              {detail.dose_lookup && Object.keys(detail.dose_lookup).length > 0 && (
                <div className="mt-8 pt-6 border-t border-outline-variant/15">
                  <h3 className="font-headline text-body-lg text-primary mb-4">
                    Dose Reference
                  </h3>
                  {Object.entries(detail.dose_lookup).map(([medication, entries]) => {
                    const doseEntries = Array.isArray(entries) ? entries : [];
                    return (
                      <div key={medication} className="mb-6 last:mb-0">
                        <h4 className="font-label text-label-lg text-on-surface-variant mb-2">
                          {medication}
                        </h4>
                        <ul className="space-y-1.5 pl-4">
                          {doseEntries.map((entry, i) => (
                            <li
                              key={i}
                              className="font-body text-body-sm text-on-surface leading-relaxed list-disc ml-4"
                            >
                              {typeof entry === "string" ? entry : (entry as Record<string, unknown>).text as string || JSON.stringify(entry)}
                            </li>
                          ))}
                        </ul>
                      </div>
                    );
                  })}
                </div>
              )}

              {detail.flowchart && (
                <div className="mt-8 pt-6 border-t border-outline-variant/15">
                  <h3 className="font-headline text-body-lg text-primary mb-4">
                    Flowchart
                  </h3>
                  {typeof detail.flowchart === "string" ? (
                    <MarkdownRenderer content={detail.flowchart} />
                  ) : (
                    <MarkdownRenderer content={JSON.stringify(detail.flowchart, null, 2)} />
                  )}
                </div>
              )}
            </div>

            <div className="p-6 border-t border-outline-variant/15 bg-surface-container-low">
              {scopePickerOpen && (
                <div className="flex gap-2 mb-3">
                  <button
                    onClick={() => handleStartRevision("guideline")}
                    className="flex-1 px-3 py-2 bg-surface-container-lowest text-on-surface font-label text-[10px] uppercase tracking-widest hover:bg-primary hover:text-on-primary transition-colors"
                  >
                    This Guideline
                  </button>
                  <button
                    onClick={() => handleStartRevision("section")}
                    className="flex-1 px-3 py-2 bg-surface-container-lowest text-on-surface font-label text-[10px] uppercase tracking-widest hover:bg-primary hover:text-on-primary transition-colors"
                  >
                    This Section
                  </button>
                  <button
                    onClick={() => handleStartRevision("all")}
                    className="flex-1 px-3 py-2 bg-surface-container-lowest text-on-surface font-label text-[10px] uppercase tracking-widest hover:bg-primary hover:text-on-primary transition-colors"
                  >
                    All Guidelines
                  </button>
                </div>
              )}
              <button
                onClick={() => setScopePickerOpen(!scopePickerOpen)}
                className="w-full bg-primary text-on-primary py-3 px-4 font-label text-xs uppercase tracking-[0.2em] hover:opacity-90 transition-opacity"
              >
                Start Revision
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
