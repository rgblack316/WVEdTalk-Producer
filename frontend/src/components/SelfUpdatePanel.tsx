import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  Loader2,
  ArrowUpCircle,
  RefreshCw,
  CheckCircle2,
  XCircle,
  CloudDownload,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { apiGet, apiPost, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/useAuth";
import type { VersionInfo, SelfUpdateStatus, SelfUpdateResult } from "@/lib/types";

const errText = (e: unknown) =>
  e instanceof ApiError ? String((e.body as { detail?: string })?.detail ?? e.message) : String(e);

// Admin-only "Software updates" panel. Shows current/latest version and a one-click
// "Download & apply update" button that queues the host watcher (see upgrade-watch.sh),
// then polls /self-update/status so the admin sees progress without SSH.
export default function SelfUpdatePanel() {
  const { isAdmin } = useAuth();
  const qc = useQueryClient();

  const { data: ver } = useQuery({
    queryKey: ["version"],
    queryFn: () => apiGet<VersionInfo>("/version"),
    enabled: isAdmin,
  });

  const { data: st } = useQuery({
    queryKey: ["self-update-status"],
    queryFn: () => apiGet<SelfUpdateStatus>("/self-update/status"),
    enabled: isAdmin,
    refetchInterval: (q) =>
      ["queued", "running"].includes(q.state.data?.state ?? "") ? 4000 : 20000,
  });

  const check = useMutation({
    mutationFn: () => apiPost<VersionInfo>("/version/check"),
    onSuccess: (d) => {
      qc.setQueryData(["version"], d);
      toast.success(d.update_available ? `Update available: ${d.latest}` : "You're on the latest version.");
    },
    onError: (e) => toast.error(errText(e)),
  });

  const apply = useMutation({
    mutationFn: () => apiPost<SelfUpdateResult>("/self-update"),
    onSuccess: (d) => {
      qc.invalidateQueries({ queryKey: ["self-update-status"] });
      toast.message(d.already ? "An update is already in progress." : "Update queued — this takes a few minutes.");
    },
    onError: (e) => toast.error(errText(e)),
  });

  if (!isAdmin) return null;

  const state = st?.state ?? "idle";
  const inFlight = state === "queued" || state === "running";
  const available = st?.available ?? false;
  const watcher = st?.watcher_alive ?? false;

  return (
    <section
      className="mt-8 rounded-md border border-border bg-card p-5"
      data-testid="self-update-panel"
    >
      <h3 className="flex items-center gap-2 font-heading text-lg font-bold">
        <CloudDownload className="size-4 text-primary" /> Software updates
      </h3>
      <p className="mt-1 text-xs text-muted-foreground">
        Current version{" "}
        <Badge variant="secondary" data-testid="self-update-current">
          {ver?.current ?? "…"}
        </Badge>
        {ver?.latest && ver.latest !== ver.current && (
          <>
            {" "}
            · latest{" "}
            <Badge data-testid="self-update-latest">{ver.latest}</Badge>
          </>
        )}
      </p>

      <div className="mt-3 flex items-center gap-2 text-sm" data-testid="self-update-state">
        {state === "running" && <Loader2 className="size-4 animate-spin text-accent-foreground" />}
        {state === "success" && <CheckCircle2 className="size-4 text-emerald-600" />}
        {state === "failed" && <XCircle className="size-4 text-destructive" />}
        <span className="text-muted-foreground">
          {st?.message ?? (ver?.update_available ? "An update is available." : "Up to date.")}
        </span>
      </div>
      {st?.revision_before && (
        <p className="mt-1 text-xs text-muted-foreground" data-testid="self-update-revisions">
          Revision {st.revision_before}
          {st.revision_after ? ` → ${st.revision_after}` : ""}
        </p>
      )}

      {!available && (
        <p
          className="mt-3 rounded-sm bg-secondary/60 px-3 py-2 text-xs text-muted-foreground"
          data-testid="self-update-unavailable"
        >
          One-click update isn't available on this deployment (the control volume isn't mounted).
          Run <code className="font-mono">./upgrade.sh</code> on the server instead.
        </p>
      )}
      {available && !watcher && (
        <p
          className="mt-3 rounded-sm bg-amber-500/10 px-3 py-2 text-xs text-amber-700 dark:text-amber-400"
          data-testid="self-update-no-watcher"
        >
          Updater service not detected. Start it on the server
          (<code className="font-mono">sudo systemctl enable --now wvedtalk-updater</code> or{" "}
          <code className="font-mono">./upgrade-watch.sh</code>) — see the README.
        </p>
      )}

      <div className="mt-4 flex flex-wrap gap-2">
        <Button
          size="sm"
          variant="outline"
          disabled={check.isPending}
          onClick={() => check.mutate()}
          data-testid="self-update-check-button"
        >
          {check.isPending ? <Loader2 className="size-4 animate-spin" /> : <RefreshCw className="size-4" />}
          Check for updates
        </Button>
        <Button
          size="sm"
          disabled={!available || inFlight || apply.isPending}
          onClick={() => apply.mutate()}
          data-testid="self-update-apply-button"
        >
          {inFlight || apply.isPending ? (
            <Loader2 className="size-4 animate-spin" />
          ) : (
            <ArrowUpCircle className="size-4" />
          )}
          {state === "running" ? "Updating…" : state === "queued" ? "Queued…" : "Download & apply update"}
        </Button>
      </div>
    </section>
  );
}
