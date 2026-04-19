import { useState, useCallback, useMemo, useEffect } from "react";
import { useService } from "../hooks/useService";
import { useSettingsContext } from "../providers/SettingsProvider";
import Button from "./Button";

interface ServiceSetupModalProps {
  open: boolean;
  onClose?: () => void;
}

export function ServiceSetupModal({ open, onClose }: ServiceSetupModalProps) {
  const { services, setActiveService, loading } = useService();
  const { save, config } = useSettingsContext();

  const [selectedServiceId, setSelectedServiceId] = useState<string | null>(null);
  const [selectedBaseId, setSelectedBaseId] = useState<string | null>(null);
  const [selectedEndorsementIds, setSelectedEndorsementIds] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);

  const selectedService = useMemo(
    () => services.find((s) => s.id === selectedServiceId) ?? null,
    [services, selectedServiceId]
  );

  const filteredEndorsements = useMemo(() => {
    if (!selectedService || !selectedBaseId) return [];
    return selectedService.qualifications.endorsements.filter((e) =>
      e.requires_base.includes(selectedBaseId)
    );
  }, [selectedService, selectedBaseId]);

  // Reset base and endorsements when service changes
  useEffect(() => {
    setSelectedBaseId(null);
    setSelectedEndorsementIds([]);
  }, [selectedServiceId]);

  const canSave = selectedServiceId !== null && selectedBaseId !== null && !saving;

  const handleSave = useCallback(async () => {
    if (!selectedServiceId || !selectedBaseId) return;
    setSaving(true);
    try {
      await setActiveService(selectedServiceId);
      if (config) {
        await save({
          ...config,
          base_qualification: selectedBaseId,
          endorsements: selectedEndorsementIds,
        } as typeof config & { base_qualification: string; endorsements: string[] });
      }
    } finally {
      setSaving(false);
    }
  }, [selectedServiceId, selectedBaseId, selectedEndorsementIds, setActiveService, save, config]);

  const handleEndorsementToggle = useCallback((id: string) => {
    setSelectedEndorsementIds((prev) =>
      prev.includes(id) ? prev.filter((e) => e !== id) : [...prev, id]
    );
  }, []);

  const handleBackdropClick = useCallback(() => {
    if (onClose) onClose();
  }, [onClose]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Escape" && onClose) onClose();
    },
    [onClose]
  );

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
      onClick={handleBackdropClick}
      onKeyDown={handleKeyDown}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Service setup"
        className="bg-surface-container-lowest rounded-lg shadow-ambient max-w-lg w-full mx-4 p-6 max-h-[85vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="font-headline text-headline-sm text-on-surface mb-1">
          Select Your Service
        </h2>
        <p className="text-body-md text-on-surface-variant mb-6">
          Choose your ambulance service and qualification level to get started.
        </p>

        {loading ? (
          <div className="flex justify-center py-8">
            <div className="loading-spinner" />
          </div>
        ) : (
          <>
            {/* Step 1: Service selection */}
            <div className="mb-6">
              <h3 className="font-label text-label-sm text-on-surface-variant uppercase tracking-wider mb-3">
                Service
              </h3>
              <div className="space-y-2">
                {services.map((service) => (
                  <button
                    key={service.id}
                    type="button"
                    onClick={() => setSelectedServiceId(service.id)}
                    className={`
                      w-full text-left px-4 py-3 rounded-lg transition-colors duration-200
                      flex items-center gap-3
                      ${
                        selectedServiceId === service.id
                          ? "bg-surface-container-high"
                          : "bg-surface-container-low hover:bg-surface-container"
                      }
                    `}
                  >
                    <span
                      className="w-3 h-3 rounded-full shrink-0"
                      style={{ backgroundColor: service.accent_colour }}
                    />
                    <div className="flex-1 min-w-0">
                      <div className="font-body text-body-md text-on-surface font-medium">
                        {service.display_name}
                      </div>
                      <div className="text-body-md text-on-surface-variant">
                        {service.region}
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            </div>

            {/* Step 2: Qualification base (shown after service selection) */}
            {selectedService && (
              <div className="mb-6">
                <h3 className="font-label text-label-sm text-on-surface-variant uppercase tracking-wider mb-3">
                  Qualification Base
                </h3>
                <div className="space-y-2">
                  {selectedService.qualifications.bases.map((base) => (
                    <label
                      key={base.id}
                      className={`
                        flex items-center gap-3 px-4 py-3 rounded-lg transition-colors duration-200 cursor-pointer
                        ${
                          selectedBaseId === base.id
                            ? "bg-surface-container-high"
                            : "bg-surface-container-low hover:bg-surface-container"
                        }
                      `}
                    >
                      <input
                        type="radio"
                        name="qualification-base"
                        value={base.id}
                        checked={selectedBaseId === base.id}
                        onChange={() => setSelectedBaseId(base.id)}
                        className="accent-primary"
                      />
                      <span className="font-body text-body-md text-on-surface">
                        {base.display}
                      </span>
                    </label>
                  ))}
                </div>
              </div>
            )}

            {/* Step 3: Endorsements (shown after base selection, if any match) */}
            {selectedService && selectedBaseId && filteredEndorsements.length > 0 && (
              <div className="mb-6">
                <h3 className="font-label text-label-sm text-on-surface-variant uppercase tracking-wider mb-3">
                  Endorsements
                </h3>
                <div className="space-y-2">
                  {filteredEndorsements.map((endo) => (
                    <label
                      key={endo.id}
                      className={`
                        flex items-center gap-3 px-4 py-3 rounded-lg transition-colors duration-200 cursor-pointer
                        ${
                          selectedEndorsementIds.includes(endo.id)
                            ? "bg-surface-container-high"
                            : "bg-surface-container-low hover:bg-surface-container"
                        }
                      `}
                    >
                      <input
                        type="checkbox"
                        checked={selectedEndorsementIds.includes(endo.id)}
                        onChange={() => handleEndorsementToggle(endo.id)}
                        className="accent-primary"
                      />
                      <span className="font-body text-body-md text-on-surface">
                        {endo.display}
                      </span>
                    </label>
                  ))}
                </div>
              </div>
            )}

            {/* Actions */}
            <div className="flex justify-end gap-3">
              {onClose && (
                <Button variant="tertiary" onClick={onClose}>
                  Cancel
                </Button>
              )}
              <Button
                variant="primary"
                disabled={!canSave}
                onClick={handleSave}
              >
                {saving ? "Saving..." : "Confirm"}
              </Button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
