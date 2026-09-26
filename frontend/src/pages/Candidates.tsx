import { useMemo, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Star, Trash2, Loader2 } from "lucide-react";
import { toast } from "sonner";
import DeskLayout from "@/components/DeskLayout";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ScoreChip } from "@/components/StoryCard";
import { apiGet, apiPost, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/useAuth";
import type { CandidateStory } from "@/lib/types";

function formatDate(date: string) {
  const [y, m, d] = date.split("-").map(Number);
  if (!y || !m || !d) return date;
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  });
}

export default function Candidates() {
  const { canEdit } = useAuth();
  const qc = useQueryClient();
  // undefined = dialog closed; null = clear ALL; string = clear that edition's week.
  const [target, setTarget] = useState<string | null | undefined>(undefined);

  const { data, isLoading } = useQuery({
    queryKey: ["candidates"],
    queryFn: () => apiGet<CandidateStory[]>("/candidates"),
  });

  const clearMut = useMutation({
    mutationFn: (date: string | null) => apiPost<{ cleared: number }>("/candidates/clear", { date }),
    onSuccess: (r) => {
      qc.invalidateQueries({ queryKey: ["candidates"] });
      qc.invalidateQueries({ queryKey: ["briefing"] });
      toast.success(
        r.cleared === 0
          ? "No candidates to clear"
          : `Cleared ${r.cleared} candidate${r.cleared === 1 ? "" : "s"} (prep notes kept)`,
      );
    },
    onError: (e) =>
      toast.error(
        e instanceof ApiError ? String((e.body as { detail?: string })?.detail ?? e.message) : String(e),
      ),
  });

  // Group flagged stories by edition date. `data` arrives newest-first, and a Map keeps
  // insertion order, so the groups render newest week first.
  const groups = useMemo(() => {
    const m = new Map<string, CandidateStory[]>();
    (data ?? []).forEach((c) => {
      const arr = m.get(c.date) ?? [];
      arr.push(c);
      m.set(c.date, arr);
    });
    return Array.from(m.entries());
  }, [data]);

  const total = data?.length ?? 0;
  const hasCandidates = total > 0;
  const targetCount =
    target === null ? total : typeof target === "string" ? groups.find(([d]) => d === target)?.[1].length ?? 0 : 0;

  return (
    <DeskLayout>
      <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs tracking-[0.2em] text-accent uppercase">Podcast Prep</p>
          <h2 className="font-heading text-3xl font-bold tracking-tight">Episode candidates</h2>
          <p className="mt-2 text-sm text-muted-foreground">
            Every story flagged across all editions, newest first. Open a story to edit its prep notes.
          </p>
        </div>

        {canEdit && hasCandidates && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => setTarget(null)}
            data-testid="clear-candidates-button"
          >
            <Trash2 className="size-4" /> Clear all candidates
          </Button>
        )}
      </div>

      {isLoading ? (
        <div className="py-16 text-center text-muted-foreground">Loading candidates…</div>
      ) : hasCandidates ? (
        <div className="space-y-8" data-testid="candidate-list">
          {groups.map(([date, items]) => (
            <div key={date} data-testid={`candidate-week-${date}`}>
              <div className="mb-3 flex flex-wrap items-center justify-between gap-2 border-b border-border pb-1.5">
                <div className="flex items-center gap-2">
                  <Star className="size-3.5 fill-current text-accent" />
                  <span className="font-heading text-sm font-bold tracking-tight">{formatDate(date)}</span>
                  <span className="text-xs text-muted-foreground">
                    {items.length} flagged {items.length === 1 ? "story" : "stories"}
                  </span>
                </div>
                {canEdit && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-muted-foreground hover:text-destructive"
                    onClick={() => setTarget(date)}
                    data-testid={`clear-week-${date}`}
                  >
                    <Trash2 className="size-3.5" /> Clear this week
                  </Button>
                )}
              </div>
              <div className="space-y-4">
                {items.map(({ story }) => (
                  <div
                    key={story.id}
                    className="wire-rise rounded-md border border-border bg-card p-5"
                    data-testid={`candidate-${story.id}`}
                  >
                    <div className="mb-2 flex flex-wrap items-center gap-2 text-xs">
                      {story.location && (
                        <span className="tracking-[0.14em] text-muted-foreground uppercase">
                          {story.location}
                        </span>
                      )}
                      {story.classification?.map((c) => (
                        <Badge key={c} variant="secondary">
                          {c}
                        </Badge>
                      ))}
                    </div>
                    <Link
                      to={`/briefings/${date}/stories/${story.id}`}
                      className="font-heading text-xl font-bold tracking-tight transition-colors hover:text-primary"
                    >
                      {story.headline}
                    </Link>
                    <div className="mt-2 flex flex-wrap gap-2">
                      <ScoreChip label="Importance" value={story.importance} />
                      <ScoreChip label="Podcast" value={story.podcast_potential} />
                    </div>
                    {story.notes && (
                      <p className="mt-3 border-l-2 border-accent pl-3 text-sm text-muted-foreground">
                        {story.notes}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="py-16 text-center" data-testid="candidates-empty">
          <Star className="mx-auto mb-4 size-10 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">
            No episode candidates yet. Open any story and flag it to build the shortlist here.
          </p>
        </div>
      )}

      <Dialog open={target !== undefined} onOpenChange={(o) => !o && setTarget(undefined)}>
        <DialogContent data-testid="clear-candidates-dialog">
          <DialogHeader>
            <DialogTitle>
              {target ? "Clear this week's candidates?" : "Clear all episode candidates?"}
            </DialogTitle>
            <DialogDescription>
              This un-flags{" "}
              {target ? (
                <>
                  the {targetCount} flagged {targetCount === 1 ? "story" : "stories"} from{" "}
                  <strong>{formatDate(target)}</strong>
                </>
              ) : (
                <>
                  all {targetCount} flagged {targetCount === 1 ? "story" : "stories"}
                </>
              )}
              . Prep notes are kept, and nothing clears automatically — you can re-flag any story later
              if you produce the episode again.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setTarget(undefined)} data-testid="clear-candidates-cancel">
              Cancel
            </Button>
            <Button
              variant="destructive"
              disabled={clearMut.isPending}
              onClick={() => clearMut.mutate(target ?? null, { onSettled: () => setTarget(undefined) })}
              data-testid="clear-candidates-confirm"
            >
              {clearMut.isPending ? <Loader2 className="size-4 animate-spin" /> : <Trash2 className="size-4" />}
              {target ? "Clear this week" : "Clear candidates"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </DeskLayout>
  );
}
