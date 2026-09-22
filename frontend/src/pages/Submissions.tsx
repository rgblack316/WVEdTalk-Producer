import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { Inbox, ExternalLink, Heart, Trash2, Check, Archive, Ban, Save, LinkIcon } from "lucide-react";
import DeskLayout from "@/components/DeskLayout";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { apiGet, apiPatch, apiPost, apiDelete, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/useAuth";
import type { DeskConfig, StorySubmission } from "@/lib/types";

const FILTERS = [
  { value: "all", label: "All" },
  { value: "new", label: "New" },
  { value: "used", label: "Used" },
  { value: "rejected", label: "Rejected" },
  { value: "archived", label: "Archived" },
];

const STATUS_VARIANT: Record<string, "default" | "secondary" | "outline" | "destructive"> = {
  new: "secondary",
  used: "default",
  archived: "outline",
  rejected: "destructive",
};

function errMsg(e: unknown, fallback: string) {
  return e instanceof ApiError ? String((e.body as { detail?: string })?.detail ?? fallback) : fallback;
}

export default function Submissions() {
  const qc = useQueryClient();
  const { canEdit } = useAuth();
  const invalidate = () => qc.invalidateQueries({ queryKey: ["submissions"] });

  const { data, isLoading } = useQuery({
    queryKey: ["submissions"],
    queryFn: () => apiGet<StorySubmission[]>("/submissions"),
    refetchInterval: 60000,
  });

  const [filter, setFilter] = useState("all");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const filtered = (data ?? []).filter((s) => filter === "all" || s.status === filter);

  const { data: config } = useQuery({
    queryKey: ["config"],
    queryFn: () => apiGet<DeskConfig>("/settings"),
    staleTime: 60000,
  });

  const toggleAutoThank = useMutation({
    mutationFn: (enabled: boolean) => apiPost<DeskConfig>("/settings/auto-thank", { enabled }),
    onSuccess: (cfg) => {
      qc.setQueryData(["config"], cfg);
      toast.success(cfg.auto_thank_on_use ? "Auto-thank on use is on." : "Auto-thank on use is off.");
    },
    onError: (e) => toast.error(errMsg(e, "Could not update the setting.")),
  });

  const bulkReject = useMutation({
    mutationFn: (ids: string[]) => apiPost<{ ok: boolean; count: number }>("/submissions/bulk-reject", { ids }),
    onSuccess: (r) => {
      invalidate();
      setSelected(new Set());
      toast.success(`Rejected ${r.count} submission(s) — readers were notified.`);
    },
    onError: (e) => toast.error(errMsg(e, "Could not reject the selected tips.")),
  });

  const setStatus = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      apiPatch<StorySubmission>(`/submissions/${id}`, { status }),
    onSuccess: () => invalidate(),
    onError: (e) => toast.error(errMsg(e, "Could not update the submission.")),
  });

  const saveNote = useMutation({
    mutationFn: ({ id, note }: { id: string; note: string }) =>
      apiPatch<StorySubmission>(`/submissions/${id}`, { note }),
    onSuccess: () => {
      invalidate();
      toast.success("Note saved.");
    },
    onError: (e) => toast.error(errMsg(e, "Could not save the note.")),
  });

  const thank = useMutation({
    mutationFn: (id: string) => apiPost<StorySubmission>(`/submissions/${id}/thank`),
    onSuccess: () => {
      invalidate();
      toast.success("Thank-you email sent to the reader.");
    },
    onError: (e) => toast.error(errMsg(e, "Could not send the thank-you email.")),
  });

  const reject = useMutation({
    mutationFn: (id: string) => apiPost<StorySubmission>(`/submissions/${id}/reject`),
    onSuccess: () => {
      invalidate();
      toast.success("Submission rejected — the reader was notified.");
    },
    onError: (e) => toast.error(errMsg(e, "Could not reject the submission.")),
  });

  const remove = useMutation({
    mutationFn: (id: string) => apiDelete(`/submissions/${id}`),
    onSuccess: () => {
      invalidate();
      toast.success("Submission deleted.");
    },
    onError: (e) => toast.error(errMsg(e, "Could not delete the submission.")),
  });

  return (
    <DeskLayout>
      <div className="mb-8">
        <p className="text-xs tracking-[0.2em] text-accent uppercase">Reader Tips</p>
        <h2 className="font-heading text-3xl font-bold tracking-tight">Story submissions</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          News links sent in by the public for the desk to consider — newest first. Add a private note,
          reject anything not relevant to West Virginia, and thank readers whose tips make an edition.
        </p>
        {canEdit && (
          <label
            className="mt-3 inline-flex cursor-pointer items-center gap-2 text-sm"
            data-testid="auto-thank-toggle"
          >
            <input
              type="checkbox"
              checked={!!config?.auto_thank_on_use}
              onChange={(e) => toggleAutoThank.mutate(e.target.checked)}
              className="size-4 cursor-pointer accent-primary"
            />
            Auto-thank readers when their tip is used in a briefing or episode
          </label>
        )}
      </div>

      {isLoading ? (
        <div className="py-16 text-center text-muted-foreground">Loading submissions…</div>
      ) : data && data.length > 0 ? (
        <>
          <div className="mb-4 flex flex-wrap items-center gap-2" data-testid="submission-filters">
            {FILTERS.map((f) => (
              <button
                key={f.value}
                onClick={() => {
                  setSelected(new Set());
                  setFilter(f.value);
                }}
                className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                  filter === f.value
                    ? "border-primary bg-primary text-primary-foreground"
                    : "border-border bg-card hover:bg-muted"
                }`}
                data-testid={`filter-${f.value}`}
              >
                {f.label} ({f.value === "all" ? data.length : data.filter((s) => s.status === f.value).length})
              </button>
            ))}
          </div>

          {canEdit && selected.size > 0 && (
            <div
              className="mb-4 flex flex-wrap items-center justify-between gap-2 rounded-md border border-primary/40 bg-primary/5 px-4 py-2"
              data-testid="bulk-bar"
            >
              <span className="text-sm font-medium">{selected.size} selected</span>
              <div className="flex gap-2">
                <Button size="sm" variant="ghost" onClick={() => setSelected(new Set())} data-testid="bulk-clear">
                  Clear
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  className="text-destructive hover:text-destructive"
                  onClick={() => bulkReject.mutate([...selected])}
                  disabled={bulkReject.isPending}
                  data-testid="bulk-reject"
                >
                  <Ban className="size-4" /> Reject selected
                </Button>
              </div>
            </div>
          )}

          {filtered.length > 0 ? (
            <div className="space-y-4" data-testid="submissions-list">
              {filtered.map((s) => (
                <SubmissionCard
                  key={s.id}
                  s={s}
                  canEdit={canEdit}
                  selected={selected.has(s.id)}
                  onToggleSelect={() =>
                    setSelected((prev) => {
                      const n = new Set(prev);
                      if (n.has(s.id)) n.delete(s.id);
                      else n.add(s.id);
                      return n;
                    })
                  }
                  onStatus={(status) => setStatus.mutate({ id: s.id, status })}
                  onSaveNote={(note) => saveNote.mutate({ id: s.id, note })}
                  onThank={() => thank.mutate(s.id)}
                  onReject={() => reject.mutate(s.id)}
                  onDelete={() => remove.mutate(s.id)}
                  busy={
                    setStatus.isPending ||
                    saveNote.isPending ||
                    thank.isPending ||
                    reject.isPending ||
                    remove.isPending ||
                    bulkReject.isPending
                  }
                />
              ))}
            </div>
          ) : (
            <div className="py-12 text-center text-sm text-muted-foreground" data-testid="submissions-filter-empty">
              No {filter} submissions.
            </div>
          )}
        </>
      ) : (
        <div className="py-16 text-center" data-testid="submissions-empty">
          <Inbox className="mx-auto mb-4 size-10 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">
            No submissions yet. Share your public submit link so readers can send in story tips.
          </p>
        </div>
      )}
    </DeskLayout>
  );
}

function SubmissionCard({
  s,
  canEdit,
  selected,
  onToggleSelect,
  onStatus,
  onSaveNote,
  onThank,
  onReject,
  onDelete,
  busy,
}: {
  s: StorySubmission;
  canEdit: boolean;
  selected: boolean;
  onToggleSelect: () => void;
  onStatus: (status: string) => void;
  onSaveNote: (note: string) => void;
  onThank: () => void;
  onReject: () => void;
  onDelete: () => void;
  busy: boolean;
}) {
  const [note, setNote] = useState(s.note ?? "");
  const dirty = note !== (s.note ?? "");

  return (
    <div className="rounded-md border border-border bg-card p-5" data-testid={`submission-${s.id}`}>
      <div className="mb-2 flex flex-wrap items-center gap-2 text-xs">
        {canEdit && (
          <input
            type="checkbox"
            checked={selected}
            onChange={onToggleSelect}
            className="size-4 cursor-pointer accent-primary"
            aria-label="Select submission"
            data-testid={`submission-select-${s.id}`}
          />
        )}
        <Badge variant={STATUS_VARIANT[s.status] ?? "secondary"} data-testid={`submission-status-${s.id}`}>
          {s.status}
        </Badge>
        {s.thanked && (
          <Badge variant="outline" className="gap-1 text-primary">
            <Heart className="size-3 fill-current" /> Thanked
          </Badge>
        )}
        <span className="text-muted-foreground">{new Date(s.submitted_at).toLocaleString()}</span>
      </div>

      <a
        href={s.url}
        target="_blank"
        rel="noreferrer noopener"
        className="inline-flex items-center gap-1 font-heading text-lg font-bold tracking-tight break-all transition-colors hover:text-primary"
        data-testid={`submission-url-${s.id}`}
      >
        {s.url}
        <ExternalLink className="size-4 shrink-0" />
      </a>

      <p className="mt-2 text-sm text-muted-foreground" data-testid={`submission-by-${s.id}`}>
        Submitted by <span className="font-medium text-foreground">{s.name}</span> ·{" "}
        <a href={`mailto:${s.email}`} className="text-primary underline-offset-2 hover:underline">
          {s.email}
        </a>
      </p>

      {s.used_in && s.used_ref && (
        <Link
          to={s.used_ref}
          className="mt-2 inline-flex items-center gap-1 text-xs text-primary underline-offset-2 hover:underline"
          data-testid={`submission-usedin-${s.id}`}
        >
          <LinkIcon className="size-3" /> Appeared in: {s.used_in}
        </Link>
      )}

      {canEdit && (
        <>
          <Textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Private note — why it matters, follow-ups…"
            className="mt-4 text-sm"
            data-testid={`submission-note-${s.id}`}
          />
          <div className="mt-3 flex flex-wrap gap-2">
            <Button
              size="sm"
              variant="secondary"
              onClick={() => onSaveNote(note)}
              disabled={busy || !dirty}
              data-testid={`submission-savenote-${s.id}`}
            >
              <Save className="size-4" /> Save note
            </Button>
            <Button
              size="sm"
              variant={s.status === "used" ? "default" : "outline"}
              onClick={() => onStatus(s.status === "used" ? "new" : "used")}
              disabled={busy}
              data-testid={`submission-use-${s.id}`}
            >
              <Check className="size-4" /> {s.status === "used" ? "Used" : "Mark used"}
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => onStatus(s.status === "archived" ? "new" : "archived")}
              disabled={busy}
              data-testid={`submission-archive-${s.id}`}
            >
              <Archive className="size-4" /> {s.status === "archived" ? "Un-archive" : "Archive"}
            </Button>
            <Button
              size="sm"
              variant="outline"
              className="text-destructive hover:text-destructive"
              onClick={onReject}
              disabled={busy || s.status === "rejected"}
              data-testid={`submission-reject-${s.id}`}
            >
              <Ban className="size-4" /> Reject
            </Button>
            <Button
              size="sm"
              variant="secondary"
              onClick={onThank}
              disabled={busy}
              data-testid={`submission-thank-${s.id}`}
            >
              <Heart className="size-4" /> {s.thanked ? "Thank again" : "Send thanks"}
            </Button>
            <Button
              size="sm"
              variant="ghost"
              className="text-destructive hover:text-destructive"
              onClick={onDelete}
              disabled={busy}
              data-testid={`submission-delete-${s.id}`}
            >
              <Trash2 className="size-4" /> Delete
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
