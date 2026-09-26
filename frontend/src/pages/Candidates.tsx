import { useEffect, useMemo, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Star, Trash2, Loader2, CalendarRange } from "lucide-react";
import { toast } from "sonner";
import DeskLayout from "@/components/DeskLayout";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
import type { CandidateRef, CandidateStory, Story } from "@/lib/types";

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

function CandidateCard({ date, story, showDate }: { date: string; story: Story; showDate: boolean }) {
  return (
    <div className="wire-rise rounded-md border border-border bg-card p-5" data-testid={`candidate-${story.id}`}>
      <div className="mb-2 flex flex-wrap items-center gap-2 text-xs">
        {showDate && (
          <Badge variant="outline" className="gap-1">
            <Star className="size-3 fill-current" />
            {formatDate(date)}
          </Badge>
        )}
        {story.location && (
          <span className="tracking-[0.14em] text-muted-foreground uppercase">{story.location}</span>
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
        <p className="mt-3 border-l-2 border-accent pl-3 text-sm text-muted-foreground">{story.notes}</p>
      )}
    </div>
  );
}

type SortKey = "date" | "podcast" | "importance";
const SORTS: [SortKey, string][] = [
  ["date", "Date"],
  ["podcast", "Podcast potential"],
  ["importance", "Importance"],
];
const SORT_STORAGE_KEY = "wvedtalk.candidates.sort";
const isSortKey = (v: unknown): v is SortKey => v === "date" || v === "podcast" || v === "importance";

