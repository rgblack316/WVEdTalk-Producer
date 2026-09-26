import { useState } from "react";
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
  const [confirmOpen, setConfirmOpen] = useState(false);
  const { data, isLoading } = useQuery({
    queryKey: ["candidates"],
    queryFn: () => apiGet<CandidateStory[]>("/candidates"),
  });

  const clearAll = useMutation({
    mutationFn: () => apiPost<{ cleared: number }>("/candidates/clear"),
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

  const hasCandidates = !!data && data.length > 0;

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
          <>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setConfirmOpen(true)}
              data-testid="clear-candidates-button"
            >
              <Trash2 className="size-4" /> Clear all candidates
            </Button>
            <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
              <DialogContent data-testid="clear-candidates-dialog">
                <DialogHeader>
                  <DialogTitle>Clear all episode candidates?</DialogTitle>
                  <DialogDescription>
                    This un-flags all {data?.length} flagged {data?.length === 1 ? "story" : "stories"} so
                    the shortlist starts fresh for the next week. Prep notes are kept, and nothing clears
                    automatically — you can re-flag any story later if you produce the episode again.
                  </DialogDescription>
                </DialogHeader>
                <DialogFooter>
                  <Button
                    variant="ghost"
                    onClick={() => setConfirmOpen(false)}
                    data-testid="clear-candidates-cancel"
                  >
                    Cancel
                  </Button>
                  <Button
                    variant="destructive"
                    disabled={clearAll.isPending}
                    onClick={() => clearAll.mutate(undefined, { onSettled: () => setConfirmOpen(false) })}
                    data-testid="clear-candidates-confirm"
                  >
                    {clearAll.isPending ? <Loader2 className="size-4 animate-spin" /> : <Trash2 className="size-4" />}
                    Clear candidates
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </>
        )}
      </div>

      {isLoading ? (
        <div className="py-16 text-center text-muted-foreground">Loading candidates…</div>
      ) : hasCandidates ? (
        <div className="space-y-4" data-testid="candidate-list">
          {data.map(({ date, story }) => (
            <div
              key={story.id}
              className="wire-rise rounded-md border border-border bg-card p-5"
              data-testid={`candidate-${story.id}`}
            >
              <div className="mb-2 flex flex-wrap items-center gap-2 text-xs">
                <Badge variant="outline" className="gap-1">
                  <Star className="size-3 fill-current" />
                  {formatDate(date)}
                </Badge>
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
      ) : (
        <div className="py-16 text-center" data-testid="candidates-empty">
          <Star className="mx-auto mb-4 size-10 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">
            No episode candidates yet. Open any story and flag it to build the shortlist here.
          </p>
        </div>
      )}
    </DeskLayout>
  );
}
