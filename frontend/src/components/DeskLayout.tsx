import { Link, useLocation } from "react-router-dom";
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Loader2, RefreshCw, LogOut, Clock, ArrowUpCircle, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { apiGet, apiPost, ApiError } from "@/lib/api";
import { endSession } from "@/lib/session";
import type { AuthState, CandidateStory, DeskConfig, NextRuns, RunStatus, VersionInfo } from "@/lib/types";

const BASE_NAV = [
  { to: "/", label: "Today's Briefing" },
  { to: "/archive", label: "Archive" },
  { to: "/episodes", label: "Weekly Script" },
  { to: "/candidates", label: "Podcast Prep" },
  { to: "/submissions", label: "Submissions" },
  { to: "/excluded", label: "Excluded" },
  { to: "/settings", label: "Settings" },
];

export default function DeskLayout({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  const qc = useQueryClient();

  const { data: auth } = useQuery({
    queryKey: ["auth", "me"],
    queryFn: () => apiGet<AuthState>("/auth/me"),
    staleTime: 5 * 60 * 1000,
  });

  const { data: status } = useQuery({
    queryKey: ["run-status"],
    queryFn: () => apiGet<RunStatus>("/run-status"),
    refetchInterval: (q) => (q.state.data?.running ? 5000 : 30000),
  });

  const { data: config } = useQuery({
    queryKey: ["config"],
    queryFn: () => apiGet<DeskConfig>("/settings"),
    staleTime: 60000,
  });

  const { data: nextRuns } = useQuery({
    queryKey: ["schedule-next"],
    queryFn: () => apiGet<NextRuns>("/schedule/next"),
    refetchInterval: 60000,
  });

  // Shared cache with the Podcast Prep page (queryKey ["candidates"]) so the nav badge and the
  // board stay in sync — clearing candidates invalidates this key and both update together.
  const { data: candidates } = useQuery({
    queryKey: ["candidates"],
    queryFn: () => apiGet<CandidateStory[]>("/candidates"),
    staleTime: 30000,
  });
  const candidateCount = candidates?.length ?? 0;

  // Shares the ["positive-stories"] cache with the Podcast Prep "Positive" filter so the nav badge
  // and the board stay in sync — flagging a story positive invalidates this key.
  const { data: positiveStories } = useQuery({
    queryKey: ["positive-stories"],
    queryFn: () => apiGet<CandidateStory[]>("/positive-stories"),
    staleTime: 30000,
  });
  const positiveCount = positiveStories?.length ?? 0;

  const { data: unverified } = useQuery({
    queryKey: ["unverified-count"],
    queryFn: () => apiGet<{ count: number }>("/unverified-count"),
    staleTime: 30000,
  });
  const unverifiedCount = unverified?.count ?? 0;

  const isAdmin = auth?.user?.role === "admin";
  const isViewer = auth?.user?.role === "viewer";
  const canEdit = auth?.user?.role === "admin" || auth?.user?.role === "editor";
  const nav = isAdmin ? [...BASE_NAV, { to: "/users", label: "Users" }] : BASE_NAV;

  // Self-hosted "update available" indicator — admin-only, cached server-side (1h TTL).
  const { data: versionInfo } = useQuery({
    queryKey: ["version"],
    queryFn: () => apiGet<VersionInfo>("/version"),
    enabled: isAdmin,
    staleTime: 30 * 60 * 1000,
    refetchInterval: 60 * 60 * 1000,
  });
  const [updateDismissed, setUpdateDismissed] = useState(false);
  const showUpdateBanner = isAdmin && !!versionInfo?.update_available && !updateDismissed;

  // Auto-lock after a period of inactivity (0 = off). Any interaction resets the timer.
  const lockMinutes = config?.auto_lock_minutes ?? 0;
  useEffect(() => {
    if (!lockMinutes) return;
    let timer: ReturnType<typeof setTimeout>;
    const reset = () => {
      clearTimeout(timer);
      timer = setTimeout(() => {
        toast.message("Signed out due to inactivity");
        endSession();
      }, lockMinutes * 60 * 1000);
    };
    const events = ["mousemove", "mousedown", "keydown", "scroll", "touchstart"];
    events.forEach((e) => window.addEventListener(e, reset, { passive: true }));
    reset();
    return () => {
      clearTimeout(timer);
      events.forEach((e) => window.removeEventListener(e, reset));
    };
  }, [lockMinutes]);

  const run = useMutation({
    mutationFn: () => apiPost<RunStatus>("/run"),
    onSuccess: () => {
      toast.success("Research run started — this takes a few minutes.");
      qc.invalidateQueries({ queryKey: ["run-status"] });
    },
    onError: (e) => {
      const msg = e instanceof ApiError ? String((e.body as { detail?: string })?.detail ?? e.message) : String(e);
      toast.error(msg);
    },
  });

  const running = status?.running ?? false;

  return (
    <div className="min-h-screen bg-background" data-testid="desk-layout">
      <header className="border-b border-border bg-card/70 backdrop-blur">
        <div className="mx-auto flex max-w-6xl flex-col gap-3 px-5 py-4 md:flex-row md:items-end md:justify-between">
          <div>
            <Link to="/" className="block" data-testid="desk-masthead-link">
              <img
                src="/wvedtalk-logo.png"
                alt="WVEdTalk News Desk — The Weekly Drive Through West Virginia Education"
                className="h-14 w-auto md:h-16"
              />
            </Link>
          </div>
          <div className="flex items-center gap-3">
            <nav className="flex flex-wrap gap-1" data-testid="desk-nav">
              {nav.map((n) => {
                const active = location.pathname === n.to;
                return (
                  <Link
                    key={n.to}
                    to={n.to}
                    data-testid={`nav-${n.to === "/" ? "today" : n.to.slice(1)}`}
                    className={`rounded-sm px-3 py-1.5 text-sm transition-colors duration-150 ${
                      active
                        ? "bg-primary text-primary-foreground"
                        : "text-muted-foreground hover:bg-secondary hover:text-foreground"
                    }`}
                  >
                    {n.label}
                    {n.to === "/candidates" && candidateCount > 0 && (
                      <span
                        className={`ml-1.5 inline-flex min-w-[1.125rem] items-center justify-center rounded-full px-1.5 py-0.5 text-[10px] font-semibold leading-none ${
                          active ? "bg-primary-foreground text-primary" : "bg-accent text-accent-foreground"
                        }`}
                        data-testid="candidate-count-badge"
                      >
                        {candidateCount}
                      </span>
                    )}
                    {n.to === "/candidates" && positiveCount > 0 && (
                      <span
                        className="ml-1 inline-flex min-w-[1.125rem] items-center justify-center rounded-full bg-emerald-600 px-1.5 py-0.5 text-[10px] font-semibold leading-none text-white"
                        data-testid="positive-count-badge"
                        title={`${positiveCount} positive-note ${positiveCount === 1 ? "story" : "stories"} flagged`}
                      >
                        {positiveCount}
                      </span>
                    )}
                    {n.to === "/archive" && unverifiedCount > 0 && (
                      <span
                        className="ml-1.5 inline-flex min-w-[1.125rem] items-center justify-center rounded-full bg-amber-500 px-1.5 py-0.5 text-[10px] font-semibold leading-none text-white"
                        data-testid="unverified-count-badge"
                        title={`${unverifiedCount} source link${unverifiedCount === 1 ? "" : "s"} flagged unverified`}
                      >
                        {unverifiedCount}
                      </span>
                    )}
                  </Link>
                );
              })}
            </nav>
            {canEdit && (
            <Button
              size="sm"
              variant="outline"
              disabled={running || run.isPending}
              onClick={() => run.mutate()}
              data-testid="run-now-button"
            >
              {running ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <RefreshCw className="size-4" />
              )}
              {running ? "Researching…" : "Run now"}
            </Button>
            )}
            {nextRuns && (
              <span
                className="hidden items-center gap-1 text-xs text-muted-foreground xl:inline-flex"
                data-testid="next-run-indicator"
                title={`Your timezone: ${Intl.DateTimeFormat().resolvedOptions().timeZone}\nNext weekly script: ${new Date(
                  nextRuns.weekly_next,
                ).toLocaleString(undefined, { timeZoneName: "short" })}`}
              >
                <Clock className="size-3.5" />
                Next briefing{" "}
                {new Date(nextRuns.daily_next).toLocaleString(undefined, {
                  weekday: "short",
                  hour: "numeric",
                  minute: "2-digit",
                  timeZoneName: "short",
                })}
              </span>
            )}
            {auth?.user && (
              <span
                className="hidden text-xs text-muted-foreground lg:inline"
                data-testid="current-user-email"
              >
                {auth.user.email}
              </span>
            )}
            <Button
              size="icon-sm"
              variant="ghost"
              onClick={() => endSession()}
              aria-label="Sign out"
              title="Sign out"
              data-testid="logout-button"
            >
              <LogOut className="size-4" />
            </Button>
          </div>
        </div>
        {running && (
          <div
            className="border-t border-border bg-accent/10 px-5 py-2 text-center text-xs text-accent-foreground"
            data-testid="run-status-banner"
          >
            <span className="desk-pulse font-medium text-foreground">
              {status?.message || "Research run in progress…"}
            </span>
          </div>
        )}
      </header>
      {showUpdateBanner && (
        <div
          className="flex items-center justify-center gap-2 border-b border-accent/40 bg-accent/15 px-5 py-2 text-center text-xs text-foreground"
          data-testid="update-available-banner"
        >
          <ArrowUpCircle className="size-3.5 text-accent-foreground" />
          <span>
            Update available — version{" "}
            <span className="font-semibold" data-testid="update-latest-version">
              {versionInfo?.latest}
            </span>{" "}
            is out (you're on {versionInfo?.current}). Run{" "}
            <code className="rounded bg-background/70 px-1 py-0.5 font-mono">./upgrade.sh</code> on
            your server to update.
          </span>
          <button
            type="button"
            onClick={() => setUpdateDismissed(true)}
            aria-label="Dismiss update notice"
            className="ml-1 rounded-sm p-0.5 text-muted-foreground transition-colors hover:text-foreground"
            data-testid="update-dismiss-button"
          >
            <X className="size-3.5" />
          </button>
        </div>
      )}
      {isViewer && (
        <div
          className="border-b border-border bg-secondary/60 px-5 py-1.5 text-center text-xs text-muted-foreground"
          data-testid="view-only-banner"
        >
          View-only access — you can read everything the desk has produced, but editing, tagging and
          running research are turned off for your account.
        </div>
      )}
      <main className="mx-auto max-w-6xl px-5 py-8">{children}</main>
      <footer className="border-t border-border px-5 py-6 text-center text-xs text-muted-foreground">
        Runs on the schedule set in Settings · Editorial judgment, scores and rankings are produced by
        the research model and presented unaltered.
      </footer>
    </div>
  );
}
