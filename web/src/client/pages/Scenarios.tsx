import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router";
import { documentPath, SCORE_CLASS, SCORE_LABEL } from "../components/Feedback";
import { REASONS } from "../components/QuizParts";
import { ScopePicker } from "../components/ScopePicker";
import { api, ApiError, type ReportReason, type ScenarioOption, type ScenarioStage, type ScenarioSummary, type StageReveal } from "../lib/api";
import { QUIZ_SCOPE_OPTIONS, useQuizScope, viewFor } from "../lib/scopeView";
import { useSession } from "../lib/session";
import { PATIENT_GROUP_LABELS, PATIENT_GROUPS, scenarioScore, stageScore, type PatientGroup, type Score } from "../../shared/scenarios";

type Difficulty = "easy" | "medium" | "hard";
const DIFFICULTIES: { value: Difficulty | null; label: string }[] = [
  { value: null, label: "Any" },
  { value: "easy", label: "Easy" },
  { value: "medium", label: "Medium" },
  { value: "hard", label: "Hard" },
];
const SEEN_KEY = "scenario-seen";
const MAX_SEEN = 400;

interface StageState {
  stage: ScenarioStage;
  answer: string;
  reveal: StageReveal | null;
  ticked: number[];
}

function loadSeen(): string[] {
  try {
    const value = JSON.parse(localStorage.getItem(SEEN_KEY) ?? "[]") as unknown;
    return Array.isArray(value) ? value.filter((x): x is string => typeof x === "string") : [];
  } catch {
    return [];
  }
}

function saveSeen(ids: string[]) {
  try {
    localStorage.setItem(SEEN_KEY, JSON.stringify(ids.slice(-MAX_SEEN)));
  } catch {
    return;
  }
}

function Choice<T extends string | null>({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: T;
  options: { value: T; label: string; disabled?: boolean }[];
  onChange: (value: T) => void;
}) {
  return (
    <div className="space-y-2">
      <p className="text-xs font-medium uppercase tracking-widest text-on-surface-variant" id={`choice-${label}`}>
        {label}
      </p>
      <div className="flex flex-wrap gap-1" role="radiogroup" aria-labelledby={`choice-${label}`}>
        {options.map((o) => (
          <button
            key={o.label}
            type="button"
            role="radio"
            aria-checked={value === o.value}
            disabled={o.disabled}
            onClick={() => onChange(o.value)}
            className={`min-h-10 rounded-sm px-3 py-2 text-sm font-medium disabled:opacity-40 ${
              value === o.value ? "bg-primary text-on-primary" : "bg-surface-container-low hover:bg-surface-container"
            }`}
          >
            {o.label}
          </button>
        ))}
      </div>
    </div>
  );
}

function ScoreChip({ score }: { score: Score }) {
  return <span className={`inline-block rounded-sm px-2 py-1 text-sm font-semibold ${SCORE_CLASS[score]}`}>{SCORE_LABEL[score]}</span>;
}

function Rubric({ reveal, ticked, onToggle, locked }: { reveal: StageReveal; ticked: number[]; onToggle: (i: number) => void; locked: boolean }) {
  return (
    <fieldset className="space-y-3">
      <legend className="text-sm font-semibold">Tick what your answer covered</legend>
      {reveal.rubric.map((p, i) => (
        <div key={i} className="rounded-sm bg-surface-container-low p-3">
          <label className="flex items-start gap-3">
            <input type="checkbox" className="mt-1" checked={ticked.includes(i)} disabled={locked} onChange={() => onToggle(i)} />
            <span>
              {p.critical && <span className="mr-2 rounded-sm bg-error px-1.5 py-0.5 text-xs font-semibold text-white">Critical</span>}
              {p.point}
            </span>
          </label>
          <details className="mt-2 pl-7 text-sm">
            <summary className="cursor-pointer text-on-surface-variant">From the guideline</summary>
            {p.cites.map((c, j) => (
              <blockquote key={j} className="mt-1 bg-highlight/30 px-2 py-1 font-body">
                {c.quote}
              </blockquote>
            ))}
          </details>
        </div>
      ))}
    </fieldset>
  );
}

