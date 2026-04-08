import { useNavigate } from "react-router-dom";
import { useMastery } from "../hooks/useMastery";
import { useHistory } from "../hooks/useHistory";
import KnowledgeHeatmap from "../components/KnowledgeHeatmap";
import MetricCard from "../components/MetricCard";
import RecentEntries from "../components/RecentEntries";
import Button from "../components/Button";
import { useBackendStatus } from "../hooks/useBackendStatus";
import { useBackendStatusActions } from "../hooks/useBackendStatus";
import PageStateNotice from "../components/PageStateNotice";
import { getErrorStateCopy } from "../lib/loadingState";
import { resolveTopic } from "../utils/resolveTopic";

export default function Dashboard() {
  const navigate = useNavigate();
  const { categories, streak, accuracy, loading, error, refetch } = useMastery();
  const {
    entries,
    loading: historyLoading,
    error: historyError,
    refetch: refetchHistory,
  } = useHistory(3);
  const backendStatus = useBackendStatus();
  const { restart } = useBackendStatusActions();
  const hasDashboardData = categories.length > 0 || Boolean(entries?.length);
  const dashboardError = error ?? historyError;
  const errorCopy = getErrorStateCopy(dashboardError, backendStatus, "dashboard data");
  const retryLabel =
    backendStatus.state === "error" || backendStatus.state === "stopped"
      ? "Restart Backend"
      : "Retry";
  const retryAction =
    backendStatus.state === "error" || backendStatus.state === "stopped"
      ? () => {
          void restart();
        }
      : () => {
          void refetch();
          void refetchHistory();
        };

  if (loading && !hasDashboardData) {
    return <PageStateNotice loading title="Loading dashboard" message="Preparing mastery, streak, and recent activity." />;
  }

  if (dashboardError && !hasDashboardData) {
    return (
      <PageStateNotice
        title={errorCopy.title}
        message={errorCopy.message}
        actionLabel={retryLabel}
        onAction={retryAction}
      />
    );
  }

  if (!loading && !dashboardError && !hasDashboardData) {
    return (
      <PageStateNotice
        title="No progress yet"
        message="Your dashboard will populate after you complete quiz sessions and record results."
        actionLabel="Start Session"
        onAction={() => navigate("/quiz")}
      />
    );
  }

  const suggestedCategory =
    categories.length > 0
      ? categories.reduce((weakest, c) =>
          c.mastery_percent < weakest.mastery_percent ? c : weakest
        ).category
      : null;

  const handleCategoryClick = (category: string) => {
    const section = resolveTopic(category);
    if (section) {
      navigate("/quiz", { state: { scope: "section" as const, guidelineId: null, section } });
    } else {
      navigate("/quiz");
    }
  };

  return (
    <div>
      <div className="flex items-end justify-between mb-12">
        <div>
           <h2 className="font-headline text-display-lg text-primary">
             Study Dashboard
          </h2>
          <p className="font-body text-body-md text-on-surface-variant mt-1">
            Review mastery across clinical domains and begin active recall.
          </p>
          {(loading || historyLoading) && hasDashboardData && (
            <p className="font-mono text-[10px] text-on-surface-variant mt-3">
               Refreshing data...
            </p>
          )}
          {dashboardError && hasDashboardData && (
            <p className="font-mono text-[10px] text-status-critical mt-3">
              {getErrorStateCopy(dashboardError, backendStatus, "dashboard data").message}
            </p>
          )}
        </div>
        <Button
          onClick={() => navigate("/quiz")}
          variant="primary"
          disabled={backendStatus.state !== "ready"}
        >
          Start Session
          <span className="material-symbols-outlined text-sm">arrow_forward</span>
        </Button>
      </div>

      <div className="grid grid-cols-12 gap-8">
        <div className="col-span-12 lg:col-span-8">
          <h3 className="font-label text-label-sm text-on-surface-variant mb-4">
            Knowledge Heatmap
          </h3>
          <KnowledgeHeatmap categories={categories} onCategoryClick={handleCategoryClick} />
        </div>

        <div className="col-span-12 lg:col-span-4 space-y-4">
          <h3 className="font-label text-label-sm text-on-surface-variant mb-4">
            Performance Metrics
          </h3>
          <div className="grid grid-cols-2 gap-4">
            <MetricCard value={`${streak} days`} label="Current Streak" />
            <MetricCard value={`${accuracy.toFixed(1)}%`} label="Accuracy" />
          </div>

          {suggestedCategory && (
            <div
              className="bg-tertiary-fixed p-6 shadow-ambient cursor-pointer hover:bg-tertiary-fixed/80 transition-colors"
              onClick={() => handleCategoryClick(suggestedCategory)}
              role="button"
              tabIndex={0}
            >
              <div className="flex items-start gap-3">
                <span className="material-symbols-outlined text-on-tertiary-fixed text-sm opacity-60">
                  push_pin
                </span>
                <div>
                  <p className="font-headline text-title-lg italic text-on-tertiary-fixed">
                    Review {suggestedCategory}
                  </p>
                  <p className="font-mono text-[10px] text-on-tertiary-fixed-variant mt-2">
                    Suggested reflection — lowest mastery domain
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="col-span-12">
          <h3 className="font-label text-label-sm text-on-surface-variant mb-4">
             Recent Quiz History
          </h3>
          <RecentEntries entries={entries ?? []} />
        </div>
      </div>
    </div>
  );
}
