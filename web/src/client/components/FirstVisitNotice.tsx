import { useState } from "react";
import { Link } from "react-router";

const KEY = "disclaimer-ack-v1";

function acknowledged(): boolean {
  try {
    return window.localStorage.getItem(KEY) === "1";
  } catch {
    return false;
  }
}

export function FirstVisitNotice() {
  const [open, setOpen] = useState(() => !acknowledged());
  if (!open) return null;
  const dismiss = () => {
    try {
      window.localStorage.setItem(KEY, "1");
    } catch {
      /* storage unavailable */
    }
    setOpen(false);
  };
  return (
    <section aria-label="Before you start" className="mb-6 space-y-3 rounded-sm bg-highlight/30 p-4 text-sm">
      <p className="font-semibold">This is a study aid, not clinical guidance.</p>
      <p>
        AI writes the questions and marks your answers, and it can be wrong. Always follow the current ACTAS CMGs and
        your service's directions. Your answers are sent to Google's Gemini service for marking; see the{" "}
        <Link to="/privacy" className="underline">
          privacy policy
        </Link>
        .
      </p>
      <button type="button" onClick={dismiss} className="rounded-sm bg-primary px-4 py-2 font-semibold text-on-primary">
        I understand
      </button>
    </section>
  );
}
