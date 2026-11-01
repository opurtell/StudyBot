import { VIEWS, type CorpusView } from "../corpus/repo";
import prompts from "./prompts.json";

export type Visibility = Record<CorpusView, boolean>;

const COVERED_BY: Record<CorpusView, CorpusView[]> = {
  ap: ["ap", "ap_pacer", "icp", "icp_pacer"],
  ap_pacer: ["ap_pacer", "icp_pacer"],
  icp: ["icp", "icp_pacer"],
  icp_pacer: ["icp_pacer"],
};

const ICP_MENTION = new RegExp(prompts.icpMentionPattern, "i");

export function mentionsIcpOnly(text: string): boolean {
  return ICP_MENTION.test(text);
}

export function questionVisibility(generatedFor: CorpusView, chunk: Visibility, questionText: string): Visibility {
  const allowed = new Set(COVERED_BY[generatedFor]);
  const icpOnly = mentionsIcpOnly(questionText);
  const out = {} as Visibility;
  for (const view of VIEWS) {
    out[view] = allowed.has(view) && chunk[view] && !(icpOnly && (view === "ap" || view === "ap_pacer"));
  }
  return out;
}

export function visibilityFromRow(row: { vis_ap: number; vis_ap_pacer: number; vis_icp: number; vis_icp_pacer: number }): Visibility {
  return { ap: row.vis_ap === 1, ap_pacer: row.vis_ap_pacer === 1, icp: row.vis_icp === 1, icp_pacer: row.vis_icp_pacer === 1 };
}
