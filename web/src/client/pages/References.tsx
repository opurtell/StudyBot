import { Link, useParams } from "react-router";
import { DocumentList } from "../components/DocumentList";
import { DocumentView } from "../components/DocumentView";
import { api } from "../lib/api";
import { useLoad } from "../lib/useLoad";

export function References() {
  const { data, error, loading } = useLoad(() => api.references(), []);
  return (
    <div className="space-y-6">
      <section className="space-y-2">
        <h1 className="font-headline text-3xl font-semibold">Pathophysiology and ECGs</h1>
        <p className="text-on-surface-variant">
          General open references behind the pathophysiology and ECG questions. They are not ACTAS guidelines: where they
          differ, the CMGs take precedence. <Link to="/sources" className="underline">Sources and licences</Link>
        </p>
      </section>
      {loading && <p className="text-on-surface-variant">Loading…</p>}
      {error && (
        <p role="alert" className="rounded-sm bg-error-container p-3 text-sm text-error">
          {error}
        </p>
      )}
      {data && data.items.length === 0 && <p className="text-on-surface-variant">The general references haven't been loaded yet.</p>}
      {data && data.items.length > 0 && <DocumentList items={data.items} basePath="/references" filterLabel="Filter references" />}
    </div>
  );
}

export function ReferenceDetail() {
  const { id = "" } = useParams();
  return <DocumentView id={id} load={api.reference} backTo="/references" backLabel="All references" />;
}
