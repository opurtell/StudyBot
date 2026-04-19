import { useState } from "react";
import SourceCard from "../components/SourceCard";
import CleaningFeed from "../components/CleaningFeed";
import RepositoryFilter from "../components/RepositoryFilter";
import Button from "../components/Button";
import UploadDialog from "../components/UploadDialog";
import { ServiceChip } from "../components/ServiceChip";
import { useApi } from "../hooks/useApi";
import type { LibraryStatusResponse } from "../types/api";

export default function Library() {
  const [activeFilter, setActiveFilter] = useState("all");
  const [feedVisible, setFeedVisible] = useState(true);
  const [uploadOpen, setUploadOpen] = useState(false);
  const { data, loading, error, refetch } = useApi<LibraryStatusResponse>("/sources", 1);

  const sources = data?.sources ?? [];
  const cleaningItems = data?.cleaning_feed ?? [];

  const filtered =
    activeFilter === "all"
      ? sources
      : sources.filter((s) => s.filter_type === activeFilter);

  return (
    <div>
      <div className="flex items-end justify-between mb-8">
        <div>
          <div className="mb-2">
            <ServiceChip />
          </div>
          <span className="font-label text-label-sm text-on-surface-variant">
            Library
          </span>
          <h2 className="font-headline text-display-lg text-primary">
            Source Pipeline
          </h2>
        </div>
        <Button variant="secondary" onClick={() => setUploadOpen(true)}>
          <span className="material-symbols-outlined text-sm">add</span>
          New Documentation
        </Button>
      </div>

      <div className="grid grid-cols-12 gap-8">
        <div className="col-span-12 lg:col-span-8">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-label text-label-sm text-on-surface-variant">
              Document Repository
            </h3>
            <span className="font-mono text-[10px] text-on-surface-variant">
              {filtered.filter((s) => s.progress >= 100).length} ACTIVE SOURCES
            </span>
          </div>
          <div className="mb-4">
            <RepositoryFilter activeType={activeFilter} onTypeChange={setActiveFilter} />
          </div>
          {loading && (
            <div className="bg-surface-container-lowest p-6 font-body text-body-md text-on-surface-variant">
              Loading source repository...
            </div>
          )}
          {error && (
            <div className="bg-surface-container-lowest p-6 font-body text-body-md text-error">
              Failed to load source repository: {error}
            </div>
          )}
          {!loading && !error && filtered.length === 0 && (
            <div className="bg-surface-container-lowest p-6 font-body text-body-md text-on-surface-variant">
              No sources match the current filter.
            </div>
          )}
          {!loading && !error && filtered.length > 0 && (
            <div className="space-y-4">
              {filtered.map((source) => (
                <SourceCard
                  key={source.id}
                  id={source.id}
                  name={source.name}
                  type={source.type}
                  progress={source.progress}
                  statusText={source.status_text}
                  detail={source.detail}
                />
              ))}
            </div>
          )}
        </div>

        <div className="col-span-12 lg:col-span-4">
          <div className="sticky top-24">
            <CleaningFeed
              items={cleaningItems}
              visible={feedVisible}
              onToggle={() => setFeedVisible(!feedVisible)}
            />
          </div>
        </div>
      </div>
      <UploadDialog
        isOpen={uploadOpen}
        onClose={() => setUploadOpen(false)}
        onUploaded={refetch}
      />
    </div>
  );
}
