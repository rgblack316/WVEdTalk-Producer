import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Inbox, ExternalLink, Heart, Trash2, Check, Archive } from "lucide-react";
import DeskLayout from "@/components/DeskLayout";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { apiGet, apiPatch, apiPost, apiDelete, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/useAuth";
import type { StorySubmission } from "@/lib/types";

const STATUS_VARIANT: Record<string, "secondary" | "outline" | "destructive"> = {
  new: "secondary",
  used: "outline",
  archived: "destructive",
};

function errMsg(e: unknown, fallback: string) {
  return e instanceof ApiError
    ? String((e.body as { detail?: string })?.detail ?? fallback)
    : fallback;
}

export default function Submissions() {
  const qc = useQueryClient();
  const { canEdit } = useAuth();

  const { data, isLoading } = useQuery({
    queryKey: ["submissions"],
    queryFn: () => apiGet<StorySubmission[]>("/submissions"),
    refetchInterval: 60000,
  });

  const invalidate = () => qc.invalidateQueries({ queryKey: ["submissions"] });

  const setStatus = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      apiPatch<StorySubmission>(`/submissions/${id}`, { status }),
    onSuccess: () => invalidate(),
    onError: (e) => toast.error(errMsg(e, "Could not update the submission.")),
  });

  const thank = useMutation({
    mutationFn: (id: string) => apiPost<StorySubmission>(`/submissions/${id}/thank`),
    onSuccess: () => {
      invalidate();
      toast.success("Thank-you email sent to the reader.");
    },
    onError: (e) => toast.error(errMsg(e, "Could not send the thank-you email.")),
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
          News links sent in by the public for the desk to consider — newest first. Mark the ones you
          use, and send a thank-you when a submission makes it into a briefing or episode.
        </p>
      </div>

      {isLoading ? (
        <div className="py-16 text-center text-muted-foreground">Loading submissions…</div>
      ) : data && data.length > 0 ? (
        <div className="space-y-4" data-testid="submissions-list">
          {data.map((s) => (
            <div
              key={s.id}
              className="rounded-md border border-border bg-card p-5"
              data-testid={`submission-${s.id}`}
            >
              <div className="mb-2 flex flex-wrap items-center gap-2 text-xs">
                <Badge variant={STATUS_VARIANT[s.status] ?? "secondary"} data-testid={`submission-status-${s.id}`}>
                  {s.status}
                </Badge>
                {s.thanked && (
                  <Badge variant="outline" className="gap-1 text-primary">
                    <Heart className="size-3 fill-current" /> Thanked
                  </Badge>
                )}
                <span className="text-muted-foreground">
                  {new Date(s.submitted_at).toLocaleString()}
                </span>
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

              {canEdit && (
                <div className="mt-4 flex flex-wrap gap-2">
                  <Button
                    size="sm"
                    variant={s.status === "used" ? "default" : "outline"}
                    onClick={() => setStatus.mutate({ id: s.id, status: s.status === "used" ? "new" : "used" })}
                    disabled={setStatus.isPending}
                    data-testid={`submission-use-${s.id}`}
                  >
                    <Check className="size-4" /> {s.status === "used" ? "Used" : "Mark used"}
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() =>
                      setStatus.mutate({ id: s.id, status: s.status === "archived" ? "new" : "archived" })
                    }
                    disabled={setStatus.isPending}
                    data-testid={`submission-archive-${s.id}`}
                  >
                    <Archive className="size-4" /> {s.status === "archived" ? "Un-archive" : "Archive"}
                  </Button>
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => thank.mutate(s.id)}
                    disabled={thank.isPending}
                    data-testid={`submission-thank-${s.id}`}
                  >
                    <Heart className="size-4" /> {s.thanked ? "Thank again" : "Send thanks"}
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="text-destructive hover:text-destructive"
                    onClick={() => remove.mutate(s.id)}
                    disabled={remove.isPending}
                    data-testid={`submission-delete-${s.id}`}
                  >
                    <Trash2 className="size-4" /> Delete
                  </Button>
                </div>
              )}
            </div>
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