function ReportForm({ scenarioId, stage, onDone }: { scenarioId: string; stage: number | null; onDone: () => void }) {
  const [reason, setReason] = useState<ReportReason>("incorrect");
  const [detail, setDetail] = useState("");
  const [state, setState] = useState<"idle" | "sending" | "sent" | "error">("idle");
  if (state === "sent") return <p role="status" className="text-sm">Thanks. The report has been sent.</p>;
  return (
    <form
      className="space-y-2 rounded-sm bg-surface-container-low p-3"
      onSubmit={(e) => {
        e.preventDefault();
        setState("sending");
        api
          .reportScenario(scenarioId, reason, detail, stage)
          .then(() => setState("sent"))
          .catch(() => setState("error"));
      }}
    >
      <label className="block text-sm">
        What's wrong?
        <select className="mt-1 block w-full bg-surface p-2" value={reason} onChange={(e) => setReason(e.target.value as ReportReason)}>
          {REASONS.map((r) => (
            <option key={r.value} value={r.value}>
              {r.label}
            </option>
          ))}
        </select>
      </label>
      <label className="block text-sm">
        Details (optional)
        <textarea className="mt-1 block w-full bg-surface p-2 text-base sm:text-sm" maxLength={1000} value={detail} onChange={(e) => setDetail(e.target.value)} />
      </label>
      {state === "error" && <p role="alert" className="text-sm text-error">Couldn't send the report. Try again.</p>}
      <div className="flex gap-2">
        <button type="submit" disabled={state === "sending"} className="rounded-sm bg-primary px-3 py-2 text-sm font-semibold text-on-primary">
          Send report
        </button>
        <button type="button" onClick={onDone} className="rounded-sm px-3 py-2 text-sm">
          Cancel
        </button>
      </div>
    </form>
  );
}

export function Scenarios() {
  const { me } = useSession();
  const [choice, setChoice] = useQuizScope();
  const icpOnly = choice.level === "icp_only";
  const view = viewFor(choice);
  const [options, setOptions] = useState<ScenarioOption[] | null>(null);
  const [category, setCategory] = useState<string | null>(null);
  const [difficulty, setDifficulty] = useState<Difficulty | null>(null);
  const [group, setGroup] = useState<PatientGroup | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [scenario, setScenario] = useState<ScenarioSummary | null>(null);
  const [stages, setStages] = useState<StageState[]>([]);
  const [busy, setBusy] = useState(false);
  const [exhausted, setExhausted] = useState<{ canRepeat: boolean } | null>(null);
  const [finished, setFinished] = useState(false);
  const [reporting, setReporting] = useState(false);

  useEffect(() => {
    let live = true;
    setOptions(null);
    api
      .scenarioOptions(view, icpOnly)
      .then((r) => live && setOptions(r.options))
      .catch((err: unknown) => live && setError(err instanceof ApiError && err.status === 404 ? "Scenarios aren't available yet." : "Couldn't load scenarios."));
    return () => {
      live = false;
    };
  }, [view, icpOnly]);

  const counts = useMemo(() => {
    const match = (o: ScenarioOption, skip: "category" | "difficulty" | "group") =>
      (skip === "category" || category === null || o.category === category) &&
      (skip === "difficulty" || difficulty === null || o.difficulty === difficulty) &&
      (skip === "group" || group === null || o.patientGroup === group);
    const sum = (skip: "category" | "difficulty" | "group", key: (o: ScenarioOption) => string) => {
      const out = new Map<string, number>();
      for (const o of options ?? []) if (match(o, skip)) out.set(key(o), (out.get(key(o)) ?? 0) + o.count);
      return out;
    };
    return {
      category: sum("category", (o) => o.category),
      difficulty: sum("difficulty", (o) => o.difficulty),
      group: sum("group", (o) => o.patientGroup),
    };
  }, [options, category, difficulty, group]);

  const start = async (repeat = false) => {
    setBusy(true);
    setError(null);
    setExhausted(null);
    try {
      const seen = me?.signedIn ? [] : loadSeen();
      const res = await api.nextScenario({ view, icpOnly, category, difficulty, patientGroup: group }, seen, repeat);
      if (!res.scenario) {
        setExhausted({ canRepeat: Boolean(res.canRepeat) || (!me?.signedIn && seen.length > 0) });
        if (repeat && !me?.signedIn) saveSeen([]);
        return;
      }
      if (!me?.signedIn) saveSeen([...seen.filter((id) => id !== res.scenario!.id), res.scenario.id]);
      setScenario(res.scenario);
      setStages(res.scenario.stage ? [{ stage: res.scenario.stage, answer: "", reveal: null, ticked: [] }] : []);
      setFinished(false);
      setReporting(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't load a scenario.");
    } finally {
      setBusy(false);
    }
  };

  const update = (i: number, patch: Partial<StageState>) => setStages((all) => all.map((s, j) => (j === i ? { ...s, ...patch } : s)));

  const reveal = async (i: number) => {
    if (!scenario) return;
    setBusy(true);
    try {
      update(i, { reveal: await api.revealStage(scenario.id, stages[i]!.stage.ordinal, view) });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't reveal the stage.");
    } finally {
      setBusy(false);
    }
  };

  const advance = (i: number) => {
    const next = stages[i]?.reveal?.next;
    if (next) setStages((all) => [...all, { stage: next, answer: "", reveal: null, ticked: [] }]);
  };

  const finish = async () => {
    setFinished(true);
    if (scenario && me?.signedIn) {
      await api
        .saveScenarioAttempt(scenario.id, view, stages.map((s) => ({ ordinal: s.stage.ordinal, ticked: s.ticked, answer: s.answer })))
        .catch(() => setError("Your result couldn't be saved, but the debrief below is still right."));
    }
  };

  const stageScores = stages.map((s) => (s.reveal ? stageScore(s.reveal.rubric, s.ticked) : null));
  const overall = finished ? scenarioScore(stageScores.filter((s): s is Score => s !== null)) : null;

  if (scenario) {
    return (
      <div className="space-y-6">
        <header className="space-y-2">
          <p className="text-xs font-medium uppercase tracking-widest text-on-surface-variant">
            {scenario.category} · {scenario.difficulty} · {PATIENT_GROUP_LABELS[scenario.patientGroup]} · {scenario.stageCount} stages
          </p>
          <h1 className="font-headline text-3xl font-semibold">{scenario.title}</h1>
        </header>
        {error && (
          <p role="alert" className="rounded-sm bg-error-container p-3 text-sm text-error">
            {error}
          </p>
        )}
        <section aria-label="Dispatch" className="rounded-sm bg-surface-container-low p-4">
          <p className="text-xs font-medium uppercase tracking-widest text-on-surface-variant">Dispatch</p>
          <p className="mt-1 font-headline text-lg">{scenario.dispatch}</p>
        </section>
        {stages.map((s, i) => (
          <section key={s.stage.ordinal} aria-label={`Stage ${s.stage.ordinal}`} className="space-y-3">
            <h2 className="font-headline text-xl font-semibold">
              Stage {s.stage.ordinal} of {scenario.stageCount}
            </h2>
            <p className="font-mono text-sm leading-relaxed">{s.stage.reveal}</p>
            <p className="font-semibold">{s.stage.question}</p>
            <label className="block text-sm">
              <span className="sr-only">Your answer for stage {s.stage.ordinal}</span>
              <textarea
                className="block min-h-24 w-full rounded-sm bg-surface-container-lowest p-3 text-base sm:text-sm"
                placeholder="Type your answer, or think it through and reveal"
                value={s.answer}
                disabled={Boolean(s.reveal)}
                onChange={(e) => update(i, { answer: e.target.value })}
              />
            </label>
            {!s.reveal ? (
              <button type="button" disabled={busy} onClick={() => void reveal(i)} className="rounded-sm bg-primary px-4 py-2 font-semibold text-on-primary">
                Reveal
              </button>
            ) : (
              <>
                <Rubric
                  reveal={s.reveal}
                  ticked={s.ticked}
                  locked={finished}
                  onToggle={(p) => update(i, { ticked: s.ticked.includes(p) ? s.ticked.filter((x) => x !== p) : [...s.ticked, p] })}
                />
                {i === stages.length - 1 && !finished && (
                  <button
                    type="button"
                    onClick={() => (s.reveal?.next ? advance(i) : void finish())}
                    className="rounded-sm bg-primary px-4 py-2 font-semibold text-on-primary"
                  >
                    {s.reveal.next ? "Next stage" : "Finish"}
                  </button>
                )}
              </>
            )}
          </section>
        ))}
        {finished && overall && (
          <section aria-label="Debrief" className="space-y-3 rounded-sm bg-surface-container-low p-4">
            <h2 className="font-headline text-xl font-semibold">Debrief</h2>
            <p className="flex items-center gap-2">
              Overall: <ScoreChip score={overall} />
            </p>
            <ul className="space-y-1 text-sm">
              {stageScores.map((score, i) =>
                score ? (
                  <li key={i} className="flex items-center gap-2">
                    Stage {i + 1}: <ScoreChip score={score} />
                  </li>
                ) : null,
              )}
            </ul>
            <p className="text-sm">
              Read: <Link className="underline" to={documentPath(scenario.documentId)}>{scenario.documentTitle ?? "the guideline"}</Link>
            </p>
            <div className="flex flex-wrap gap-2">
              <button type="button" onClick={() => void start()} className="rounded-sm bg-primary px-4 py-2 font-semibold text-on-primary">
                Another like this
              </button>
              <button type="button" onClick={() => setScenario(null)} className="rounded-sm px-4 py-2">
                Change choices
              </button>
              {!reporting && (
                <button type="button" onClick={() => setReporting(true)} className="rounded-sm px-4 py-2">
                  Report a problem
                </button>
              )}
            </div>
            {reporting && <ReportForm scenarioId={scenario.id} stage={null} onDone={() => setReporting(false)} />}
          </section>
        )}
      </div>
    );
  }

  const categories = [...counts.category.keys()].sort();
  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <h1 className="font-headline text-3xl font-semibold">Scenarios</h1>
        <p className="text-on-surface-variant">
          Work through a patient case in stages. Answer each stage, then tick the points you covered against the ACTAS guidelines.
        </p>
      </header>
      {error && (
        <p role="alert" className="rounded-sm bg-error-container p-3 text-sm text-error">
          {error}
        </p>
      )}
      <ScopePicker level={choice.level} pacer={choice.pacer} options={QUIZ_SCOPE_OPTIONS} onChange={setChoice} legend="Scenarios for" label="Scope" />
      {options === null && !error && <p className="text-sm text-on-surface-variant">Loading…</p>}
      {options && options.length === 0 && <p>No scenarios in this scope yet.</p>}
      {options && options.length > 0 && (
        <div className="space-y-5">
          <Choice
            label="Category"
            value={category}
            onChange={setCategory}
            options={[{ value: null, label: "Any" }, ...categories.map((c) => ({ value: c as string | null, label: `${c} (${counts.category.get(c)})` }))]}
          />
          <Choice
            label="Difficulty"
            value={difficulty}
            onChange={setDifficulty}
            options={DIFFICULTIES.map((d) => ({ ...d, disabled: d.value !== null && !counts.difficulty.get(d.value) }))}
          />
          <Choice
            label="Patient"
            value={group}
            onChange={setGroup}
            options={[
              { value: null, label: "Any" },
              ...PATIENT_GROUPS.filter((g) => counts.group.get(g)).map((g) => ({ value: g as PatientGroup | null, label: PATIENT_GROUP_LABELS[g] })),
            ]}
          />
          <button type="button" disabled={busy} onClick={() => void start()} className="min-h-12 rounded-sm bg-primary px-5 py-3 font-semibold text-on-primary">
            Start scenario
          </button>
        </div>
      )}
      {exhausted && (
        <div role="status" className="space-y-2 rounded-sm bg-surface-container-low p-3 text-sm">
          <p>You've done every scenario that matches these choices.</p>
          {exhausted.canRepeat && (
            <button type="button" onClick={() => void start(true)} className="rounded-sm bg-primary px-3 py-2 font-semibold text-on-primary">
              Repeat one
            </button>
          )}
        </div>
      )}
    </div>
  );
}
