import { useSearchParams } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { MailX, Loader2, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { apiPost, ApiError } from "@/lib/api";

// Public, unauthenticated one-click unsubscribe. The email + HMAC token come from the
// link embedded in each daily briefing email (/unsubscribe?email=…&t=…).
export default function Unsubscribe() {
  const [params] = useSearchParams();
  const email = params.get("email") ?? "";
  const token = params.get("t") ?? "";

  const unsubscribe = useMutation({
    mutationFn: () =>
      apiPost<{ ok: boolean; message: string }>("/public/unsubscribe", { email, token }),
  });

  const done = unsubscribe.isSuccess;

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-5" data-testid="unsubscribe-page">
      <div className="w-full max-w-md">
        <div className="mb-8 text-center">
          <h1 className="font-heading text-3xl leading-tight font-bold tracking-tight">
            WVEdTalk News Desk
          </h1>
        </div>

        <div className="rounded-md border border-border bg-card p-6 text-center shadow-sm">
          {done ? (
            <div data-testid="unsubscribe-success">
              <CheckCircle2 className="mx-auto mb-3 size-8 text-primary" />
              <h2 className="font-heading text-lg font-bold">Unsubscribed</h2>
              <p className="mt-2 text-sm text-muted-foreground">
                {unsubscribe.data?.message ?? "You won't receive further briefings."}
              </p>
            </div>
          ) : (
            <>
              <MailX className="mx-auto mb-3 size-8 text-muted-foreground" />
              <h2 className="font-heading text-lg font-bold">Unsubscribe from the daily briefing</h2>
              <p className="mt-2 mb-4 text-sm text-muted-foreground">
                {email ? (
                  <>Stop sending the daily briefing to <span className="font-medium text-foreground">{email}</span>?</>
                ) : (
                  "This unsubscribe link is missing its details."
                )}
              </p>
              {unsubscribe.isError && (
                <p className="mb-3 text-sm text-destructive" data-testid="unsubscribe-error">
                  {unsubscribe.error instanceof ApiError
                    ? String((unsubscribe.error.body as { detail?: string })?.detail ?? "This link is invalid.")
                    : "Something went wrong — try again."}
                </p>
              )}
              <Button
                className="w-full"
                disabled={unsubscribe.isPending || !email || !token}
                onClick={() => unsubscribe.mutate()}
                data-testid="unsubscribe-submit"
              >
                {unsubscribe.isPending ? <Loader2 className="size-4 animate-spin" /> : <MailX className="size-4" />}
                Confirm unsubscribe
              </Button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
