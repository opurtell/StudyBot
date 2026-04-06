import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import type { PropsWithChildren } from "react";
import { useQuizSession } from "../../src/renderer/hooks/useQuizSession";
import { BackendStatusProvider } from "../../src/renderer/hooks/useBackendStatus";
import { stubWindowBackendApi } from "./testUtils";

function jsonResponse(body: unknown, init?: { status?: number }) {
  const status = init?.status ?? 200;
  return {
    ok: status >= 200 && status < 300,
    status,
    text: () => Promise.resolve(body === undefined ? "" : JSON.stringify(body)),
    json: () => Promise.resolve(body),
  } as Response;
}

beforeEach(() => {
  global.fetch = vi.fn();
  stubWindowBackendApi();
});

function wrapper({ children }: PropsWithChildren) {
  return <BackendStatusProvider>{children}</BackendStatusProvider>;
}

describe("useQuizSession", () => {
  it("transitions through a full quiz session", async () => {
    const mockStart = { session_id: "s1", mode: "random", blacklist: [] };
    const mockQuestion = {
      question_id: "q1",
      question_text: "Define hypovolemic shock.",
      question_type: "recall",
      category: "Cardiac",
      difficulty: "medium",
      source_citation: "CMG 14.1",
    };
    const mockEvaluation = {
      score: "partial",
      correct_elements: ["hypotension"],
      missing_or_wrong: ["tachycardia"],
      source_quote: "Hypovolemic shock presents with...",
      source_citation: "CMG 14.1",
      feedback_summary: "Good start but missed key signs.",
    };

    (global.fetch as ReturnType<typeof vi.fn>).mockImplementation((url: string) => {
      if (url.includes("/session/start")) {
        return Promise.resolve(jsonResponse(mockStart));
      }
      if (url.includes("/question/generate")) {
        return Promise.resolve(jsonResponse(mockQuestion));
      }
      if (url.includes("/question/evaluate")) {
        return Promise.resolve(jsonResponse(mockEvaluation));
      }
      return Promise.resolve(jsonResponse({ detail: "not found" }, { status: 404 }));
    });

    const { result } = renderHook(() => useQuizSession(), { wrapper });
    await waitFor(() => expect(result.current.backendReady).toBe(true));

    expect(result.current.phase).toBe("idle");

    await act(() => result.current.startSession({ mode: "random" }));
    await waitFor(() => expect(result.current.phase).toBe("question"));
    expect(result.current.question?.question_text).toBe("Define hypovolemic shock.");

    await act(() => result.current.submitAnswer("Low blood pressure"));
    await waitFor(() => expect(result.current.phase).toBe("feedback"));
    expect(result.current.evaluation?.score).toBe("partial");

    await act(() => result.current.nextQuestion());
    await waitFor(() => expect(result.current.phase).toBe("question"));
  });

  it("resets to idle on endSession", async () => {
    const mockStart = { session_id: "s1", mode: "random", blacklist: [] };
    const mockQuestion = {
      question_id: "q1",
      question_text: "Test question",
      question_type: "recall",
      category: "Cardiac",
      difficulty: "medium",
      source_citation: "CMG 14.1",
    };

    (global.fetch as ReturnType<typeof vi.fn>).mockImplementation((url: string) => {
      if (url.includes("/session/start")) {
        return Promise.resolve(jsonResponse(mockStart));
      }
      if (url.includes("/question/generate")) {
        return Promise.resolve(jsonResponse(mockQuestion));
      }
      return Promise.resolve(jsonResponse({ detail: "not found" }, { status: 404 }));
    });

    const { result } = renderHook(() => useQuizSession(), { wrapper });
    await waitFor(() => expect(result.current.backendReady).toBe(true));

    await act(() => result.current.startSession({ mode: "random" }));
    await waitFor(() => expect(result.current.phase).toBe("question"));

    act(() => result.current.endSession());
    expect(result.current.phase).toBe("idle");
    expect(result.current.sessionId).toBeNull();
  });

  it("pre-loads the next question and uses it", async () => {
    const mockStart = { session_id: "s1", mode: "random", blacklist: [] };
    const mockQ1 = { question_id: "q1", question_text: "Q1", category: "C1" };
    const mockQ2 = { question_id: "q2", question_text: "Q2", category: "C2" };

    let callCount = 0;
    (global.fetch as ReturnType<typeof vi.fn>).mockImplementation((url: string) => {
      if (url.includes("/session/start")) {
        return Promise.resolve(jsonResponse(mockStart));
      }
      if (url.includes("/question/generate")) {
        callCount++;
        const data = callCount === 1 ? mockQ1 : mockQ2;
        return Promise.resolve(jsonResponse(data));
      }
      return Promise.resolve(jsonResponse({ detail: "not found" }, { status: 404 }));
    });

    const { result } = renderHook(() => useQuizSession(), { wrapper });
    await waitFor(() => expect(result.current.backendReady).toBe(true));

    // Start session -> loads Q1 -> triggers prefetch for Q2
    await act(() => result.current.startSession({ mode: "random" }));
    await waitFor(() => expect(result.current.question?.question_id).toBe("q1"));

    // Wait for prefetch for Q2 to be initiated and finished
    await waitFor(() => expect(callCount).toBe(2));

    // Now call nextQuestion -> should use already fetched Q2 immediately
    await act(() => result.current.nextQuestion());
    expect(result.current.question?.question_id).toBe("q2");

    await waitFor(() => expect(callCount).toBe(3));
  });

  it("surfaces shared-client error messages on session start failure", async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      jsonResponse({ detail: "Backend processing failed" }, { status: 500 })
    );

    const { result } = renderHook(() => useQuizSession(), { wrapper });
    await waitFor(() => expect(result.current.backendReady).toBe(true));

    await act(() => result.current.startSession({ mode: "random" }));

    await waitFor(() => expect(result.current.phase).toBe("error"));
    expect(result.current.error).toBe("Backend processing failed");
  });
});
