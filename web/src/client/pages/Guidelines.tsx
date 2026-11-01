import { useParams, useSearchParams } from "react-router";
import { DocumentList } from "../components/DocumentList";
import { DocumentView } from "../components/DocumentView";
import { api } from "../lib/api";
import { useLoad } from "../lib/useLoad";

const TABS = [
  { kind: "cmg", label: "Guidelines" },
  { kind: "csm", label: "Clinical skills" },
] as const;

export function Guidelines() {
  const [params, setParams] = useSearchParams();
  const kind = params.get("kind") === "csm" ? "csm" : "cmg";
  const { data, error, loading } = useLoad(() => api.guidelines(), []);
  const items = (data?.items ?? []).filter((i) => i.kind === kind);

  return (
    <div className="space-y-6">
      <section className="space-y-2">
        <h1 className="font-headline text-3xl font-semibold">Clinical guidelines</h1>
        <p className="text-on-surface-variant">The ACTAS Clinical Management Guidelines and clinical skills, filtered to your scope of practice.</p>
      </section>
      <div className="flex gap-1" role="tablist" aria-label="Guideline type">
        {TABS.map((tab) => (
          <button
            key={tab.kind}
            type="button"
            role="tab"
            aria-selected={kind === tab.kind}
            onClick={() => setParams(tab.kind === "cmg" ? {} : { kind: tab.kind })}
            className={`rounded-sm px-3 py-2 text-sm font-medium ${
              kind === tab.kind ? "bg-highlight text-on-highlight" : "text-on-surface-variant hover:bg-surface-container"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>
      {loading && <p className="text-on-surface-variant">Loading…</p>}
      {error && (
        <p role="alert" className="rounded-sm bg-error-container p-3 text-sm text-error">
          {error}
        </p>
      )}
      {data && data.items.length === 0 && <p className="text-on-surface-variant">The guidelines haven't been loaded yet.</p>}
      {items.length > 0 && (
        <div role="tabpanel">
          <DocumentList
            key={kind}
            items={items}
            basePath="/guidelines"
            filterLabel={kind === "csm" ? "Filter skills" : "Filter guidelines"}
            grouped={kind === "cmg"}
          />
        </div>
      )}
    </div>
  );
}

export function GuidelineDetail() {
  const { id = "" } = useParams();
  const back = id.includes("CSM.") ? "/guidelines?kind=csm" : "/guidelines";
  return <DocumentView id={id} load={api.guideline} backTo={back} backLabel="All guidelines" />;
}