export default function Candidates() {
  const { canEdit } = useAuth();
  const qc = useQueryClient();
  // undefined = dialog closed; null = clear ALL; string = clear that edition's week.
  const [target, setTarget] = useState<string | null | undefined>(undefined);
  const [rangeOpen, setRangeOpen] = useState(false);
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  // Remember the chosen sort between visits so the board opens how the user left it.
  const [sort, setSort] = useState<SortKey>(() => {
    const saved = typeof window !== "undefined" ? window.localStorage.getItem(SORT_STORAGE_KEY) : null;
    return isSortKey(saved) ? saved : "date";
  });
  useEffect(() => {
    window.localStorage.setItem(SORT_STORAGE_KEY, sort);
  }, [sort]);

  const { data, isLoading } = useQuery({
    queryKey: ["candidates"],
    queryFn: () => apiGet<CandidateStory[]>("/candidates"),
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["candidates"] });
    qc.invalidateQueries({ queryKey: ["briefing"] });
  };
  const errText = (e: unknown) =>
    e instanceof ApiError ? String((e.body as { detail?: string })?.detail ?? e.message) : String(e);

  const reflag = useMutation({
    mutationFn: (refs: CandidateRef[]) => apiPost<{ restored: number }>("/candidates/reflag", { refs }),
    onSuccess: (r) => {
      invalidate();
      toast.success(`Restored ${r.restored} candidate${r.restored === 1 ? "" : "s"}`);
    },
    onError: (e) => toast.error(errText(e)),
  });

  const clearMut = useMutation({
    mutationFn: (body: { date?: string | null; from_date?: string; to_date?: string }) =>
      apiPost<{ cleared: number; refs: CandidateRef[] }>("/candidates/clear", body),
    onSuccess: (r) => {
      invalidate();
      if (r.cleared === 0) {
        toast.success("No candidates to clear");
        return;
      }
      toast.success(`Cleared ${r.cleared} candidate${r.cleared === 1 ? "" : "s"} (prep notes kept)`, {
        duration: 8000,
        action: { label: "Undo", onClick: () => reflag.mutate(r.refs) },
      });
    },
    onError: (e) => toast.error(errText(e)),
  });

  // Group flagged stories by edition date. `data` arrives newest-first, and a Map keeps insertion
  // order, so the groups render newest week first.
  const groups = useMemo(() => {
    const m = new Map<string, CandidateStory[]>();
    (data ?? []).forEach((c) => {
      const arr = m.get(c.date) ?? [];
      arr.push(c);
      m.set(c.date, arr);
    });
    return Array.from(m.entries());
  }, [data]);

  // Flat list sorted by the chosen score (desc). Used when sort !== "date".
  const sorted = useMemo(() => {
    const field = sort === "podcast" ? "podcast_potential" : "importance";
    return [...(data ?? [])].sort((a, b) => (b.story[field] ?? 0) - (a.story[field] ?? 0));
  }, [data, sort]);

  // Distinct edition dates (ascending) — bounds + defaults for the "clear a date range" picker.
  const dates = useMemo(() => Array.from(new Set((data ?? []).map((c) => c.date))).sort(), [data]);
  const openRange = () => {
    setFromDate(dates[0] ?? "");
    setToDate(dates[dates.length - 1] ?? "");
    setRangeOpen(true);
  };
  const rangeInvalid = !fromDate || !toDate || fromDate > toDate;

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
            Every story flagged across all editions. Open a story to edit its prep notes.
          </p>
        </div>

        {hasCandidates && (
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-1 rounded-md border border-border p-0.5" data-testid="candidate-sort">
              <span className="px-2 text-xs text-muted-foreground">Sort</span>
              {SORTS.map(([key, label]) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => setSort(key)}
                  data-testid={`sort-${key}`}
                  className={`rounded px-2.5 py-1 text-xs transition-colors duration-150 ${
                    sort === key
                      ? "bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
            {canEdit && dates.length >= 2 && (
              <Button variant="outline" size="sm" onClick={openRange} data-testid="clear-range-button">
                <CalendarRange className="size-4" /> Clear range…
              </Button>
            )}
            {canEdit && (
              <Button variant="outline" size="sm" onClick={() => setTarget(null)} data-testid="clear-candidates-button">
                <Trash2 className="size-4" /> Clear all candidates
              </Button>
            )}
          </div>
        )}
      </div>

      {isLoading ? (
        <div className="py-16 text-center text-muted-foreground">Loading candidates…</div>
      ) : !hasCandidates ? (
        <div className="py-16 text-center" data-testid="candidates-empty">
          <Star className="mx-auto mb-4 size-10 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">
            No episode candidates yet. Open any story and flag it to build the shortlist here.
          </p>
        </div>
      ) : sort === "date" ? (
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
                    data-testid={`clear-day-${date}`}
                  >
                    <Trash2 className="size-3.5" /> Clear this day
                  </Button>
                )}
              </div>
              <div className="space-y-4">
                {items.map(({ story }) => (
                  <CandidateCard key={story.id} date={date} story={story} showDate={false} />
                ))}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="space-y-4" data-testid="candidate-list">
          {sorted.map(({ date, story }) => (
            <CandidateCard key={story.id} date={date} story={story} showDate />
          ))}
        </div>
      )}

      <Dialog open={target !== undefined} onOpenChange={(o) => !o && setTarget(undefined)}>
        <DialogContent data-testid="clear-candidates-dialog">
          <DialogHeader>
            <DialogTitle>{target ? "Clear this day's candidates?" : "Clear all episode candidates?"}</DialogTitle>
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
              . Prep notes are kept, nothing clears automatically, and you can Undo right after — so
              anything cleared can be reconsidered if you produce the episode again.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setTarget(undefined)} data-testid="clear-candidates-cancel">
              Cancel
            </Button>
            <Button
              variant="destructive"
              disabled={clearMut.isPending}
              onClick={() => clearMut.mutate(target ? { date: target } : {}, { onSettled: () => setTarget(undefined) })}
              data-testid="clear-candidates-confirm"
            >
              {clearMut.isPending ? <Loader2 className="size-4 animate-spin" /> : <Trash2 className="size-4" />}
              {target ? "Clear this day" : "Clear candidates"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={rangeOpen} onOpenChange={(o) => !o && setRangeOpen(false)}>
        <DialogContent data-testid="clear-range-dialog">
          <DialogHeader>
            <DialogTitle>Clear candidates in a date range</DialogTitle>
            <DialogDescription>
              Un-flags every candidate whose edition date falls between these dates (inclusive). Prep
              notes are kept and you can Undo right after.
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-wrap items-end gap-3">
            <label className="flex flex-col gap-1 text-xs text-muted-foreground">
              From
              <Input
                type="date"
                value={fromDate}
                min={dates[0]}
                max={dates[dates.length - 1]}
                onChange={(e) => setFromDate(e.target.value)}
                data-testid="range-from"
              />
            </label>
            <label className="flex flex-col gap-1 text-xs text-muted-foreground">
              To
              <Input
                type="date"
                value={toDate}
                min={dates[0]}
                max={dates[dates.length - 1]}
                onChange={(e) => setToDate(e.target.value)}
                data-testid="range-to"
              />
            </label>
          </div>
          {fromDate && toDate && fromDate > toDate && (
            <p className="text-xs text-destructive" data-testid="range-error">
              The “from” date must be on or before the “to” date.
            </p>
          )}
          <DialogFooter>
            <Button variant="ghost" onClick={() => setRangeOpen(false)} data-testid="clear-range-cancel">
              Cancel
            </Button>
            <Button
              variant="destructive"
              disabled={clearMut.isPending || rangeInvalid}
              onClick={() =>
                clearMut.mutate({ from_date: fromDate, to_date: toDate }, { onSettled: () => setRangeOpen(false) })
              }
              data-testid="clear-range-confirm"
            >
              {clearMut.isPending ? <Loader2 className="size-4 animate-spin" /> : <Trash2 className="size-4" />}
              Clear range
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </DeskLayout>
  );
}
