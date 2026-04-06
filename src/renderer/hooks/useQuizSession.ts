import { useState, useCallback, useRef } from "react";
import type {
  StartSessionRequest,
  StartSessionResponse,
  GenerateQuestionResponse,
  EvaluateResponse,
} from "../types/api";
import { apiPost, getApiErrorMessage, LLM_REQUEST_TIMEOUT_MS } from "../lib/apiClient";
import { useBackendStatus } from "./useBackendStatus";

export type QuizPhase = "idle" | "loading" | "question" | "submitting" | "feedback" | "error";

interface UseQuizSessionResult {
  phase: QuizPhase;
  sessionId: string | null;
  question: GenerateQuestionResponse | null;
  evaluation: EvaluateResponse | null;
  elapsedSeconds: number;
  questionCount: number;
  error: string | null;
  loadingLabel: string | null;
  backendReady: boolean;
  startSession: (req: StartSessionRequest) => Promise<void>;
  submitAnswer: (answer: string | null) => Promise<void>;
  nextQuestion: () => Promise<void>;
  resumeSession: (sessionId: string, questionCount: number) => Promise<void>;
  endSession: () => void;
  setElapsedSeconds: (s: number) => void;
}

export function useQuizSession(): UseQuizSessionResult {
  const backendStatus = useBackendStatus();
  const [phase, setPhase] = useState<QuizPhase>("idle");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [question, setQuestion] = useState<GenerateQuestionResponse | null>(null);
  const [evaluation, setEvaluation] = useState<EvaluateResponse | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [questionCount, setQuestionCount] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [loadingLabel, setLoadingLabel] = useState<string | null>(null);
  const startTimeRef = useRef<number>(0);

  const [preloadedQuestion, setPreloadedQuestion] = useState<GenerateQuestionResponse | null>(null);
  const [isPreloading, setIsPreloading] = useState(false);
  const prefetchPromiseRef = useRef<Promise<GenerateQuestionResponse | null> | null>(null);

  const requireBackend = useCallback(() => {
    if (backendStatus.state === "ready") {
      return true;
    }
    setError(backendStatus.message ?? "Backend unavailable");
    setLoadingLabel(null);
    setPhase("error");
    return false;
  }, [backendStatus.message, backendStatus.state]);

  const prefetchNextQuestion = useCallback(
    (sid: string) => {
      if (backendStatus.state !== "ready") {
        return Promise.resolve<GenerateQuestionResponse | null>(null);
      }
      if (isPreloading) return Promise.resolve<GenerateQuestionResponse | null>(null);
      setIsPreloading(true);
      const promise = apiPost<GenerateQuestionResponse>(
        "/quiz/question/generate",
        { session_id: sid },
        { timeoutMs: LLM_REQUEST_TIMEOUT_MS }
      )
        .then((data) => {
          setPreloadedQuestion(data);
          return data;
        })
        .catch((err) => {
          setPreloadedQuestion(null);
          setError(getApiErrorMessage(err));
          return null;
        })
        .finally(() => {
          setIsPreloading(false);
        });
      prefetchPromiseRef.current = promise;
      return promise;
    },
    [backendStatus.state, isPreloading]
  );

  const startSession = useCallback(
    async (req: StartSessionRequest) => {
      if (!requireBackend()) return;
      setPhase("loading");
      setLoadingLabel("Generating question...");
      setError(null);
      setQuestionCount(0);
      try {
        const data = await apiPost<StartSessionResponse>("/quiz/session/start", req);
        setSessionId(data.session_id);

        const qData = await apiPost<GenerateQuestionResponse>(
          "/quiz/question/generate",
          { session_id: data.session_id },
          { timeoutMs: LLM_REQUEST_TIMEOUT_MS }
        );
        setQuestion(qData);
        setQuestionCount(1);
        setEvaluation(null);
        setElapsedSeconds(0);
        setLoadingLabel(null);
        startTimeRef.current = Date.now();
        setPhase("question");

        prefetchNextQuestion(data.session_id);
      } catch (err) {
        setError(getApiErrorMessage(err));
        setLoadingLabel(null);
        setPhase("error");
      }
    },
    [prefetchNextQuestion, requireBackend]
  );

  const submitAnswer = useCallback(
    async (answer: string | null) => {
      if (!question) return;
      if (!requireBackend()) return;
      setPhase("submitting");
      setLoadingLabel("Evaluating answer...");
      try {
        const elapsed = (Date.now() - startTimeRef.current) / 1000;
        setElapsedSeconds(elapsed);
        const data = await apiPost<EvaluateResponse>(
          "/quiz/question/evaluate",
          {
            question_id: question.question_id,
            user_answer: answer,
            elapsed_seconds: elapsed,
          },
          { timeoutMs: LLM_REQUEST_TIMEOUT_MS }
        );
        setEvaluation(data);
        setLoadingLabel(null);
        setPhase("feedback");
      } catch (err) {
        setError(getApiErrorMessage(err));
        setLoadingLabel(null);
        setPhase("error");
      }
    },
    [question, requireBackend]
  );

  const nextQuestion = useCallback(async () => {
    if (!sessionId) return;
    if (!requireBackend()) return;

    if (preloadedQuestion) {
      setQuestion(preloadedQuestion);
      setPreloadedQuestion(null);
      setQuestionCount((n) => n + 1);
      setEvaluation(null);
      setElapsedSeconds(0);
      startTimeRef.current = Date.now();
      setPhase("question");

      // Start pre-loading the next one
      prefetchNextQuestion(sessionId);
      return;
    }

    if (isPreloading && prefetchPromiseRef.current) {
      setPhase("loading");
      setLoadingLabel("Generating question...");
      const pData = await prefetchPromiseRef.current;
      if (pData) {
        setQuestion(pData);
        setPreloadedQuestion(null);
        setQuestionCount((n) => n + 1);
        setEvaluation(null);
        setElapsedSeconds(0);
        setLoadingLabel(null);
        startTimeRef.current = Date.now();
        setPhase("question");
        prefetchNextQuestion(sessionId);
        return;
      }
    }

    setPhase("loading");
    setLoadingLabel("Generating question...");
    setError(null);
    try {
      const data = await apiPost<GenerateQuestionResponse>(
        "/quiz/question/generate",
        { session_id: sessionId },
        { timeoutMs: LLM_REQUEST_TIMEOUT_MS }
      );
      setQuestion(data);
      setQuestionCount((n) => n + 1);
      setEvaluation(null);
      setElapsedSeconds(0);
      setLoadingLabel(null);
      startTimeRef.current = Date.now();
      setPhase("question");

      prefetchNextQuestion(sessionId);
    } catch (err) {
      setError(getApiErrorMessage(err));
      setLoadingLabel(null);
      setPhase("error");
    }
  }, [sessionId, preloadedQuestion, isPreloading, prefetchNextQuestion, requireBackend]);

  const resumeSession = useCallback(
    async (existingSessionId: string, existingQuestionCount: number) => {
      if (!requireBackend()) return;
      setPhase("loading");
      setLoadingLabel("Generating question...");
      setError(null);
      setSessionId(existingSessionId);
      setQuestionCount(existingQuestionCount);
      try {
        const data = await apiPost<GenerateQuestionResponse>(
          "/quiz/question/generate",
          { session_id: existingSessionId },
          { timeoutMs: LLM_REQUEST_TIMEOUT_MS }
        );
        setQuestion(data);
        setQuestionCount((n) => n + 1);
        setEvaluation(null);
        setElapsedSeconds(0);
        setLoadingLabel(null);
        startTimeRef.current = Date.now();
        setPhase("question");

        prefetchNextQuestion(existingSessionId);
      } catch (err) {
        setError(getApiErrorMessage(err));
        setLoadingLabel(null);
        setPhase("error");
      }
    },
    [prefetchNextQuestion, requireBackend]
  );

  const endSession = useCallback(() => {
    setPhase("idle");
    setSessionId(null);
    setQuestion(null);
    setEvaluation(null);
    setQuestionCount(0);
    setElapsedSeconds(0);
    setError(null);
    setLoadingLabel(null);
    setPreloadedQuestion(null);
    prefetchPromiseRef.current = null;
  }, []);

  return {
    phase,
    sessionId,
    question,
    evaluation,
    elapsedSeconds,
    questionCount,
    error,
    loadingLabel,
    backendReady: backendStatus.state === "ready",
    startSession,
    submitAnswer,
    nextQuestion,
    resumeSession,
    endSession,
    setElapsedSeconds,
  };
}
