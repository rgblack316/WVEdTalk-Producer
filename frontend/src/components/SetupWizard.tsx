import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Loader2, UserPlus, Upload, Lock } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiPost, ApiError } from "@/lib/api";
import { beginSession } from "@/lib/session";

// Shown by AuthGate on a brand-new install (empty users collection). Two mutually exclusive
// paths: create the first admin, or import an existing backup to complete a migration in one step.
export default function SetupWizard() {
  const qc = useQueryClient();
  const [mode, setMode] = useState<"admin" | "import">("admin");
  const [email, setEmail] = useState("");
  const [pw, setPw] = useState("");
  const [pw2, setPw2] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");

  const errText = (e: unknown) =>
    e instanceof ApiError ? String((e.body as { detail?: string })?.detail ?? e.message) : String(e);

  const createAdmin = async () => {
    setErr("");
    if (!email.trim()) return setErr("Enter an email or username.");
    if (pw.length < 8) return setErr("Password must be at least 8 characters.");
    if (pw !== pw2) return setErr("Passwords do not match.");
    setBusy(true);
    try {
      await apiPost("/setup/admin", { email: email.trim(), password: pw });
      await beginSession(qc);
      window.location.reload();
    } catch (e) {
      setErr(errText(e));
    } finally {
      setBusy(false);
    }
  };

  const importBackup = async (file?: File | null) => {
    if (!file) return;
    setErr("");
    setMsg("");
    setBusy(true);
    try {
      const archive = JSON.parse(await file.text());
      await apiPost("/setup/import", { archive });
      setMsg("Backup imported. Sign in with your existing credentials.");
      setTimeout(() => window.location.reload(), 1600);
    } catch (e) {
      setErr(e instanceof SyntaxError ? "That file isn't valid JSON." : errText(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-5 py-10" data-testid="setup-wizard">
      <div className="w-full max-w-md">
        <div className="mb-6 text-center">
          <img src="/wvedtalk-logo.png" alt="WVEdTalk News Desk" className="mx-auto w-full max-w-[280px]" />
          <p className="mt-3 text-sm text-muted-foreground">Welcome — let's set up your News Desk.</p>
        </div>

        <div className="mb-4 flex gap-1 rounded-md border border-border bg-secondary/40 p-1">
          <button
            type="button"
            onClick={() => setMode("admin")}
            data-testid="setup-tab-admin"
            className={`flex-1 rounded-sm px-3 py-1.5 text-sm transition-colors ${mode === "admin" ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground"}`}
          >
            Create admin
          </button>
          <button
            type="button"
            onClick={() => setMode("import")}
            data-testid="setup-tab-import"
            className={`flex-1 rounded-sm px-3 py-1.5 text-sm transition-colors ${mode === "import" ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground"}`}
          >
            Import a backup
          </button>
        </div>

        <div className="rounded-md border border-border bg-card p-6 shadow-sm">
          {mode === "admin" ? (
            <form
              className="space-y-3"
              onSubmit={(e) => {
                e.preventDefault();
                createAdmin();
              }}
            >
              <div className="flex items-center gap-2">
                <UserPlus className="size-4 text-primary" />
                <h2 className="font-heading text-lg font-bold">Create the first admin</h2>
              </div>
              <Input
                placeholder="Email or username"
                value={email}
                autoFocus
                onChange={(e) => setEmail(e.target.value)}
                data-testid="setup-email-input"
              />
              <Input
                type="password"
                placeholder="Password (min 8 characters)"
                value={pw}
                onChange={(e) => setPw(e.target.value)}
                data-testid="setup-password-input"
              />
              <Input
                type="password"
                placeholder="Confirm password"
                value={pw2}
                onChange={(e) => setPw2(e.target.value)}
                data-testid="setup-password2-input"
              />
              {err && <p className="text-sm text-destructive" data-testid="setup-error">{err}</p>}
              <Button type="submit" className="w-full" disabled={busy} data-testid="setup-create-submit">
                {busy ? <Loader2 className="size-4 animate-spin" /> : <Lock className="size-4" />}
                Create account & sign in
              </Button>
            </form>
          ) : (
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <Upload className="size-4 text-primary" />
                <h2 className="font-heading text-lg font-bold">Import an existing backup</h2>
              </div>
              <p className="text-sm text-muted-foreground">
                Upload a JSON export from another News Desk. Your accounts and data are restored and you
                sign in with your existing credentials.
              </p>
              <input
                type="file"
                accept="application/json,.json"
                disabled={busy}
                onChange={(e) => importBackup(e.target.files?.[0])}
                data-testid="setup-import-file"
                className="block w-full text-sm file:mr-3 file:rounded-sm file:border file:border-border file:bg-secondary file:px-3 file:py-1.5 file:text-sm"
              />
              {busy && (
                <p className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Loader2 className="size-4 animate-spin" /> Importing…
                </p>
              )}
              {msg && <p className="text-sm text-emerald-600 dark:text-emerald-400" data-testid="setup-import-ok">{msg}</p>}
              {err && <p className="text-sm text-destructive" data-testid="setup-error">{err}</p>}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
