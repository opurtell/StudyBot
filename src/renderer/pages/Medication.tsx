import MarkdownRenderer from "../components/MarkdownRenderer";
import { useApi } from "../hooks/useApi";
import { useSettings } from "../hooks/useSettings";
import type { MedicationDose } from "../types/api";
import PageStateNotice from "../components/PageStateNotice";
import { useBackendStatus, useBackendStatusActions } from "../hooks/useBackendStatus";
import { getErrorStateCopy } from "../lib/loadingState";

function Section({ label, text }: { label: string; text: string }) {
  return (
    <div>
      <span className="font-mono text-[10px] text-on-surface-variant uppercase tracking-wider">
        {label}
      </span>
      <MarkdownRenderer
        content={text}
        className="mt-1 [&_p]:text-body-sm [&_li]:text-body-sm [&_ul]:my-1 [&_ol]:my-1 [&_h1]:mt-2 [&_h2]:mt-2 [&_h3]:mt-2 [&_h4]:mt-2"
      />
    </div>
  );
}

export default function Medication() {
  const { config } = useSettings();
  const { data: medicines, loading, error, refetch } = useApi<MedicationDose[]>("/medication/doses", 4);
  const backendStatus = useBackendStatus();
  const { restart } = useBackendStatusActions();
  const errorCopy = getErrorStateCopy(error, backendStatus, "medication data");

  const filtered = (medicines || []).filter((med) => {
    if (config?.skill_level === "AP" && med.is_icp_only) return false;
    return true;
  });

  return (
    <div>
      <div className="mb-8">
        <span className="font-label text-label-sm text-on-surface-variant">
          Pharmacological Reference
        </span>
        <h2 className="font-headline text-display-lg text-primary">
          Medications
        </h2>
        <p className="font-body text-body-md text-on-surface-variant mt-1">
          Indications, contraindications, adverse effects, precautions, and doses drawn from ACTAS CMGs.
        </p>
      </div>

      {loading && !medicines && (
        <PageStateNotice
          loading
          title="Loading medications"
          message="Preparing the ACTAS medication reference."
        />
      )}

      {error && !medicines && (
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

      {(loading || error) && medicines && (
        <div className="mb-4 flex items-center justify-between gap-4">
          <span className={`font-mono text-[10px] ${error ? "text-status-critical" : "text-on-surface-variant"}`}>
            {error
              ? `${errorCopy.title}. Showing the last loaded medication index.`
              : "Refreshing medication index..."}
          </span>
          <button
            onClick={() => void refetch()}
            className="font-label text-[10px] uppercase tracking-widest text-primary"
          >
            Refresh
          </button>
        </div>
      )}

      {filtered && filtered.length > 0 && (
        <div className="space-y-4">
          {filtered.map((med, i) => (
            <div key={i} className="bg-surface-container-low p-6 hover:bg-surface-container-lowest transition-colors">
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-3">
                  <h3 className="font-headline text-title-lg text-primary">{med.name}</h3>
                  {med.is_icp_only && (
                    <span className="font-label text-[9px] uppercase tracking-widest px-2 py-0.5 rounded-sm bg-status-critical/10 text-status-critical">
                      ICP ONLY
                    </span>
                  )}
                </div>
                <span className="font-mono text-[10px] text-on-surface-variant">
                  {med.cmg_reference}
                </span>
              </div>
              <div className="space-y-3">
                <Section label="Indications" text={med.indication} />
                <Section label="Contraindications" text={med.contraindications} />
                <Section label="Adverse Effects" text={med.adverse_effects} />
                <Section label="Precautions" text={med.precautions} />
                <Section label="Doses" text={med.dose} />
              </div>
            </div>
          ))}
        </div>
      )}

      {medicines && medicines.length === 0 && (
        <PageStateNotice
          title="No medications available"
          message="Medication data will appear here once the CMG pipeline has been run."
        />
      )}

      {medicines && medicines.length > 0 && filtered.length === 0 && (
        <PageStateNotice
          title="No medications in scope"
          message="The current skill level hides ICP-only medication entries."
        />
      )}
    </div>
  );
}
