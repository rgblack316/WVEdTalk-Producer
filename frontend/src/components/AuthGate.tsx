import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Lock, Loader2, Mail, KeyRound } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiGet, apiPost, ApiError } from "@/lib/api";
import { beginSession } from "@/lib/session";
import type { AuthState } from "@/lib/types";

export default function AuthGate({ children }: { children: React.ReactNode }) {
  const qc = useQueryClient();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["auth", "me"],
    queryFn: () => apiGet<AuthState>("/auth/me"),
    retry: false,
    staleTime: 5 * 60 * 1000,
  });

  const login = useMutation({
    mutationFn: (creds: { email: string; password: string }) =>
      apiPost<AuthState>("/auth/login", creds),
    onSuccess: async () => {
      setError("");
      setPassword("");
      await beginSession(qc);
    },
    onError: (e) => {
      setError(
        e instanceof ApiError && (e.status === 401 || e.status === 429)
          ? String((e.body as { detail?: string })?.detail ?? "Incorrect email or password.")
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
            WVEdTalk News Desk
          </h1>
          <p className="mt-1 text-xs tracking-[0.18em] text-muted-foreground uppercase">
            Statewide research &amp; editorial briefing
          </p>
        </div>
        <div className="rounded-md border border-border bg-card p-6 shadow-sm">
          <div className="mb-4 flex items-center gap-2">
            <Lock className="size-4 text-primary" />
            <h2 className="font-heading text-lg font-bold">Sign in</h2>
          </div>
          <p className="mb-4 text-sm text-muted-foreground">
            This desk is private. Sign in with your account to continue.
          </p>
          <form
            className="space-y-3"
            onSubmit={(e) => {
              e.preventDefault();
              if (email.trim() && password) login.mutate({ email: email.trim(), password });
            }}
          >
            <div className="relative">
              <Mail className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                type="email"
                autoFocus
                autoComplete="email"
                placeholder="you@example.com"
                className="pl-9"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                data-testid="login-email-input"
              />
            </div>
            <div className="relative">
              <KeyRound className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                type="password"
                autoComplete="current-password"
                placeholder="Password"
                className="pl-9"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                data-testid="login-password-input"
              />
            </div>
            {error && (
              <p className="text-sm text-destructive" data-testid="login-error">
                {error}
              </p>
            )}
            <Button
              type="submit"
              className="w-full"
              disabled={login.isPending || !email.trim() || !password}
              data-testid="login-submit"
            >
              {login.isPending ? <Loader2 className="size-4 animate-spin" /> : <Lock className="size-4" />}
              Sign in
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
}
