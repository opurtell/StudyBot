import { useState } from "react";
import Button from "./Button";

interface BlacklistManagerProps {
  items: string[];
  loading: boolean;
  onAdd: (name: string) => Promise<void>;
  onRemove: (name: string) => Promise<void>;
}

export default function BlacklistManager({ items, loading, onAdd, onRemove }: BlacklistManagerProps) {
  const [newItem, setNewItem] = useState("");

  const handleAdd = async () => {
    const trimmed = newItem.trim();
    if (!trimmed) return;
    await onAdd(trimmed);
    setNewItem("");
  };

  return (
    <div className="space-y-4">
      <h3 className="font-label text-label-sm text-on-surface-variant uppercase">
        Quiz Blacklist
      </h3>
      <div className="flex gap-2">
        <input
          type="text"
          value={newItem}
          onChange={(e) => setNewItem(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") handleAdd(); }}
          placeholder="Category or topic to exclude..."
          className="flex-1 bg-transparent border-0 border-b border-outline-variant/20 text-on-surface font-body text-body-md py-2 focus:border-primary focus:outline-none placeholder:text-on-surface-variant/40"
        />
        <Button onClick={handleAdd} disabled={loading || !newItem.trim()} variant="secondary">
          Add
        </Button>
      </div>
      {items.length === 0 && (
        <p className="font-body text-body-md text-on-surface-variant italic">
          No items blacklisted.
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        {items.map((item) => (
          <span
            key={item}
            className="inline-flex items-center gap-2 bg-surface-container-highest px-3 py-1"
          >
            <span className="font-label text-[9px] uppercase tracking-widest text-on-surface-variant">
              {item}
            </span>
            <button
              onClick={() => onRemove(item)}
              className="text-on-surface-variant hover:text-status-critical transition-colors"
              aria-label={`Remove ${item} from blacklist`}
            >
              <span className="material-symbols-outlined text-sm">close</span>
            </button>
          </span>
        ))}
      </div>
    </div>
  );
}
