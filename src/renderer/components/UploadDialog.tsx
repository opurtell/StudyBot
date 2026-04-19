import { useCallback, useRef, useState } from "react";
import Modal from "./Modal";
import Button from "./Button";
import { useApi } from "../hooks/useApi";
import { useService } from "../hooks/useService";
import type { AcceptedFormatsResponse } from "../types/api";

interface UploadDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onUploaded: () => void;
}

export default function UploadDialog({ isOpen, onClose, onUploaded }: UploadDialogProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [scope, setScope] = useState<"service-specific" | "general">("service-specific");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { data: formats } = useApi<AcceptedFormatsResponse>("/upload/formats", 1);
  const { services, activeService } = useService();
  const [selectedServiceId, setSelectedServiceId] = useState<string>("");
  const safeServices = Array.isArray(services) ? services : [];

  // Pre-select active service when it becomes available
  const initialisedRef = useRef(false);
  if (!initialisedRef.current && activeService?.id) {
    setSelectedServiceId(activeService.id);
    initialisedRef.current = true;
  }

  const acceptedExtensions = formats?.extensions ?? [".md", ".pdf", ".txt"];
  const acceptString = acceptedExtensions.join(",");

  const validateFile = useCallback(
    (file: File): string | null => {
      const ext = "." + file.name.split(".").pop()?.toLowerCase();
      if (!acceptedExtensions.includes(ext)) {
        return `Unsupported format: ${ext}. Accepted: ${acceptedExtensions.join(", ")}`;
      }
      return null;
    },
    [acceptedExtensions]
  );

  const handleFileSelect = useCallback(
    (file: File) => {
      const validationError = validateFile(file);
      if (validationError) {
        setError(validationError);
        setSelectedFile(null);
        return;
      }
      setError(null);
      setSelectedFile(file);
    },
    [validateFile]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const file = e.dataTransfer.files[0];
      if (file) handleFileSelect(file);
    },
    [handleFileSelect]
  );

  const handleUpload = useCallback(async () => {
    if (!selectedFile) return;
    setUploading(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append("file", selectedFile);
      if (selectedServiceId) {
        formData.append("service_id", selectedServiceId);
      }
      formData.append("scope", scope);

      const response = await fetch("http://127.0.0.1:7777/upload", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const body = await response.json();
        throw new Error(body.detail || `Upload failed (${response.status})`);
      }

      setSelectedFile(null);
      onUploaded();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }, [selectedFile, onUploaded, onClose]);

  const handleClose = useCallback(() => {
    if (!uploading) {
      setSelectedFile(null);
      setError(null);
      onClose();
    }
  }, [uploading, onClose]);

  return (
    <Modal isOpen={isOpen} onClose={handleClose}>
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-headline text-display-sm text-primary">
          Add Documentation
        </h3>
      </div>

      <div
        className={`
          border-2 border-dashed rounded-lg p-8 text-center cursor-pointer
          transition-colors duration-200
          ${dragOver ? "border-primary bg-primary/5" : "border-outline-variant/20 hover:border-outline-variant/40"}
        `}
        onClick={() => fileInputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
      >
        <span className="material-symbols-outlined text-3xl text-on-surface-variant mb-2 block">
          upload_file
        </span>
        <p className="font-body text-body-md text-on-surface-variant mb-1">
          {selectedFile ? selectedFile.name : "Drag and drop a file, or click to browse"}
        </p>
        <p className="font-mono text-[10px] text-on-surface-variant">
          Accepted: {acceptedExtensions.join(", ")}
        </p>
        <input
          ref={fileInputRef}
          type="file"
          accept={acceptString}
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) handleFileSelect(file);
          }}
        />
      </div>

      {/* Service and scope selectors */}
      <div className="flex gap-4 mt-4">
        <div className="flex-1">
          <label className="font-label text-[10px] text-on-surface-variant uppercase tracking-widest block mb-1">
            Service
          </label>
          <select
            value={selectedServiceId}
            onChange={(e) => setSelectedServiceId(e.target.value)}
            className="w-full bg-surface-container-lowest text-on-surface font-mono text-[11px] px-3 py-2"
          >
            {safeServices.map((svc) => (
              <option key={svc.id} value={svc.id}>
                {svc.display_name}
              </option>
            ))}
          </select>
        </div>
        <div className="flex-1">
          <label className="font-label text-[10px] text-on-surface-variant uppercase tracking-widest block mb-1">
            Scope
          </label>
          <select
            value={scope}
            onChange={(e) => setScope(e.target.value as "service-specific" | "general")}
            className="w-full bg-surface-container-lowest text-on-surface font-mono text-[11px] px-3 py-2"
          >
            <option value="service-specific">Service-specific</option>
            <option value="general">General</option>
          </select>
        </div>
      </div>

      {error && (
        <p className="font-body text-body-sm text-error mt-3">{error}</p>
      )}

      {selectedFile && (
        <p className="font-body text-body-sm text-on-surface-variant mt-3">
          {(selectedFile.size / 1024).toFixed(1)} KB
        </p>
      )}

      <div className="flex justify-end gap-3 mt-6">
        <Button variant="tertiary" onClick={handleClose} disabled={uploading}>
          Cancel
        </Button>
        <Button
          variant="primary"
          onClick={handleUpload}
          disabled={!selectedFile || uploading}
        >
          {uploading ? "Uploading..." : "Upload"}
        </Button>
      </div>
    </Modal>
  );
}
