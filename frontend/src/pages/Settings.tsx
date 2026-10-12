import { useState, useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Mail, Eye, Trash2, Send, Gauge, ShieldCheck, Timer, KeyRound, Users, Link2, Code2, Copy, CalendarClock, History, Megaphone, FlaskConical, RotateCcw, Database, Download, Upload, AlertTriangle, Search, Loader2 } from "lucide-react";
import DeskLayout from "@/components/DeskLayout";
import IntegrationsPanel from "@/components/IntegrationsPanel";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { apiGet, apiPost, apiDelete, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/useAuth";
import type { AuthState, DeskConfig, DigestSendResult, RunLogEntry, Subscriber, ExportArchive, ImportResult, ImportPreview } from "@/lib/types";

const DOW = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const pad = (n: number) => String(n).padStart(2, "0");
const TZ_OPTIONS = [
  "America/New_York",
  "America/Chicago",
  "America/Denver",
  "America/Phoenix",
  "America/Los_Angeles",
  "America/Anchorage",
  "Pacific/Honolulu",
  "America/Puerto_Rico",
  "UTC",
  "Europe/London",
  "Europe/Paris",
  "Asia/Kolkata",
  "Asia/Tokyo",
  "Australia/Sydney",
];

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
  const [dailyTime, setDailyTime] = useState("22:00");
  const [weeklyDow, setWeeklyDow] = useState(4);
  const [weeklyTime, setWeeklyTime] = useState("16:00");
  const [tz, setTz] = useState("America/New_York");
  const [supportText, setSupportText] = useState("");
  const [supportOn, setSupportOn] = useState(true);
  const [testEmail, setTestEmail] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["config"],
    queryFn: () => apiGet<DeskConfig>("/settings"),
  });

  const { data: auth } = useQuery({
    queryKey: ["auth", "me"],
    queryFn: () => apiGet<AuthState>("/auth/me"),
    staleTime: 5 * 60 * 1000,
  });
  const isAdmin = auth?.user?.role === "admin";

  // --- Source links: hide-unverified toggle + all-briefings re-check (admin-only) ---
  const [recheckResult, setRecheckResult] = useState<{ briefings: number; episodes: number; links_checked: number; unverified: number } | null>(null);
  const [purgeArmed, setPurgeArmed] = useState(false);
  const [purgeResult, setPurgeResult] = useState<{ removed: number; briefings: number; episodes: number } | null>(null);

  const toggleHideUnverified = useMutation({
    mutationFn: (enabled: boolean) => apiPost<DeskConfig>("/settings/hide-unverified", { enabled }),
    onSuccess: (cfg) => {
      qc.setQueryData(["config"], cfg);
      toast.success(cfg.hide_unverified_sources ? "Unverified links are now hidden." : "Unverified links are shown.");
    },
    onError: (e) => toast.error(errMsg(e)),
  });

  const recheckSources = useMutation({
    mutationFn: () => apiPost<{ briefings: number; episodes: number; links_checked: number; unverified: number }>("/briefings/recheck-sources"),
    onSuccess: (r) => {
      setRecheckResult(r);
      qc.invalidateQueries({ queryKey: ["briefing"] });
      qc.invalidateQueries({ queryKey: ["briefings"] });
      qc.invalidateQueries({ queryKey: ["episode"] });
      qc.invalidateQueries({ queryKey: ["unverified-count"] });
      toast.success(`Re-checked ${r.links_checked} link(s) across ${r.briefings} briefing(s) + ${r.episodes} episode(s).`);
    },
    onError: (e) => toast.error(errMsg(e)),
  });

  const purgeUnverified = useMutation({
    mutationFn: () => apiPost<{ removed: number; briefings: number; episodes: number }>("/briefings/purge-unverified"),
    onSuccess: (r) => {
      setPurgeResult(r);
      setPurgeArmed(false);
      qc.invalidateQueries({ queryKey: ["briefing"] });
      qc.invalidateQueries({ queryKey: ["briefings"] });
      qc.invalidateQueries({ queryKey: ["episode"] });
      qc.invalidateQueries({ queryKey: ["unverified-count"] });
      toast.success(`Removed ${r.removed} unverified link(s).`);
    },
    onError: (e) => {
      setPurgeArmed(false);
      toast.error(errMsg(e));
    },
  });

  // --- Data export & import (admin-only) ---
  const [exportCounts, setExportCounts] = useState<Record<string, number> | null>(null);
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importMode, setImportMode] = useState<"merge" | "replace">("merge");
  const [replaceArmed, setReplaceArmed] = useState(false);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);
  const [importPreview, setImportPreview] = useState<ImportPreview | null>(null);

  const exportData = useMutation({
    mutationFn: () => apiGet<ExportArchive>("/data/export"),
    onSuccess: (archive) => {
      const blob = new Blob([JSON.stringify(archive, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      const date = (archive.exported_at || new Date().toISOString()).slice(0, 10);
      a.href = url;
      a.download = `wvedtalk-news-desk-${date}.json`;
      a.click();
      URL.revokeObjectURL(url);
      setExportCounts(archive.counts);
      const total = Object.values(archive.counts).reduce((a2, b) => a2 + b, 0);
      toast.success(`Downloaded a full copy — ${total} records across ${Object.keys(archive.counts).length} collections.`);
    },
    onError: (e) => toast.error(errMsg(e)),
  });

  const importData = useMutation({
    mutationFn: (vars: { archive: unknown; mode: string; confirm: boolean }) =>
      apiPost<ImportResult>("/data/import", vars),
    onSuccess: (res) => {
      setImportResult(res);
      setReplaceArmed(false);
      qc.invalidateQueries();
      const loaded = Object.values(res.results).reduce((a2, b) => a2 + b.loaded, 0);
      toast.success(`Loaded ${loaded} records into this instance (${res.mode}).`);
    },
    onError: (e) => {
      setReplaceArmed(false);
      toast.error(errMsg(e));
    },
  });

  const runImport = async () => {
    if (!importFile) {
      toast.error("Choose an export file first.");
      return;
    }
    let archive: unknown;
    try {
      archive = JSON.parse(await importFile.text());
    } catch {
      toast.error("That file isn't valid JSON.");
      return;
    }
    if (importMode === "replace" && !replaceArmed) {
      setReplaceArmed(true);
      return;
    }
    importData.mutate({ archive, mode: importMode, confirm: importMode === "replace" });
  };

  const previewImport = useMutation({
    mutationFn: (vars: { archive: unknown; mode: string }) =>
      apiPost<ImportPreview>("/data/import/preview", vars),
    onSuccess: (res) => setImportPreview(res),
    onError: (e) => toast.error(errMsg(e)),
  });

  const runPreview = async () => {
    if (!importFile) {
      toast.error("Choose an export file first.");
      return;
    }
    let archive: unknown;
    try {
      archive = JSON.parse(await importFile.text());
    } catch {
      toast.error("That file isn't valid JSON.");
      return;
    }
    previewImport.mutate({ archive, mode: importMode });
  };

  const { data: runLog } = useQuery({
    queryKey: ["run-log"],
    queryFn: () => apiGet<RunLogEntry[]>("/run-log"),
    refetchInterval: 60000,
  });

  useEffect(() => {
    if (data) {
      setDailyTime(`${pad(data.daily_hour)}:${pad(data.daily_minute)}`);
      setWeeklyDow(data.weekly_dow);
      setWeeklyTime(`${pad(data.weekly_hour)}:${pad(data.weekly_minute)}`);
      setTz(data.timezone);
      setSupportText(data.support_segment);
      setSupportOn(data.support_default_on);
    }
  }, [data]);

  const { data: subscribers } = useQuery({
    queryKey: ["subscribers"],
    queryFn: () => apiGet<Subscriber[]>("/subscribers"),
    refetchInterval: 30000,
    refetchOnWindowFocus: true,
  });
  const activeSubscribers = subscribers?.filter((s) => s.active).length ?? 0;

  const removeSubscriber = useMutation({
    mutationFn: (e: string) => apiDelete<{ ok: boolean }>(`/subscribers/${encodeURIComponent(e)}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["subscribers"] });
      toast.success("Subscriber removed");
    },
    onError: (e) => toast.error(errMsg(e)),
  });

  const copySignupLink = () => {
    navigator.clipboard.writeText(`${window.location.origin}/subscribe`);
    toast.success("Public signup link copied");
  };

  const embedOrigin = typeof window !== "undefined" ? window.location.origin : "";
  const embedCode = `<!-- WVEdTalk News Desk signup -->
<div style="max-width:420px;font-family:Arial,Helvetica,sans-serif">
  <form onsubmit="var e=this.email.value;var s=this.querySelector('.wvedtalk-msg');fetch('${embedOrigin}/api/public/embed-subscribe',{method:'POST',mode:'no-cors',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:'email='+encodeURIComponent(e)});s.textContent='Thanks! You are subscribed to the WVEdTalk daily briefing.';this.reset();return false;">
    <div style="display:flex;gap:8px;flex-wrap:wrap">
      <input name="email" type="email" required placeholder="you@example.com" style="flex:1;min-width:200px;padding:10px 12px;border:1px solid #ccc;border-radius:6px;font-size:14px" />
      <button type="submit" style="background:#16305e;color:#fff;border:0;border-radius:6px;padding:10px 18px;font-size:14px;font-weight:bold;cursor:pointer">Subscribe</button>
    </div>
    <p class="wvedtalk-msg" style="margin:8px 0 0;font-size:13px;color:#16305e"></p>
  </form>
  <p style="margin:6px 0 0;font-size:11px;color:#8a8a8a">Powered by WVEdTalk News Desk</p>
</div>`;

  const copyEmbed = () => {
    navigator.clipboard.writeText(embedCode);
    toast.success("Embed code copied");
  };

  const submitEmbedCode = `<!-- WVEdTalk News Desk story submission -->
<div style="max-width:420px;font-family:Arial,Helvetica,sans-serif">
  <form onsubmit="var f=this;var s=f.querySelector('.wvedtalk-msg');fetch('${embedOrigin}/api/public/embed-submit-story',{method:'POST',mode:'no-cors',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:'url='+encodeURIComponent(f.url.value)+'&name='+encodeURIComponent(f.pname.value)+'&email='+encodeURIComponent(f.email.value)+'&website='+encodeURIComponent(f.website.value)});s.textContent='Thanks! Your story has been submitted for the desk to consider.';f.reset();return false;">
    <input name="url" type="url" required placeholder="Link to the story" style="width:100%;box-sizing:border-box;padding:10px 12px;border:1px solid #ccc;border-radius:6px;font-size:14px;margin-bottom:8px" />
    <input name="pname" type="text" required placeholder="Your name" style="width:100%;box-sizing:border-box;padding:10px 12px;border:1px solid #ccc;border-radius:6px;font-size:14px;margin-bottom:8px" />
    <input name="email" type="email" required placeholder="you@example.com" style="width:100%;box-sizing:border-box;padding:10px 12px;border:1px solid #ccc;border-radius:6px;font-size:14px;margin-bottom:8px" />
    <input name="website" type="text" tabindex="-1" autocomplete="off" aria-hidden="true" style="position:absolute;left:-9999px;height:0;width:0;opacity:0" />
    <button type="submit" style="background:#16305e;color:#fff;border:0;border-radius:6px;padding:10px 18px;font-size:14px;font-weight:bold;cursor:pointer">Submit story</button>
    <p class="wvedtalk-msg" style="margin:8px 0 0;font-size:13px;color:#16305e"></p>
  </form>
  <p style="margin:6px 0 0;font-size:11px;color:#8a8a8a">Powered by WVEdTalk News Desk</p>
</div>`;

  const copySubmitEmbed = () => {
    navigator.clipboard.writeText(submitEmbedCode);
    toast.success("Submit-form embed code copied");
  };

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
    mutationFn: () => apiPost<DigestSendResult>("/settings/send-digest"),
    onSuccess: (r) => {
      const total = r.admin_sent + r.sub_sent;
      const failed = r.admin_failed + r.sub_failed;
      if (failed > 0) {
        const first = r.failures[0];
        toast.warning(
          `Sent to ${total}; ${failed} failed${first ? ` — ${first.email}: ${first.error}` : ""}`,
        );
      } else {
        toast.success(`Digest sent to ${total} recipient${total === 1 ? "" : "s"}`);
      }
    },
    onError: (e) => toast.error(errMsg(e)),
  });

  const sendTest = useMutation({
    mutationFn: (e: string) =>
      apiPost<{ ok: boolean; email: string; error: string | null }>("/settings/test-digest", {
        email: e,
      }),
    onSuccess: (r) => {
      if (r.ok) toast.success(`Test briefing sent to ${r.email}`);
      else toast.error(`Test send failed: ${r.error}`);
    },
    onError: (e) => toast.error(errMsg(e)),
  });

  const resendMissed = useMutation({
    mutationFn: () => apiPost<DigestSendResult>("/settings/resend-digest"),
    onSuccess: (r) => {
      if (r.sub_sent === 0 && r.sub_failed === 0) {
        toast.info("Everyone already received the latest briefing.");
      } else if (r.sub_failed > 0) {
        const first = r.failures[0];
        toast.warning(
          `Resent to ${r.sub_sent}; ${r.sub_failed} still failing${first ? ` (${first.error})` : ""}`,
        );
      } else {
        toast.success(`Resent to ${r.sub_sent} subscriber${r.sub_sent === 1 ? "" : "s"} who missed it`);
      }
    },
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

  const saveSupport = useMutation({
    mutationFn: () => apiPost<DeskConfig>("/settings/support", { segment: supportText, default_on: supportOn }),
    onSuccess: (cfg) => {
      invalidate(cfg);
      toast.success("Support read saved");
    },
    onError: (e) => toast.error(errMsg(e)),
  });

  const saveSchedule = useMutation({
    mutationFn: () => {
      const [dh, dm] = dailyTime.split(":").map(Number);
      const [wh, wm] = weeklyTime.split(":").map(Number);
      return apiPost<DeskConfig>("/settings/schedule", {
        timezone: tz,
        daily_hour: dh,
        daily_minute: dm,
        weekly_dow: weeklyDow,
        weekly_hour: wh,
        weekly_minute: wm,
      });
    },
    onSuccess: (cfg) => {
      invalidate(cfg);
      qc.invalidateQueries({ queryKey: ["schedule-next"] });
      toast.success("Schedule updated");
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
        <IntegrationsPanel />
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

          {/* Automatic run schedule (admin only) */}
          {isAdmin && (
          <section
            className="rounded-md border border-border bg-card p-5 md:col-span-2"
            data-testid="schedule-panel"
          >
            <h3 className="flex items-center gap-2 font-heading text-lg font-bold">
              <CalendarClock className="size-4 text-primary" /> Automatic run schedule
            </h3>
            <p className="mt-1 text-sm text-muted-foreground">
              When the desk runs on its own, in the home timezone you choose below. The header shows
              the next run converted to your browser's local time.
            </p>
            <div className="mt-4 grid gap-6 md:grid-cols-2">
              <div>
                <label htmlFor="daily-time" className="text-sm font-semibold">
                  Daily briefing
                </label>
                <p className="mt-1 text-xs text-muted-foreground">Runs every day at this time.</p>
                <input
                  id="daily-time"
                  type="time"
                  value={dailyTime}
                  onChange={(e) => setDailyTime(e.target.value)}
                  className="mt-2 rounded-sm border border-border bg-background px-3 py-2 text-sm"
                  data-testid="daily-time-input"
                />
              </div>
              <div>
                <span className="text-sm font-semibold">Weekly script</span>
                <p className="mt-1 text-xs text-muted-foreground">
                  Runs once a week on this day and time.
                </p>
                <div className="mt-2 flex flex-wrap gap-2">
                  <select
                    value={weeklyDow}
                    onChange={(e) => setWeeklyDow(Number(e.target.value))}
                    className="rounded-sm border border-border bg-background px-3 py-2 text-sm"
                    data-testid="weekly-dow-select"
                    aria-label="Weekly run day"
                  >
                    {DOW.map((d, i) => (
                      <option key={d} value={i}>
                        {d}
                      </option>
                    ))}
                  </select>
                  <input
                    type="time"
                    value={weeklyTime}
                    onChange={(e) => setWeeklyTime(e.target.value)}
                    className="rounded-sm border border-border bg-background px-3 py-2 text-sm"
                    data-testid="weekly-time-input"
                    aria-label="Weekly run time"
                  />
                </div>
              </div>
            </div>
            <div className="mt-5">
              <label htmlFor="tz-select" className="text-sm font-semibold">
                Home timezone
              </label>
              <p className="mt-1 text-xs text-muted-foreground">
                All run times above are interpreted in this timezone (DST handled automatically). The
                header shows the next run converted to your browser's local time.
              </p>
              <select
                id="tz-select"
                value={tz}
                onChange={(e) => setTz(e.target.value)}
                className="mt-2 rounded-sm border border-border bg-background px-3 py-2 text-sm"
                data-testid="timezone-select"
              >
                {[...new Set([tz, ...TZ_OPTIONS])].map((z) => (
                  <option key={z} value={z}>
                    {z.replace(/_/g, " ")}
                  </option>
                ))}
              </select>
            </div>
            <Button
              size="sm"
              className="mt-4"
              disabled={saveSchedule.isPending}
              onClick={() => saveSchedule.mutate()}
              data-testid="save-schedule-button"
            >
              Save schedule
            </Button>
          </section>
          )}

          {/* Recent automatic runs — visible to all signed-in users */}
          {canEdit && (
          <section className="rounded-md border border-border bg-card p-5 md:col-span-2" data-testid="support-panel">
            <h3 className="flex items-center gap-2 font-heading text-lg font-bold">
              <Megaphone className="size-4 text-primary" /> Weekly support read (Value 4 Value)
            </h3>
            <p className="mt-1 text-sm text-muted-foreground">
              Added as a "Support WVEdTalk" chapter just before the closing of each new weekly script.
              Edit the wording here — no code change needed. Existing episodes keep their current text;
              toggle a specific episode on its page.
            </p>
            <textarea
              value={supportText}
              onChange={(e) => setSupportText(e.target.value)}
              className="mt-3 h-52 w-full rounded-sm border border-border bg-background p-3 text-sm"
              data-testid="support-text"
            />
            <label className="mt-3 flex cursor-pointer items-center gap-2 text-sm" data-testid="support-default-toggle">
              <input
                type="checkbox"
                checked={supportOn}
                onChange={(e) => setSupportOn(e.target.checked)}
                className="size-4 cursor-pointer accent-primary"
              />
              Include the support read on newly produced episodes by default
            </label>
            <Button size="sm" className="mt-4" disabled={saveSupport.isPending} onClick={() => saveSupport.mutate()} data-testid="save-support-button">
              Save support read
            </Button>
          </section>
          )}

          <section
            className="rounded-md border border-border bg-card p-5 md:col-span-2"
            data-testid="run-history-panel"
          >
            <h3 className="flex items-center gap-2 font-heading text-lg font-bold">
              <History className="size-4 text-primary" /> Recent runs
            </h3>
            <p className="mt-1 text-sm text-muted-foreground">
              The last briefings and weekly scripts the desk produced — confirm the schedule is
              firing. Times are shown in your local timezone.
            </p>
            <ul className="mt-4 space-y-2" data-testid="run-log-list">
              {runLog && runLog.length > 0 ? (
                runLog.slice(0, 10).map((r) => (
                  <li
                    key={r.id}
                    className="flex flex-wrap items-center justify-between gap-2 rounded-sm border border-border bg-background px-3 py-2 text-sm"
                    data-testid={`run-log-${r.id}`}
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant={r.status === "complete" ? "secondary" : "destructive"}>
                        {r.status}
                      </Badge>
                      <span className="font-medium">
                        {r.kind === "daily" ? "Daily briefing" : "Weekly script"}
                      </span>
                      <span className="text-muted-foreground">{r.label}</span>
                      <Badge variant="outline">{r.trigger}</Badge>
                    </div>
                    <span
                      className="text-xs text-muted-foreground"
                      data-testid={`run-log-time-${r.id}`}
                    >
                      {new Date(r.finished_at).toLocaleString()}
                    </span>
                  </li>
                ))
              ) : (
                <li className="text-sm text-muted-foreground">
                  No runs recorded yet. They'll appear here after the next scheduled or manual run.
                </li>
              )}
            </ul>
          </section>

          {canEdit && (
          <section className="rounded-md border border-border bg-card p-5" data-testid="recipients-panel">
            <h3 className="flex items-center gap-2 font-heading text-lg font-bold">
              <Mail className="size-4 text-primary" /> Email digest
            </h3>
            <p className="mt-1 text-sm text-muted-foreground">
              The full briefing is emailed to everyone below the moment each 10:00 PM run finishes.
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
              disabled={sendNow.isPending || (recipients.length === 0 && activeSubscribers === 0)}
              onClick={() => sendNow.mutate()}
              data-testid="send-digest-now-button"
            >
              <Send className="size-4" /> Send latest briefing now
            </Button>

            <div className="mt-6 space-y-5 border-t border-border pt-4">
              {/* Send a test copy before distribution */}
              <div data-testid="test-digest-block">
                <p className="flex items-center gap-1.5 text-sm font-semibold">
                  <FlaskConical className="size-4 text-accent" /> Send a test copy
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Email yourself the exact subscriber briefing before it goes out. Shows the real
                  reason if delivery fails.
                </p>
                <form
                  className="mt-3 flex gap-2"
                  onSubmit={(e) => {
                    e.preventDefault();
                    if (testEmail.trim()) sendTest.mutate(testEmail.trim());
                  }}
                >
                  <Input
                    type="email"
                    placeholder="you@example.com"
                    value={testEmail}
                    onChange={(e) => setTestEmail(e.target.value)}
                    data-testid="test-digest-input"
                  />
                  <Button
                    type="submit"
                    variant="outline"
                    disabled={sendTest.isPending || !testEmail.trim()}
                    data-testid="send-test-digest-button"
                  >
                    <FlaskConical className="size-4" /> Send test
                  </Button>
                </form>
              </div>

              {/* Resend today's briefing to subscribers who missed it */}
              <div data-testid="resend-digest-block">
                <p className="flex items-center gap-1.5 text-sm font-semibold">
                  <RotateCcw className="size-4 text-accent" /> Resend today's briefing
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Re-sends the latest briefing only to subscribers who haven't received it yet —
                  safe to run after fixing bad addresses.
                </p>
                <Button
                  variant="outline"
                  size="sm"
                  className="mt-3"
                  disabled={resendMissed.isPending || activeSubscribers === 0}
                  onClick={() => resendMissed.mutate()}
                  data-testid="resend-digest-button"
                >
                  <RotateCcw className="size-4" /> Resend to subscribers who missed it
                </Button>
              </div>
            </div>
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

          {/* Public subscribers (self sign-up) — visible to all, managed by editors */}
          <section
            className="rounded-md border border-border bg-card p-5 md:col-span-2"
            data-testid="subscribers-panel"
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="flex items-center gap-2 font-heading text-lg font-bold">
                <Users className="size-4 text-primary" /> Public subscribers
                <Badge variant="secondary" data-testid="active-subscriber-count">
                  {activeSubscribers} active
                </Badge>
              </h3>
              {canEdit && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={copySignupLink}
                  data-testid="copy-signup-link-button"
                >
                  <Link2 className="size-4" /> Copy signup link
                </Button>
              )}
            </div>
            <p className="mt-1 text-sm text-muted-foreground">
              People who sign up on the public page also receive the daily briefing — each email is
              sent individually so addresses stay private, with a one-click unsubscribe link. The
              weekly WVEdTalk script stays internal; subscribers never receive it.
            </p>
            <ul className="mt-4 space-y-2" data-testid="subscribers-list">
              {subscribers && subscribers.length > 0 ? (
                subscribers.map((s) => (
                  <li
                    key={s.email}
                    className="flex items-center justify-between rounded-sm border border-border bg-background px-3 py-2 text-sm"
                    data-testid={`subscriber-${s.email}`}
                  >
                    <span className={s.active ? "" : "text-muted-foreground line-through"}>
                      {s.email}
                    </span>
                    <div className="flex items-center gap-2">
                      {!s.active && <Badge variant="outline">unsubscribed</Badge>}
                      {canEdit && (
                        <button
                          onClick={() => removeSubscriber.mutate(s.email)}
                          className="text-muted-foreground transition-colors hover:text-destructive"
                          data-testid={`remove-subscriber-${s.email}`}
                          aria-label={`Remove ${s.email}`}
                        >
                          <Trash2 className="size-4" />
                        </button>
                      )}
                    </div>
                  </li>
                ))
              ) : (
                <li className="text-sm text-muted-foreground">
                  No public subscribers yet. Share the signup link to get started.
                </li>
              )}
            </ul>
            {canEdit && (
              <div className="mt-6 border-t border-border pt-4" data-testid="embed-panel">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="flex items-center gap-1.5 text-sm font-semibold">
                    <Code2 className="size-4 text-primary" /> Embed the signup form on another site
                  </p>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={copyEmbed}
                    data-testid="copy-embed-code-button"
                  >
                    <Copy className="size-4" /> Copy embed code
                  </Button>
                </div>
                <p className="mt-1 text-xs text-muted-foreground">
                  Paste this HTML into any web page. Visitors who subscribe are added to your
                  subscribers list and receive the daily briefing — no account needed.
                </p>
                <textarea
                  readOnly
                  value={embedCode}
                  onFocus={(e) => e.currentTarget.select()}
                  className="mt-3 h-40 w-full rounded-sm border border-border bg-background p-3 font-mono text-xs"
                  data-testid="embed-code-textarea"
                />
                <p className="mt-3 text-xs tracking-[0.14em] text-accent uppercase">Live preview</p>
                <div
                  className="mt-2 rounded-sm border border-dashed border-border p-4"
                  data-testid="embed-preview"
                  dangerouslySetInnerHTML={{ __html: embedCode }}
                />
              </div>
            )}
            {canEdit && (
              <div className="mt-6 border-t border-border pt-4" data-testid="submit-embed-panel">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="flex items-center gap-1.5 text-sm font-semibold">
                    <Code2 className="size-4 text-primary" /> Embed the "Submit a story" form on another site
                  </p>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={copySubmitEmbed}
                    data-testid="copy-submit-embed-button"
                  >
                    <Copy className="size-4" /> Copy embed code
                  </Button>
                </div>
                <p className="mt-1 text-xs text-muted-foreground">
                  Paste this HTML into any web page. Readers who submit a story link are added to the
                  Submissions dashboard and subscribed to the daily briefing — no account needed. A hidden
                  honeypot blocks basic bots.
                </p>
                <textarea
                  readOnly
                  value={submitEmbedCode}
                  onFocus={(e) => e.currentTarget.select()}
                  className="mt-3 h-40 w-full rounded-sm border border-border bg-background p-3 font-mono text-xs"
                  data-testid="submit-embed-code-textarea"
                />
                <p className="mt-3 text-xs tracking-[0.14em] text-accent uppercase">Live preview</p>
                <div
                  className="mt-2 rounded-sm border border-dashed border-border p-4"
                  data-testid="submit-embed-preview"
                  dangerouslySetInnerHTML={{ __html: submitEmbedCode }}
                />
              </div>
            )}
          </section>

          {isAdmin && (
            <section
              className="rounded-md border border-border bg-card p-5 md:col-span-2"
              data-testid="source-links-panel"
            >
              <h3 className="flex items-center gap-2 font-heading text-lg font-bold">
                <Search className="size-5 text-primary" /> Source links
              </h3>
              <p className="mt-1 text-sm text-muted-foreground">
                Gemini sometimes writes plausible-looking but non-existent URLs. The desk resolves Google
                Search grounding links to their real publisher page and probes every other link; anything
                it can't confirm is flagged <span className="font-medium text-amber-600 dark:text-amber-400">Unverified</span>.
                Links pulled straight from Google Search show a <span className="font-medium text-emerald-600 dark:text-emerald-400">Grounded</span> badge.
              </p>

              <label className="mt-4 inline-flex cursor-pointer items-center gap-2 text-sm" data-testid="hide-unverified-toggle">
                <input
                  type="checkbox"
                  checked={!!data?.hide_unverified_sources}
                  onChange={(e) => toggleHideUnverified.mutate(e.target.checked)}
                  className="size-4 cursor-pointer accent-primary"
                />
                Hide unverified links from briefings &amp; episode notes
              </label>

              <div className="mt-4 border-t border-border pt-4">
                <p className="text-sm font-semibold">Re-check all past briefings</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Re-resolves and re-verifies every source link across all past editions in one pass. This
                  can take a moment if you have a long history.
                </p>
                <Button
                  className="mt-3"
                  variant="outline"
                  disabled={recheckSources.isPending}
                  onClick={() => recheckSources.mutate()}
                  data-testid="recheck-sources-button"
                >
                  {recheckSources.isPending ? <Loader2 className="size-4 animate-spin" /> : <Search className="size-4" />}
                  {recheckSources.isPending ? "Re-checking…" : "Re-check all source links"}
                </Button>
                {recheckResult && (
                  <p className="mt-3 text-xs text-muted-foreground" data-testid="recheck-result">
                    Checked {recheckResult.links_checked} link(s) across {recheckResult.briefings} briefing(s) and {recheckResult.episodes} episode(s) —{" "}
                    <span className={recheckResult.unverified > 0 ? "font-medium text-amber-600 dark:text-amber-400" : ""}>
                      {recheckResult.unverified} now unverified
                    </span>
                    .
                  </p>
                )}
              </div>

              <div className="mt-4 border-t border-border pt-4">
                <p className="text-sm font-semibold text-destructive">Remove unverified links</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Permanently deletes every link currently flagged unverified from all briefings and episodes.
                  This cannot be undone.
                </p>
                <Button
                  className="mt-3"
                  variant={purgeArmed ? "destructive" : "outline"}
                  disabled={purgeUnverified.isPending}
                  onClick={() => (purgeArmed ? purgeUnverified.mutate() : setPurgeArmed(true))}
                  data-testid="purge-unverified-button"
                >
                  {purgeUnverified.isPending ? <Loader2 className="size-4 animate-spin" /> : <Trash2 className="size-4" />}
                  {purgeUnverified.isPending
                    ? "Removing…"
                    : purgeArmed
                      ? "Confirm — permanently delete unverified links"
                      : "Remove unverified links"}
                </Button>
                {purgeResult && (
                  <p className="mt-3 text-xs text-muted-foreground" data-testid="purge-result">
                    Removed {purgeResult.removed} unverified link(s) across {purgeResult.briefings} briefing(s) and {purgeResult.episodes} episode(s).
                  </p>
                )}
              </div>
            </section>
          )}

          {isAdmin && (
            <section
              className="rounded-md border border-border bg-card p-5 md:col-span-2"
              data-testid="data-io-panel"
            >
              <h3 className="flex items-center gap-2 font-heading text-lg font-bold">
                <Database className="size-5 text-primary" /> Data export &amp; import
              </h3>
              <p className="mt-1 text-sm text-muted-foreground">
                Download a complete, portable copy of this News Desk's database — every briefing, episode,
                reader submission, subscriber, user account, setting, run-history and delivery record in one
                JSON file. Accounts are included with their hashed passwords, so everyone logs in unchanged
                after a move (plaintext passwords are never exported, and login sessions don't carry over —
                everyone signs in fresh). API keys and the session secret are configuration, not data, and
                are set up separately on the new server.
              </p>

              {/* Export */}
              <div className="mt-5 rounded-sm border border-border bg-background p-4" data-testid="export-block">
                <p className="flex items-center gap-1.5 text-sm font-semibold">
                  <Download className="size-4 text-primary" /> Download a full copy
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Run this while signed in to the live site to capture production data. The archive is a
                  point-in-time snapshot named with today's date.
                </p>
                <Button
                  className="mt-3"
                  disabled={exportData.isPending}
                  onClick={() => exportData.mutate()}
                  data-testid="export-download-button"
                >
                  <Download className="size-4" />
                  {exportData.isPending ? "Preparing…" : "Download a full copy"}
                </Button>
                {exportCounts && (
                  <div className="mt-3 text-xs text-muted-foreground" data-testid="export-counts">
                    Included:{" "}
                    {Object.entries(exportCounts)
                      .map(([k, v]) => `${v} ${k}`)
                      .join(" · ")}
                  </div>
                )}
              </div>

              {/* Import */}
              <div className="mt-4 rounded-sm border border-border bg-background p-4" data-testid="import-block">
                <p className="flex items-center gap-1.5 text-sm font-semibold">
                  <Upload className="size-4 text-primary" /> Load an archive into this instance
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Choose a file produced by the export above, pick how to load it, then load. Use this on your
                  self-hosted instance after signing in as an admin.
                </p>

                <input
                  type="file"
                  accept="application/json,.json"
                  onChange={(e) => {
                    setImportFile(e.target.files?.[0] ?? null);
                    setReplaceArmed(false);
                    setImportResult(null);
                    setImportPreview(null);
                  }}
                  className="mt-3 block w-full text-sm text-muted-foreground file:mr-3 file:rounded-sm file:border file:border-border file:bg-secondary file:px-3 file:py-1.5 file:text-sm file:font-medium hover:file:bg-muted"
                  data-testid="import-file-input"
                />

                <div className="mt-3 flex flex-col gap-2 text-sm">
                  <label className="inline-flex items-center gap-2">
                    <input
                      type="radio"
                      name="import-mode"
                      checked={importMode === "merge"}
                      onChange={() => {
                        setImportMode("merge");
                        setReplaceArmed(false);
                      }}
                      className="size-4 accent-primary"
                      data-testid="import-mode-merge"
                    />
                    <span>
                      <span className="font-medium">Merge</span>{" "}
                      <span className="text-muted-foreground">— add/replace records by id; keep anything already here.</span>
                    </span>
                  </label>
                  <label className="inline-flex items-center gap-2">
                    <input
                      type="radio"
                      name="import-mode"
                      checked={importMode === "replace"}
                      onChange={() => {
                        setImportMode("replace");
                        setReplaceArmed(false);
                      }}
                      className="size-4 accent-destructive"
                      data-testid="import-mode-replace"
                    />
                    <span>
                      <span className="font-medium text-destructive">Replace</span>{" "}
                      <span className="text-muted-foreground">— clear each collection first, then load an exact copy.</span>
                    </span>
                  </label>
                </div>

                {importMode === "replace" && (
                  <div
                    className="mt-3 flex items-start gap-2 rounded-sm border border-destructive/40 bg-destructive/5 p-3 text-xs text-destructive"
                    data-testid="replace-warning"
                  >
                    <AlertTriangle className="mt-0.5 size-4 shrink-0" />
                    <span>
                      Replace permanently erases the existing data in each collection before loading — this
                      cannot be undone, and it may sign you out if your own account changes.
                    </span>
                  </div>
                )}

                <div className="mt-3 flex flex-wrap gap-2">
                  <Button
                    variant="outline"
                    disabled={previewImport.isPending || !importFile}
                    onClick={runPreview}
                    data-testid="import-preview-button"
                  >
                    <Eye className="size-4" />
                    {previewImport.isPending ? "Checking…" : "Preview changes"}
                  </Button>
                  <Button
                    variant={importMode === "replace" && replaceArmed ? "destructive" : "default"}
                    disabled={importData.isPending || !importFile}
                    onClick={runImport}
                    data-testid="import-load-button"
                  >
                    <Upload className="size-4" />
                    {importData.isPending
                      ? "Loading…"
                      : importMode === "replace"
                        ? replaceArmed
                          ? "Confirm replace — erase and load"
                          : "Load archive (Replace)"
                        : "Load archive (Merge)"}
                  </Button>
                </div>

                {importPreview && (
                  <div className="mt-4 rounded-sm border border-dashed border-border p-3 text-xs" data-testid="import-preview">
                    <p className="flex items-center gap-1.5 font-semibold">
                      <Eye className="size-4 text-primary" /> Dry run — what loading would change ({importPreview.mode}). Nothing has been written yet.
                    </p>
                    <ul className="mt-2 space-y-0.5">
                      {Object.entries(importPreview.results).map(([name, r]) => (
                        <li key={name} className="flex justify-between gap-4" data-testid={`import-preview-${name}`}>
                          <span>{name}</span>
                          <span className="text-muted-foreground">
                            +{r.to_add} new
                            {r.to_update > 0 && `, ${r.to_update} updated`}
                            {r.to_delete > 0 && <span className="text-destructive">, {r.to_delete} deleted</span>} · {r.existing} → {r.resulting}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {importResult && (
                  <div className="mt-4 rounded-sm border border-border p-3 text-xs" data-testid="import-result">
                    <p
                      className={`flex items-center gap-1.5 font-semibold ${
                        importResult.integrity_ok ? "text-emerald-700 dark:text-emerald-400" : "text-destructive"
                      }`}
                      data-testid="import-integrity"
                    >
                      {importResult.integrity_ok ? (
                        <ShieldCheck className="size-4" />
                      ) : (
                        <AlertTriangle className="size-4" />
                      )}
                      {importResult.integrity_ok
                        ? `Integrity check passed — every collection matches (${importResult.mode}).`
                        : `Integrity check: ${
                            Object.values(importResult.results).filter((r) => !r.match).length
                          } collection(s) don't match — review below.`}
                    </p>
                    <ul className="mt-2 space-y-0.5">
                      {Object.entries(importResult.results).map(([name, r]) => (
                        <li key={name} className="flex justify-between gap-4" data-testid={`import-result-${name}`}>
                          <span className={r.match ? "" : "font-medium text-destructive"}>
                            {name}
                            {!r.match && " ⚠"}
                          </span>
                          <span className="text-muted-foreground">
                            {r.loaded} loaded
                            {r.failed > 0 && <span className="text-destructive"> · {r.failed} failed</span>} · now{" "}
                            <span className={r.match ? "" : "font-medium text-destructive"}>{r.actual}</span> in db / {r.in_archive} in file
                          </span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </section>
          )}
        </div>
      )}
    </DeskLayout>
  );
}
