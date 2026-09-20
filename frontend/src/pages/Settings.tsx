import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Mail, Eye, Trash2, Send, Gauge, ShieldCheck, Timer, KeyRound } from "lucide-react";
import DeskLayout from "@/components/DeskLayout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { apiGet, apiPost, apiDelete, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/useAuth";
import type { AuthState, DeskConfig } from "@/lib/types";

function errMsg(e: unknown) {
  return e instanceof ApiError
    ? String((e.body as { detail?: string })?.detail ?? e.message)
    : String(e);
}

export default function Settings() {
  const qc = useQueryClient();
  const { canEdit } = useAuth();
  const [email, setEmail] = useState("");
  const [term, setTerm] = useState("");
  const [current, setCurrent] = useState("");
  const [newPass, setNewPass] = useState("");
  const [confirm, setConfirm] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["config"],
    queryFn: () => apiGet<DeskConfig>("/settings"),
  });

  const { data: auth } = useQuery({
    queryKey: ["auth", "me"],
    queryFn: () => apiGet<AuthState>("/auth/me"),
    staleTime: 5 * 60 * 1000,
  });

  const invalidate = (cfg: DeskConfig) => qc.setQueryData(["config"], cfg);

  const addRecipient = useMutation({
    mutationFn: (e: string) => apiPost<DeskConfig>("/settings/recipients", { email: e }),
    onSuccess: (cfg) => {
      invalidate(cfg);
      setEmail("");
      toast.success("Recipient added");
    },
    onError: (e) => toast.error(errMsg(e)),
  });

  const removeRecipient = useMutation({
    mutationFn: (e: string) => apiDelete<DeskConfig>(`/settings/recipients/${encodeURIComponent(e)}`),
    onSuccess: (cfg) => invalidate(cfg),
    onError: (e) => toast.error(errMsg(e)),
  });

  const addTerm = useMutation({
    mutationFn: (t: string) => apiPost<DeskConfig>("/settings/watch-terms", { term: t }),
    onSuccess: (cfg) => {
      invalidate(cfg);
      setTerm("");
      toast.success("Watch term added");
    },
    onError: (e) => toast.error(errMsg(e)),
  });

  const removeTerm = useMutation({
    mutationFn: (t: string) => apiDelete<DeskConfig>(`/settings/watch-terms/${encodeURIComponent(t)}`),
    onSuccess: (cfg) => invalidate(cfg),
    onError: (e) => toast.error(errMsg(e)),
  });

  const sendNow = useMutation({
    mutationFn: () => apiPost<{ sent: number }>("/settings/send-digest"),
    onSuccess: (r) => toast.success(`Digest sent to ${r.sent} recipient${r.sent === 1 ? "" : "s"}`),
    onError: (e) => toast.error(errMsg(e)),
  });

  const setLength = useMutation({
    mutationFn: (value: string) => apiPost<DeskConfig>("/settings/script-length", { value }),
    onSuccess: (cfg) => {
      invalidate(cfg);
      toast.success("Script length preference saved");
    },
    onError: (e) => toast.error(errMsg(e)),
  });

  const setAutoLock = useMutation({
    mutationFn: (minutes: number) => apiPost<DeskConfig>("/settings/auto-lock", { minutes }),
    onSuccess: (cfg) => {
      invalidate(cfg);
      toast.success("Auto-lock preference saved");
    },
    onError: (e) => toast.error(errMsg(e)),
  });

  const changePassword = useMutation({
    mutationFn: () =>
      apiPost<{ ok: boolean }>("/settings/password", {
        current_password: current,
        new_password: newPass,
      }),
    onSuccess: () => {
      setCurrent("");
      setNewPass("");
      setConfirm("");
      toast.success("Password changed.");
    },
    onError: (e) => toast.error(errMsg(e)),
  });

  const recipients = data?.recipients ?? [];
  const terms = data?.watch_terms ?? [];
  const length = data?.script_length ?? "standard";
  const autoLock = data?.auto_lock_minutes ?? 0;

  const LENGTHS: { id: string; label: string; hint: string }[] = [
    { id: "concise", label: "Concise", hint: "~10–13 min" },
    { id: "standard", label: "Standard", hint: "~15–20 min" },
    { id: "full", label: "Full", hint: "~20–26 min" },
  ];
  const LOCK_OPTIONS: { minutes: number; label: string }[] = [
    { minutes: 0, label: "Off" },
    { minutes: 5, label: "5 min" },
    { minutes: 15, label: "15 min" },
    { minutes: 30, label: "30 min" },
    { minutes: 60, label: "60 min" },
  ];
  const passwordValid = current.trim() && newPass.trim().length >= 8 && newPass === confirm;

  return (
    <DeskLayout>
      <div className="mb-8">
        <p className="text-xs tracking-[0.2em] text-accent uppercase">Settings</p>
        <h2 className="font-heading text-3xl font-bold tracking-tight">Desk settings</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          Manage who receives the morning email digest and which topics or counties the desk should
          flag on every edition.
        </p>
      </div>

      {isLoading ? (
        <div className="py-16 text-center text-muted-foreground">Loading settings…</div>
      ) : (
        <div className="grid gap-8 md:grid-cols-2">
          {/* Account: my password + auto-lock */}
          <section
            className="rounded-md border border-border bg-card p-5 md:col-span-2"
            data-testid="security-panel"
          >
            <h3 className="flex items-center gap-2 font-heading text-lg font-bold">
              <ShieldCheck className="size-4 text-primary" /> My account
            </h3>
            {auth?.user && (
              <p className="mt-1 text-xs text-muted-foreground" data-testid="account-identity">
                Signed in as <span className="font-medium text-foreground">{auth.user.email}</span> ·{" "}
                <Badge variant="secondary">{auth.user.role}</Badge>
              </p>
            )}
            <div className="mt-4 grid gap-6 md:grid-cols-2">
              {/* Change password */}
              <div>
                <p className="flex items-center gap-1.5 text-sm font-semibold">
                  <KeyRound className="size-4 text-primary" /> Change password
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Update your own password. You'll stay signed in on this browser.
                </p>
                <form
                  className="mt-3 space-y-2"
                  onSubmit={(e) => {
                    e.preventDefault();
                    if (passwordValid) changePassword.mutate();
                  }}
                >
                  <Input
                    type="password"
                    autoComplete="current-password"
                    placeholder="Current password"
                    value={current}
                    onChange={(e) => setCurrent(e.target.value)}
                    data-testid="current-password-input"
                  />
                  <Input
                    type="password"
                    autoComplete="new-password"
                    placeholder="New password (min 8 characters)"
                    value={newPass}
                    onChange={(e) => setNewPass(e.target.value)}
                    data-testid="new-password-input"
                  />
                  <Input
                    type="password"
                    autoComplete="new-password"
                    placeholder="Confirm new password"
                    value={confirm}
                    onChange={(e) => setConfirm(e.target.value)}
                    data-testid="confirm-password-input"
                  />
                  {confirm && newPass !== confirm && (
                    <p className="text-xs text-destructive">Passwords don't match.</p>
                  )}
                  <Button
                    type="submit"
                    size="sm"
                    disabled={!passwordValid || changePassword.isPending}
                    data-testid="change-password-button"
                  >
                    Update password
                  </Button>
                </form>
              </div>

              {/* Auto-lock (shared config — editors only) */}
              {canEdit && (
              <div>
                <p className="flex items-center gap-1.5 text-sm font-semibold">
                  <Timer className="size-4 text-accent" /> Auto-lock on inactivity
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Sign this browser out automatically after a period with no activity — useful on
                  shared machines.
                </p>
                <div className="mt-3 flex flex-wrap gap-2" data-testid="auto-lock-options">
                  {LOCK_OPTIONS.map((o) => (
                    <button
                      key={o.minutes}
                      onClick={() => setAutoLock.mutate(o.minutes)}
                      disabled={setAutoLock.isPending}
                      data-testid={`auto-lock-${o.minutes}`}
                      className={`rounded-sm border px-3 py-1.5 text-sm transition-colors duration-150 ${
                        autoLock === o.minutes
                          ? "border-primary bg-primary text-primary-foreground"
                          : "border-border bg-background hover:border-primary/50"
                      }`}
                    >
                      {o.label}
                    </button>
                  ))}
                </div>
              </div>
              )}
            </div>
          </section>

          {/* Weekly script length */}
          {canEdit && (
          <section
            className="rounded-md border border-border bg-card p-5 md:col-span-2"
            data-testid="script-length-panel"
          >
            <h3 className="flex items-center gap-2 font-heading text-lg font-bold">
              <Gauge className="size-4 text-primary" /> WVEdTalk script length
            </h3>
            <p className="mt-1 text-sm text-muted-foreground">
              Nudge the weekly episode toward a shorter or fuller target. It's only a target — a quiet
              week still yields a shorter episode, and no important story is cut to hit a length.
            </p>
            <div className="mt-4 flex flex-wrap gap-2" data-testid="script-length-options">
              {LENGTHS.map((l) => (
                <button
                  key={l.id}
                  onClick={() => setLength.mutate(l.id)}
                  disabled={setLength.isPending}
                  data-testid={`script-length-${l.id}`}
                  className={`rounded-sm border px-4 py-2 text-left transition-colors duration-150 ${
                    length === l.id
                      ? "border-primary bg-primary text-primary-foreground"
                      : "border-border bg-background hover:border-primary/50"
                  }`}
                >
                  <span className="block text-sm font-semibold">{l.label}</span>
                  <span className={`block text-xs ${length === l.id ? "text-primary-foreground/80" : "text-muted-foreground"}`}>
                    {l.hint}
                  </span>
                </button>
              ))}
            </div>
          </section>
          )}

          {/* Email digest recipients */}
          {canEdit && (
          <section className="rounded-md border border-border bg-card p-5" data-testid="recipients-panel">
            <h3 className="flex items-center gap-2 font-heading text-lg font-bold">
              <Mail className="size-4 text-primary" /> Email digest
            </h3>
            <p className="mt-1 text-sm text-muted-foreground">
              The full briefing is emailed to everyone below the moment each 6:00 AM run finishes.
            </p>
            <form
              className="mt-4 flex gap-2"
              onSubmit={(e) => {
                e.preventDefault();
                if (email.trim()) addRecipient.mutate(email.trim());
              }}
            >
              <Input
                type="email"
                placeholder="host@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                data-testid="recipient-input"
              />
              <Button type="submit" disabled={addRecipient.isPending} data-testid="add-recipient-button">
                Add
              </Button>
            </form>

            <ul className="mt-4 space-y-2" data-testid="recipients-list">
              {recipients.length === 0 && (
                <li className="text-sm text-muted-foreground">No recipients yet.</li>
              )}
              {recipients.map((r) => (
                <li
                  key={r}
                  className="flex items-center justify-between rounded-sm border border-border bg-background px-3 py-2 text-sm"
                  data-testid={`recipient-${r}`}
                >
                  <span>{r}</span>
                  <button
                    onClick={() => removeRecipient.mutate(r)}
                    className="text-muted-foreground transition-colors hover:text-destructive"
                    data-testid={`remove-recipient-${r}`}
                    aria-label={`Remove ${r}`}
                  >
                    <Trash2 className="size-4" />
                  </button>
                </li>
              ))}
            </ul>

            <Button
              variant="secondary"
              size="sm"
              className="mt-4"
              disabled={sendNow.isPending || recipients.length === 0}
              onClick={() => sendNow.mutate()}
              data-testid="send-digest-now-button"
            >
              <Send className="size-4" /> Send latest briefing now
            </Button>
          </section>
          )}

          {/* Watchlist terms */}
          {canEdit && (
          <section className="rounded-md border border-border bg-card p-5" data-testid="watchlist-panel">
            <h3 className="flex items-center gap-2 font-heading text-lg font-bold">
              <Eye className="size-4 text-accent" /> Watchlist
            </h3>
            <p className="mt-1 text-sm text-muted-foreground">
              Topics, counties, or names to track. Any edition whose stories mention a term shows a
              highlighted alert at the top.
            </p>
            <form
              className="mt-4 flex gap-2"
              onSubmit={(e) => {
                e.preventDefault();
                if (term.trim()) addTerm.mutate(term.trim());
              }}
            >
              <Input
                placeholder="e.g. consolidation, McDowell County, AI"
                value={term}
                onChange={(e) => setTerm(e.target.value)}
                data-testid="watch-term-input"
              />
              <Button type="submit" disabled={addTerm.isPending} data-testid="add-watch-term-button">
                Add
              </Button>
            </form>

            <div className="mt-4 flex flex-wrap gap-2" data-testid="watch-terms-list">
              {terms.length === 0 && (
                <span className="text-sm text-muted-foreground">No watch terms yet.</span>
              )}
              {terms.map((t) => (
                <Badge
                  key={t}
                  variant="outline"
                  className="gap-1.5 py-1"
                  data-testid={`watch-term-${t}`}
                >
                  {t}
                  <button
                    onClick={() => removeTerm.mutate(t)}
                    className="text-muted-foreground transition-colors hover:text-destructive"
                    aria-label={`Remove ${t}`}
                  >
                    <Trash2 className="size-3" />
                  </button>
                </Badge>
              ))}
            </div>
          </section>
          )}
        </div>
      )}
    </DeskLayout>
  );
}
