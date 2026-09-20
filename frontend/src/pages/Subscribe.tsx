import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Mail, Loader2, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiPost, ApiError } from "@/lib/api";

// Public, unauthenticated newsletter sign-up. Single opt-in; every daily briefing email
// then carries a one-click unsubscribe link.
export default function Subscribe() {
  const [email, setEmail] = useState("");

  const subscribe = useMutation({
    mutationFn: (e: string) => apiPost<{ ok: boolean; message: string }>("/public/subscribe", { email: e }),
  });

  const done = subscribe.isSuccess;

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-5" data-testid="subscribe-page">
      <div className="w-full max-w-md">
        <div className="mb-8 text-center">
          <h1 className="font-heading text-3xl leading-tight font-bold tracking-tight">
            WVEdTalk News Desk
          </h1>
          <p className="mt-1 text-xs tracking-[0.18em] text-muted-foreground uppercase">
            Daily statewide education briefing
          </p>
        </div>

        <div className="rounded-md border border-border bg-card p-6 shadow-sm">
          {done ? (
            <div className="text-center" data-testid="subscribe-success">
              <CheckCircle2 className="mx-auto mb-3 size-8 text-primary" />
              <h2 className="font-heading text-lg font-bold">You're subscribed</h2>
              <p className="mt-2 text-sm text-muted-foreground">
                {subscribe.data?.message ??
                  "You'll receive the daily briefing. Every email has a one-click unsubscribe link."}
              </p>
            </div>
          ) : (
            <>
              <div className="mb-4 flex items-center gap-2">
                <Mail className="size-4 text-primary" />
                <h2 className="font-heading text-lg font-bold">Get the daily briefing</h2>
              </div>
              <p className="mb-4 text-sm text-muted-foreground">
                A concise, statewide look at West Virginia education news — delivered each morning.
                Unsubscribe anytime from any email.
              </p>
              <form
                className="space-y-3"
                onSubmit={(e) => {
                  e.preventDefault();
                  if (email.trim()) subscribe.mutate(email.trim());
                }}
              >
                <Input
                  type="email"
                  autoFocus
                  placeholder="you@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  data-testid="subscribe-email-input"
                />
                {subscribe.isError && (
                  <p className="text-sm text-destructive" data-testid="subscribe-error">
                    {subscribe.error instanceof ApiError
                      ? String((subscribe.error.body as { detail?: string })?.detail ?? "Could not subscribe — try again.")
                      : "Could not subscribe — try again."}
                  </p>
                )}
                <Button
                  type="submit"
                  className="w-full"
                  disabled={subscribe.isPending || !email.trim()}
                  data-testid="subscribe-submit"
                >
                  {subscribe.isPending ? <Loader2 className="size-4 animate-spin" /> : <Mail className="size-4" />}
                  Subscribe
                </Button>
              </form>
            </>
          )}
        </div>
        <p className="mt-4 text-center text-xs text-muted-foreground">
          We never ask for passwords or payment details by email.
        </p>
      </div>
    </div>
  );
}
