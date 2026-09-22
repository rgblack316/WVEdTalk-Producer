import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Newspaper, Loader2, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiPost, ApiError } from "@/lib/api";

// Public, unauthenticated news-tip submission. Sending a story also subscribes the reader to the
// daily briefing. The desk verifies every link independently before it can appear in a briefing.
export default function SubmitStory() {
  const [url, setUrl] = useState("");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");

  const submit = useMutation({
    mutationFn: (payload: { url: string; name: string; email: string }) =>
      apiPost<{ ok: boolean; message: string }>("/public/submit-story", payload),
  });

  const done = submit.isSuccess;
  const ready = url.trim() && name.trim() && email.trim();

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-5" data-testid="submit-story-page">
      <div className="w-full max-w-md">
        <div className="mb-8 text-center">
          <img src="/wvedtalk-logo.png" alt="WVEdTalk News Desk" className="mx-auto w-full max-w-[300px]" />
          <p className="mt-2 text-xs tracking-[0.18em] text-muted-foreground uppercase">
            Submit a West Virginia education story
          </p>
        </div>

        <div className="rounded-md border border-border bg-card p-6 shadow-sm">
          {done ? (
            <div className="text-center" data-testid="submit-success">
              <CheckCircle2 className="mx-auto mb-3 size-8 text-primary" />
              <h2 className="font-heading text-lg font-bold">Story submitted</h2>
              <p className="mt-2 text-sm text-muted-foreground">
                {submit.data?.message ??
                  "Thank you! Your story has been submitted for the desk to consider, and you're now subscribed to the daily briefing."}
              </p>
            </div>
          ) : (
            <>
              <div className="mb-4 flex items-center gap-2">
                <Newspaper className="size-4 text-primary" />
                <h2 className="font-heading text-lg font-bold">Send us a story</h2>
              </div>
              <p className="mb-4 text-sm text-muted-foreground">
                Spotted a West Virginia education story we should cover? Share the link and we'll consider
                it for an upcoming daily briefing or podcast episode. Submitting also subscribes you to the
                daily briefing — unsubscribe anytime.
              </p>
              <form
                className="space-y-3"
                onSubmit={(e) => {
                  e.preventDefault();
                  if (ready) submit.mutate({ url: url.trim(), name: name.trim(), email: email.trim() });
                }}
              >
                <Input
                  type="url"
                  autoFocus
                  placeholder="https://link-to-the-story.com/article"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  data-testid="submit-url-input"
                />
                <Input
                  type="text"
                  placeholder="Your name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  data-testid="submit-name-input"
                />
                <Input
                  type="email"
                  placeholder="you@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  data-testid="submit-email-input"
                />
                {submit.isError && (
                  <p className="text-sm text-destructive" data-testid="submit-error">
                    {submit.error instanceof ApiError
                      ? String((submit.error.body as { detail?: string })?.detail ?? "Could not submit — try again.")
                      : "Could not submit — try again."}
                  </p>
                )}
                <Button
                  type="submit"
                  className="w-full"
                  disabled={submit.isPending || !ready}
                  data-testid="submit-story-button"
                >
                  {submit.isPending ? <Loader2 className="size-4 animate-spin" /> : <Newspaper className="size-4" />}
                  Submit story
                </Button>
              </form>
            </>
          )}
        </div>
        <p className="mt-4 text-center text-xs text-muted-foreground">
          Just want the briefing?{" "}
          <Link to="/subscribe" className="text-primary underline-offset-2 hover:underline">
            Subscribe here
          </Link>
          .
        </p>
      </div>
    </div>
  );
}
