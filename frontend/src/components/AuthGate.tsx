import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Lock, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiGet, apiPost, ApiError } from "@/lib/api";
import { beginSession } from "@/lib/session";

interface AuthState {
  authenticated: boolean;
}

export default function AuthGate({ children }: { children: React.ReactNode }) {
  const qc = useQueryClient();
  const [passcode, setPasscode] = useState("");
  const [error, setError] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["auth", "me"],
    queryFn: () => apiGet<AuthState>("/auth/me"),
    retry: false,
    staleTime: 5 * 60 * 1000,
  });

  const login = useMutation({
    mutationFn: (code: string) => apiPost<AuthState>("/auth/login", { passcode: code }),
    onSuccess: async () => {
      setError("");
      setPasscode("");
      await beginSession(qc);
    },
    onError: (e) => {
      setError(
        e instanceof ApiError && e.status === 401
          ? "Incorrect passcode. Please try again."
          : "Could not reach the desk. Check your connection and try again.",
      );
    },
  });

  // While we don't yet know, show a neutral splash (never a blank page).
  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <Loader2 className="size-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (data?.authenticated) return <>{children}</>;

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-5" data-testid="auth-gate">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <h1 className="font-heading text-3xl leading-tight font-bold tracking-tight">
            WV Education News Desk
          </h1>
          <p className="mt-1 text-xs tracking-[0.18em] text-muted-foreground uppercase">
            Statewide research &amp; editorial briefing
          </p>
        </div>
        <div className="rounded-md border border-border bg-card p-6 shadow-sm">
          <div className="mb-4 flex items-center gap-2">
            <Lock className="size-4 text-primary" />
            <h2 className="font-heading text-lg font-bold">Enter passcode</h2>
          </div>
          <p className="mb-4 text-sm text-muted-foreground">
            This desk is private. Enter the shared passcode to continue.
          </p>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (passcode.trim()) login.mutate(passcode.trim());
            }}
          >
            <Input
              type="password"
              autoFocus
              placeholder="Passcode"
              value={passcode}
              onChange={(e) => setPasscode(e.target.value)}
              data-testid="passcode-input"
            />
            {error && (
              <p className="mt-2 text-sm text-destructive" data-testid="passcode-error">
                {error}
              </p>
            )}
            <Button
              type="submit"
              className="mt-4 w-full"
              disabled={login.isPending || !passcode.trim()}
              data-testid="passcode-submit"
            >
              {login.isPending ? <Loader2 className="size-4 animate-spin" /> : <Lock className="size-4" />}
              Unlock desk
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
}
