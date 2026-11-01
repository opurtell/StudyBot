import { useParams } from "react-router";
import { DocumentList } from "../components/DocumentList";
import { DocumentView } from "../components/DocumentView";
import { api } from "../lib/api";
import { useLoad } from "../lib/useLoad";

export function Medications() {
  const { data, error, loading } = useLoad(() => api.medications(), []);
  return (
    <div className="space-y-6">
      <section className="space-y-2">
        <h1 className="font-headline text-3xl font-semibold">Medications</h1>
        <p className="text-on-surface-variant">ACTAS medicine monographs: presentations, uses, contraindications and doses.</p>
      </section>
      {loading && <p className="text-on-surface-variant">Loading…</p>}
      {error && (
        <p role="alert" className="rounded-sm bg-error-container p-3 text-sm text-error">
          {error}
        </p>
      )}
      {data && data.items.length === 0 && <p className="text-on-surface-variant">The medicines haven't been loaded yet.</p>}
      {data && data.items.length > 0 && (
        <DocumentList items={data.items} basePath="/medications" filterLabel="Filter medicines" grouped={false} />
      )}
    </div>
  );
}

export function MedicationDetail() {
  const { id = "" } = useParams();
  return <DocumentView id={id} load={api.medication} backTo="/medications" backLabel="All medications" />;
}
