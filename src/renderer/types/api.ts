export interface CategoryMastery {
  category: string;
  total_attempts: number;
  correct: number;
  partial: number;
  incorrect: number;
  mastery_percent: number;
  status: "strong" | "developing" | "weak";
}

export interface QuizAttempt {
  id: number;
  question_id: string;
  category: string;
  question_type: string;
  score: "correct" | "partial" | "incorrect" | null;
  elapsed_seconds: number;
  source_citation: string;
  created_at: string;
}

export interface StartSessionRequest {
  mode: "topic" | "gap_driven" | "random" | "clinical_guidelines";
  topic?: string;
  guideline_id?: string;
  difficulty?: "easy" | "medium" | "hard";
  randomize?: boolean;
}

export interface StartSessionResponse {
  session_id: string;
  mode: string;
  blacklist: string[];
}

export interface GenerateQuestionRequest {
  session_id: string;
}

export interface GenerateQuestionResponse {
  question_id: string;
  question_text: string;
  question_type: string;
  category: string;
  difficulty: string;
  source_citation: string;
}

export interface EvaluateRequest {
  question_id: string;
  user_answer: string | null;
  elapsed_seconds: number;
}

export interface EvaluateResponse {
  score: "correct" | "partial" | "incorrect" | null;
  correct_elements: string[];
  missing_or_wrong: string[];
  source_quote: string;
  source_citation: string;
  feedback_summary: string | null;
  model_id: string;
}

export interface CorrectScoreRequest {
  question_id: string;
  corrected_score: "correct" | "partial" | "incorrect";
}

export interface StreakResponse {
  streak: number;
  accuracy: number;
}

export interface BlacklistRequest {
  category_name: string;
}

export interface FeedbackNavigationState {
  questionText: string;
  userAnswer: string;
  evaluation: EvaluateResponse;
  elapsedSeconds: number;
  category: string;
  questionType: string;
  sessionId: string | null;
  questionCount: number;
  questionId: string;
}

export interface SettingsConfig {
  providers: {
    anthropic: { api_key: string; default_model: string };
    google: { api_key: string; default_model: string };
    zai: { api_key: string; default_model: string };
    openai: { api_key: string; default_model: string };
  };
  active_provider: string;
  quiz_model: string;
  clean_model: string;
  vision_model: string;
  skill_level: string;
}

export type ProviderKey = "anthropic" | "google" | "zai" | "openai";

export interface ModelTier {
  low: string;
  medium: string;
  high: string;
}

export interface ModelRegistry {
  anthropic: ModelTier;
  google: ModelTier;
  zai: ModelTier;
  openai: ModelTier;
}

export interface MedicationDose {
  name: string;
  indication: string;
  contraindications: string;
  adverse_effects: string;
  precautions: string;
  dose: string;
  cmg_reference: string;
  is_icp_only: boolean;
}

export interface SearchResult {
  content: string;
  source_type: string;
  source_file: string;
  category: string | null;
  cmg_number: string | null;
  chunk_type: string | null;
  relevance_score: number;
}

export interface GuidelineSummary {
  id: string;
  cmg_number: string;
  title: string;
  section: string;
  source_type: "cmg" | "med" | "csm";
  is_icp_only: boolean;
}

export interface GuidelineDetail {
  id: string;
  cmg_number: string;
  title: string;
  section: string;
  source_type: "cmg" | "med" | "csm";
  content_markdown: string;
  is_icp_only: boolean;
  dose_lookup: Record<string, unknown> | null;
  flowchart: Record<string, unknown> | null;
}

export interface LibrarySource {
  id: string;
  name: string;
  type: string;
  filter_type: string;
  progress: number;
  status_text: string;
  detail: string;
}

export interface CleaningFeedItem {
  status: "active" | "complete" | "waiting";
  label: string;
  preview: string;
  detail?: string | null;
}

export interface LibraryStatusResponse {
  sources: LibrarySource[];
  cleaning_feed: CleaningFeedItem[];
}

export interface CmgRefreshStatus {
  status: "idle" | "running" | "succeeded" | "failed";
  is_running: boolean;
  last_started_at: string | null;
  last_completed_at: string | null;
  last_successful_at: string | null;
  trigger: string | null;
  recommended_cadence: string;
  summary: {
    checked_item_count: number;
    new_count: number;
    updated_count: number;
    unchanged_count: number;
    error_count: number;
  } | null;
  last_error: string | null;
}

export interface CmgManifest {
  captured_at: string;
  source: string;
  pipeline_version: string;
  guideline_count: number;
  medication_count: number;
  clinical_skill_count: number;
}

export interface VectorStoreStatus {
  cmg: number;
  ref_doc: number;
  cpd_doc: number;
  notability_note: number;
}

export interface UploadResponse {
  filename: string;
  status: "processed" | "failed";
  chunks: number;
  categories: string[];
  source_type: string;
  error?: string | null;
}

export interface AcceptedFormatsResponse {
  extensions: string[];
  max_size_mb: number;
}

export interface Service {
  id: string;
  display_name: string;
  region: string;
  accent_colour: string;
  source_url: string;
  qualifications: {
    bases: { id: string; display: string; implies: string[] }[];
    endorsements: { id: string; display: string; requires_base: string[] }[];
  };
}
