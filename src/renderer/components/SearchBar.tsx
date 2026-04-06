import { useState, useEffect, useRef, type KeyboardEvent } from "react";
import type { SearchResult } from "../types/api";
import { apiGet, isApiClientError } from "../lib/apiClient";
import { useBackendStatus } from "../hooks/useBackendStatus";

interface SearchBarProps {
  placeholder?: string;
  className?: string;
}

export default function SearchBar({
  placeholder = "Search the archive...",
  className = "",
}: SearchBarProps) {
  const backendStatus = useBackendStatus();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [showDropdown, setShowDropdown] = useState(false);
  const [availabilityMessage, setAvailabilityMessage] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (backendStatus.state !== "ready") {
      setResults([]);
      setShowDropdown(false);
      setLoading(false);
      setAvailabilityMessage("Search is unavailable while the backend is offline.");
      return;
    }
    setAvailabilityMessage(null);
  }, [backendStatus.state]);

  useEffect(() => {
    if (backendStatus.state !== "ready") {
      return;
    }

    if (query.trim().length < 2) {
      setResults([]);
      setShowDropdown(false);
      return;
    }

    const timer = setTimeout(async () => {
      if (abortRef.current) abortRef.current.abort();
      const ctrl = new AbortController();
      abortRef.current = ctrl;

      setLoading(true);
      try {
        const data = await apiGet<SearchResult[]>(
          `/search?q=${encodeURIComponent(query.trim())}`,
          { signal: ctrl.signal }
        );
        if (ctrl.signal.aborted) {
          return;
        }
        if (!data) {
          setResults([]);
          setShowDropdown(false);
          return;
        }
        setResults(data);
        setShowDropdown(data.length > 0);
      } catch (error) {
        if (
          error instanceof DOMException &&
          error.name === "AbortError"
        ) {
          return;
        }
        if (
          isApiClientError(error) &&
          (error.category === "backend-starting" || error.category === "backend-unavailable")
        ) {
          setAvailabilityMessage("Search is unavailable while the backend is offline.");
          setResults([]);
          setShowDropdown(false);
          return;
        }
        return;
      } finally {
        if (!ctrl.signal.aborted) {
          setLoading(false);
        }
      }
    }, 300);

    return () => {
      clearTimeout(timer);
      abortRef.current?.abort();
    };
  }, [backendStatus.state, query]);

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Escape") {
      setShowDropdown(false);
    }
  };

  const sourceLabel = (type: string) => {
    if (type === "cmg") return "CMG";
    if (type === "ref_doc") return "REF";
    if (type === "cpd_doc") return "CPD";
    if (type === "notability_note") return "NOTE";
    return type.toUpperCase();
  };

  return (
    <div className={`relative ${className}`}>
      <div className="flex items-center gap-3 bg-surface-container-low px-4 py-3">
        <span className="material-symbols-outlined text-on-surface-variant text-xl select-none">
          {loading ? "hourglass_empty" : "search"}
        </span>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => results.length > 0 && setShowDropdown(true)}
          onBlur={() => setTimeout(() => setShowDropdown(false), 200)}
          placeholder={placeholder}
          aria-label="Search the archive"
          disabled={backendStatus.state !== "ready"}
          className="w-full bg-transparent text-on-surface font-body text-body-md placeholder:text-on-surface-variant/40 focus:outline-none"
        />
      </div>
      {availabilityMessage && (
        <p className="mt-2 font-mono text-[10px] text-on-surface-variant">
          {availabilityMessage}
        </p>
      )}

      {showDropdown && results.length > 0 && (
        <div className="absolute top-full left-0 right-0 z-50 bg-surface-container-low border border-outline-variant/10 mt-1 max-h-80 overflow-y-auto">
          {results.map((r, i) => (
            <div
              key={i}
              className="px-4 py-3 hover:bg-surface-container-lowest border-b border-outline-variant/5 last:border-b-0"
            >
              <div className="flex items-center gap-2 mb-1">
                <span className="font-mono text-[9px] px-1 bg-tertiary-fixed/30 text-on-surface-variant">
                  {sourceLabel(r.source_type)}
                </span>
                {r.cmg_number && (
                  <span className="font-mono text-[9px] text-on-surface-variant">
                    CMG {r.cmg_number}
                  </span>
                )}
                {r.category && (
                  <span className="font-mono text-[9px] text-on-surface-variant">
                    {r.category}
                  </span>
                )}
              </div>
              <p className="font-body text-body-sm text-on-surface line-clamp-2">
                {r.content}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
