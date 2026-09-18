import { Link, useLocation } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Loader2, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { apiGet, apiPost, ApiError } from "@/lib/api";
import type { RunStatus } from "@/lib/types";

const NAV = [
  { to: "/", label: "Today's Briefing" },
  { to: "/archive", label: "Archive" },
  { to: "/candidates", label: "Podcast Prep" },
];

export default function DeskLayout({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  const qc = useQueryClient();

  const { data: status } = useQuery({
    queryKey: ["run-status"],
    queryFn: () => apiGet<RunStatus>("/run-status"),
    refetchInterval: (q) => (q.state.data?.running ? 5000 : 30000),
  });

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
              <h1 className="font-heading text-2xl leading-none font-bold tracking-tight md:text-3xl">
                WV Education News Desk
              </h1>
            </Link>
            <p className="mt-1 text-xs tracking-[0.18em] text-muted-foreground uppercase">
              Statewide research &amp; editorial briefing · West Virginia
            </p>
          </div>
          <div className="flex items-center gap-3">
            <nav className="flex gap-1" data-testid="desk-nav">
              {NAV.map((n) => {
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
                  </Link>
                );
              })}
            </nav>
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
      <main className="mx-auto max-w-6xl px-5 py-8">{children}</main>
      <footer className="border-t border-border px-5 py-6 text-center text-xs text-muted-foreground">
        Scheduled daily at 6:00 AM Eastern · Editorial judgment, scores and rankings are produced by
        the research model and presented unaltered.
      </footer>
    </div>
  );
}
