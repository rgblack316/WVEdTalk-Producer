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
import type { StorySubmission } from "@/lib/types";

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
      </div>

      {isLoading ? (
        <div className="py-16 text-center text-muted-foreground">Loading submissions…</div>
      ) : data && data.length > 0 ? (
        <div className="space-y-4" data-testid="submissions-list">
          {data.map((s) => (
            <SubmissionCard
              key={s.id}
              s={s}
              canEdit={canEdit}
              onStatus={(status) => setStatus.mutate({ id: s.id, status })}
              onSaveNote={(note) => saveNote.mutate({ id: s.id, note })}
              onThank={() => thank.mutate(s.id)}
              onReject={() => reject.mutate(s.id)}
              onDelete={() => remove.mutate(s.id)}
              busy={setStatus.isPending || saveNote.isPending || thank.isPending || reject.isPending || remove.isPending}
            />
          ))}
        </div>
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
  onStatus,
  onSaveNote,
  onThank,
  onReject,
  onDelete,
  busy,
}: {
  s: StorySubmission;
  canEdit: boolean;
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
