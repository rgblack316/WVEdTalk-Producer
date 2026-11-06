import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { AlertTriangle, CheckCircle2, History, Loader2, MessageSquareText, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { apiGet, apiPost, ApiError } from "@/lib/api";
import type { EpisodeRevision, WeeklyEpisode } from "@/lib/types";

const errMsg = (e: unknown) =>
  e instanceof ApiError ? String((e.body as { detail?: string })?.detail ?? e.message) : String(e);

// Lets the host steer an existing script with plain-language feedback instead of regenerating the
// whole episode. Shows what the last revision changed, the fact-check findings, and past versions.
export function ScriptFeedbackPanel({ episode, canEdit }: { episode: WeeklyEpisode; canEdit: boolean }) {
  const qc = useQueryClient();
  const week = episode.week_of;
  const [feedback, setFeedback] = useState("");
  const [research, setResearch] = useState(false);
  const [showHistory, setShowHistory] = useState(false);

  const { data: revisions } = useQuery({
    queryKey: ["episode-revisions", week, episode.revision_count],
    queryFn: () => apiGet<EpisodeRevision[]>(`/episodes/${week}/revisions`),
    enabled: showHistory,
  });

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["episode", week] });
    qc.invalidateQueries({ queryKey: ["episode-revisions", week] });
  };

  const revise = useMutation({
    mutationFn: () => apiPost<WeeklyEpisode>(`/episodes/${week}/revise`, { feedback, allow_research: research }),
    onSuccess: () => {
      refresh();
      setFeedback("");
      toast.success("Script revised — the previous version is in history");
    },
    onError: (e) => toast.error(errMsg(e)),
  });

  const restore = useMutation({
    mutationFn: (id: string) => apiPost<WeeklyEpisode>(`/episodes/${week}/revisions/${id}/restore`),
    onSuccess: () => {
      refresh();
      toast.success("Earlier version restored");
    },
    onError: (e) => toast.error(errMsg(e)),
  });

  const open = (episode.fact_check ?? []).filter((i) => !i.fixed);
  const fixed = (episode.fact_check ?? []).filter((i) => i.fixed);

  return (
    <div className="mb-4 rounded-md border border-border bg-card p-4" data-testid="script-feedback-panel">
      <h3 className="flex items-center gap-2 font-heading text-base font-bold">
        <MessageSquareText className="size-4 text-primary" /> Revise with feedback
      </h3>

      {open.length > 0 && (
        <div className="mt-3 rounded-sm border border-amber-500/50 bg-amber-500/5 p-3" data-testid="fact-check-open">
          <p className="flex items-center gap-1.5 text-sm font-semibold text-amber-700 dark:text-amber-400">
            <AlertTriangle className="size-4" /> Fact-check flagged {open.length} claim{open.length === 1 ? "" : "s"} to review
          </p>
          <ul className="mt-2 space-y-2 text-sm">
            {open.map((i, n) => (
              <li key={n}>
                <span className="font-medium">“{i.claim}”</span>
                <span className="text-muted-foreground"> — {i.problem}{i.source_id ? ` (${i.source_id})` : ""}</span>
                {canEdit && (
                  <button
                    type="button"
                    className="ml-2 text-xs text-primary underline"
                    onClick={() =>
                      setFeedback((f) => `${f ? f + "\n" : ""}Fix: "${i.claim}" — ${i.problem}${i.suggested_fix ? `. Suggested: ${i.suggested_fix}` : ""}`)
                    }
                  >
                    add to feedback
                  </button>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
      {fixed.length > 0 && (
        <p className="mt-3 flex items-center gap-1.5 text-sm text-emerald-700 dark:text-emerald-400" data-testid="fact-check-fixed">
          <CheckCircle2 className="size-4" /> Fact-check automatically corrected {fixed.length} claim{fixed.length === 1 ? "" : "s"} while writing.
        </p>
      )}

      {episode.last_revision_notes && (
        <p className="mt-3 rounded-sm bg-secondary/50 p-2 text-sm" data-testid="last-revision-notes">
          <span className="font-semibold">Last revision: </span>
          {episode.last_revision_notes}
        </p>
      )}

      {canEdit ? (
        <>
          <textarea
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            placeholder={'e.g. "The notice-of-intent window closes November 20, not this week — fix every mention. Shorten the budget story and give the Mercer County story more time."'}
            className="mt-3 h-28 w-full rounded-sm border border-border bg-background p-3 text-sm"
            data-testid="revise-feedback"
          />
          <label className="mt-2 flex cursor-pointer items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={research}
              onChange={(e) => setResearch(e.target.checked)}
              className="size-4 cursor-pointer accent-primary"
            />
            Allow new web research for this revision (use when asking to add or check something not already covered)
          </label>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <Button size="sm" disabled={revise.isPending || !feedback.trim()} onClick={() => revise.mutate()} data-testid="revise-button">
              {revise.isPending ? <Loader2 className="size-4 animate-spin" /> : <MessageSquareText className="size-4" />}
              {revise.isPending ? "Revising… (can take a minute or two)" : "Revise script"}
            </Button>
            <Button variant="outline" size="sm" onClick={() => setShowHistory((v) => !v)} data-testid="revision-history-toggle">
              <History className="size-4" /> {showHistory ? "Hide history" : `History${episode.revision_count ? ` (${episode.revision_count})` : ""}`}
            </Button>
          </div>
          <p className="mt-2 text-xs text-muted-foreground">
            Only the parts your feedback touches are changed; the rest stays word-for-word. The intro, chapter format and support read are preserved.
          </p>
        </>
      ) : (
        <p className="mt-3 text-sm text-muted-foreground">Your account is view-only.</p>
      )}

      {showHistory && (
        <ul className="mt-3 space-y-2 border-t border-border pt-3 text-sm" data-testid="revision-history">
          {(revisions ?? []).length === 0 && <li className="text-muted-foreground">No earlier versions yet.</li>}
          {(revisions ?? []).map((r) => (
            <li key={r.id} className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xs text-muted-foreground">{new Date(r.at).toLocaleString()}</p>
                <p className="whitespace-pre-wrap">{r.feedback}</p>
                {r.notes && <p className="text-xs text-muted-foreground">{r.notes}</p>}
              </div>
              {canEdit && (
                <Button
                  variant="outline"
                  size="sm"
                  disabled={restore.isPending}
                  onClick={() => restore.mutate(r.id)}
                  title="Put back the script as it was before this revision"
                >
                  <RotateCcw className="size-3.5" /> Restore
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
