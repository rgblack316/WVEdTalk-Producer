import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { CloudUpload, Download, Loader2, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiGet, apiPost, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/useAuth";
import type { BackupConfig, RemoteBackup } from "@/lib/types";

const errText = (e: unknown) =>
  e instanceof ApiError ? String((e.body as { detail?: string })?.detail ?? e.message) : String(e);

const DOW = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const INTERVALS = [1, 2, 3, 4, 6, 8, 12];
const pad = (n: number) => String(n).padStart(2, "0");
const selectCls = "h-9 w-full rounded-sm border border-border bg-background px-2 text-sm";

function Field({ label, children, hint }: { label: string; children: React.ReactNode; hint?: string }) {
  return (
    <label className="block space-y-1">
      <span className="text-xs tracking-wide text-muted-foreground uppercase">{label}</span>
      {children}
      {hint && <span className="block text-xs text-muted-foreground">{hint}</span>}
    </label>
  );
}

function fmtSize(n: number) {
  return n > 1048576 ? `${(n / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1024))} KB`;
}

// Admin-only: back up to any S3-compatible bucket. Schedule and retention are separate settings.
export default function BackupsPanel() {
  const { isAdmin } = useAuth();
  const { data, refetch } = useQuery({
    queryKey: ["backup-config"],
    queryFn: () => apiGet<BackupConfig>("/backups/config"),
    enabled: isAdmin,
  });
  const { data: remote, refetch: refetchList } = useQuery({
    queryKey: ["backup-list"],
    queryFn: () => apiGet<{ backups: RemoteBackup[]; error: string }>("/backups"),
    enabled: isAdmin && !!data?.configured,
  });
  const [f, setF] = useState<Record<string, string | number | boolean>>({});
  const [accessKey, setAccessKey] = useState("");
  const [secret, setSecret] = useState("");
  const [preset, setPreset] = useState("");
  const [busy, setBusy] = useState("");

  useEffect(() => {
    if (!data) return;
    setF({
      enabled: data.enabled, endpoint_url: data.endpoint_url, region: data.region, bucket: data.bucket,
      prefix: data.prefix, addressing_style: data.addressing_style, frequency: data.frequency,
      every_hours: data.every_hours, hour: data.hour, minute: data.minute, dow: data.dow,
      keep_last: data.keep_last, keep_days: data.keep_days,
    });
  }, [data]);

  if (!isAdmin || !data) return null;
  const set = (k: string, v: string | number | boolean) => setF((p) => ({ ...p, [k]: v }));
  const chosen = data.presets.find((p) => p.id === preset);

  const pickPreset = (id: string) => {
    setPreset(id);
    const p = data.presets.find((x) => x.id === id);
    if (p) setF((cur) => ({ ...cur, endpoint_url: p.endpoint, region: p.region, addressing_style: p.style }));
  };

  const run = async (name: string, fn: () => Promise<void>) => {
    setBusy(name);
    try {
      await fn();
    } catch (e) {
      toast.error(errText(e));
    } finally {
      setBusy("");
    }
  };

  const save = () =>
    run("save", async () => {
      const body: Record<string, unknown> = { ...f };
      if (accessKey.trim()) body.access_key_id = accessKey.trim();
      if (secret.trim()) body.secret_access_key = secret.trim();
      await apiPost("/backups/config", body);
      setAccessKey("");
      setSecret("");
      await refetch();
      await refetchList();
      toast.success("Backup settings saved");
    });

  const test = () =>
    run("test", async () => {
      const r = await apiPost<{ ok: boolean; message: string }>("/backups/test");
      r.ok ? toast.success(r.message) : toast.error(r.message);
    });

  const backupNow = () =>
    run("now", async () => {
      await apiPost("/backups/run");
      await refetch();
      await refetchList();
      toast.success("Backup uploaded");
    });

  const restore = (key: string, mode: "merge" | "replace") => {
    const msg =
      mode === "replace"
        ? "REPLACE all current data with this backup? Anything newer than the backup is lost. This cannot be undone."
        : "Merge this backup into the current data? Records in the backup overwrite matching records; nothing else is removed.";
    if (!window.confirm(msg)) return;
    run("restore", async () => {
      const r = await apiPost<{ integrity_ok: boolean }>("/backups/restore", { key, mode, confirm: mode === "replace" });
      r.integrity_ok ? toast.success("Backup restored") : toast.error("Restored with some mismatches — check the data");
    });
  };

  const kl = Number(f.keep_last ?? 0);
  const kd = Number(f.keep_days ?? 0);
  const plural = (n: number, w: string) => `${n} ${w}${n === 1 ? "" : "s"}`;
  const retention =
    kl === 0 && kd === 0
      ? "Keeping every backup forever (storage grows over time)."
      : kl > 0 && kd > 0
        ? `Keeps the newest ${plural(kl, "backup")} and also deletes any older than ${plural(kd, "day")} (whichever removes more). The newest backup is never deleted.`
        : kl > 0
          ? `Keeps the newest ${plural(kl, "backup")}; older ones are deleted. The newest backup is never deleted.`
          : `Deletes backups older than ${plural(kd, "day")}. The newest backup is never deleted.`;

  return (
    <section className="mt-8 rounded-md border border-border bg-card p-5" data-testid="backups-panel">
      <h3 className="flex items-center gap-2 font-heading text-lg font-bold">
        <CloudUpload className="size-4 text-primary" /> Backups to S3 storage
      </h3>
      <p className="mt-1 text-sm text-muted-foreground">
        Sends a full copy of the desk's data (including user accounts with hashed passwords) to a bucket on Amazon S3,
        Cloudflare R2, Backblaze B2, DigitalOcean Spaces, Wasabi, MinIO or any S3-compatible service.
        <span className="font-semibold text-foreground"> Use a private bucket.</span>
      </p>

      <h4 className="mt-5 font-heading text-base font-bold">Destination</h4>
      <div className="mt-2 grid gap-3 md:grid-cols-2">
        <Field label="Provider" hint={chosen?.hint}>
          <select className={selectCls} value={preset} onChange={(e) => pickPreset(e.target.value)}>
            <option value="">Choose to fill in typical settings…</option>
            {data.presets.map((p) => (
              <option key={p.id} value={p.id}>{p.label}</option>
            ))}
          </select>
        </Field>
        <Field label="Endpoint URL" hint="Blank for Amazon S3. Replace any <PLACEHOLDER> with your own value.">
          <Input value={String(f.endpoint_url ?? "")} onChange={(e) => set("endpoint_url", e.target.value)} placeholder="https://…" />
        </Field>
        <Field label="Region">
          <Input value={String(f.region ?? "")} onChange={(e) => set("region", e.target.value)} placeholder="us-east-1 (R2: auto)" />
        </Field>
        <Field label="Bucket name">
          <Input value={String(f.bucket ?? "")} onChange={(e) => set("bucket", e.target.value)} />
        </Field>
        <Field label="Folder in bucket" hint="Only files this app creates in this folder are ever listed or deleted.">
          <Input value={String(f.prefix ?? "")} onChange={(e) => set("prefix", e.target.value)} />
        </Field>
        <Field label="Addressing style" hint="Auto works for most. Path-style is needed by some (R2, MinIO, B2).">
          <select className={selectCls} value={String(f.addressing_style ?? "auto")} onChange={(e) => set("addressing_style", e.target.value)}>
            <option value="auto">Auto</option>
            <option value="path">Path</option>
            <option value="virtual">Virtual-hosted</option>
          </select>
        </Field>
        <Field label="Access key ID">
          <Input value={accessKey} onChange={(e) => setAccessKey(e.target.value)} autoComplete="off"
            placeholder={data.access_key_id_mask ? `Saved (${data.access_key_id_mask}) — leave blank to keep` : ""} />
        </Field>
        <Field label="Secret access key">
          <Input type="password" value={secret} onChange={(e) => setSecret(e.target.value)} autoComplete="new-password"
            placeholder={data.secret_access_key_set ? "Saved — leave blank to keep" : ""} />
        </Field>
      </div>

      <h4 className="mt-6 font-heading text-base font-bold">Schedule</h4>
      <label className="mt-2 flex cursor-pointer items-center gap-2 text-sm">
        <input type="checkbox" className="size-4 accent-primary" checked={!!f.enabled} onChange={(e) => set("enabled", e.target.checked)} />
        Run backups automatically
      </label>
      <div className="mt-2 grid gap-3 md:grid-cols-3">
        <Field label="How often">
          <select className={selectCls} value={String(f.frequency ?? "daily")} onChange={(e) => set("frequency", e.target.value)}>
            <option value="hours">Every few hours</option>
            <option value="daily">Daily</option>
            <option value="weekly">Weekly</option>
          </select>
        </Field>
        {f.frequency === "hours" && (
          <Field label="Every">
            <select className={selectCls} value={Number(f.every_hours)} onChange={(e) => set("every_hours", Number(e.target.value))}>
              {INTERVALS.map((n) => (
                <option key={n} value={n}>{n} hour{n === 1 ? "" : "s"}</option>
              ))}
            </select>
          </Field>
        )}
        {f.frequency === "weekly" && (
          <Field label="On">
            <select className={selectCls} value={Number(f.dow)} onChange={(e) => set("dow", Number(e.target.value))}>
              {DOW.map((d, i) => (
                <option key={d} value={i}>{d}</option>
              ))}
            </select>
          </Field>
        )}
        {f.frequency !== "hours" && (
          <Field label="At (desk timezone)">
            <Input type="time" value={`${pad(Number(f.hour ?? 2))}:${pad(Number(f.minute ?? 0))}`}
              onChange={(e) => {
                const [h, m] = e.target.value.split(":").map(Number);
                if (!Number.isNaN(h)) setF((p) => ({ ...p, hour: h, minute: m || 0 }));
              }} />
          </Field>
        )}
      </div>
      <p className="mt-2 text-xs text-muted-foreground">
        {data.enabled && data.configured && data.next_run
          ? `Next backup: ${new Date(data.next_run).toLocaleString()}`
          : "Automatic backups are off or not fully set up."}
        {" "}Uses the timezone set under the run schedule above.
      </p>

      <h4 className="mt-6 font-heading text-base font-bold">Retention</h4>
      <p className="text-xs text-muted-foreground">Independent of the schedule. Set either limit, both, or 0 for no limit.</p>
      <div className="mt-2 grid gap-3 md:grid-cols-2">
        <Field label="Keep the newest (backups)">
          <Input type="number" min={0} max={1000} value={String(f.keep_last ?? 0)} onChange={(e) => set("keep_last", Number(e.target.value))} />
        </Field>
        <Field label="Delete backups older than (days)">
          <Input type="number" min={0} max={3650} value={String(f.keep_days ?? 0)} onChange={(e) => set("keep_days", Number(e.target.value))} />
        </Field>
      </div>
      <p className="mt-2 text-sm">{retention}</p>

      <div className="mt-5 flex flex-wrap gap-2">
        <Button size="sm" disabled={!!busy} onClick={save} data-testid="backup-save">
          {busy === "save" && <Loader2 className="size-4 animate-spin" />} Save settings
        </Button>
        <Button size="sm" variant="outline" disabled={!!busy || !data.configured} onClick={test} data-testid="backup-test">
          {busy === "test" && <Loader2 className="size-4 animate-spin" />} Test connection
        </Button>
        <Button size="sm" variant="outline" disabled={!!busy || !data.configured} onClick={backupNow} data-testid="backup-now">
          {busy === "now" ? <Loader2 className="size-4 animate-spin" /> : <CloudUpload className="size-4" />} Back up now
        </Button>
      </div>
      <p className="mt-2 text-xs text-muted-foreground">Save first, then test. Keys are stored encrypted and never shown again.</p>

      {data.last && (
        <p className={`mt-4 text-sm ${data.last.status === "complete" && !data.last.error ? "" : "text-destructive"}`} data-testid="backup-last">
          Last backup ({data.last.trigger}) {new Date(data.last.at).toLocaleString()}:{" "}
          {data.last.status === "complete" ? `uploaded ${fmtSize(data.last.size)}` : "failed"}
          {data.last.pruned > 0 ? `, removed ${data.last.pruned} old` : ""}
          {data.last.error ? ` — ${data.last.error}` : ""}
        </p>
      )}

      {data.configured && (
        <div className="mt-4" data-testid="backup-list">
          <h4 className="font-heading text-base font-bold">Backups in the bucket</h4>
          {remote?.error && <p className="mt-1 text-sm text-destructive">{remote.error}</p>}
          {!remote?.error && (remote?.backups ?? []).length === 0 && (
            <p className="mt-1 text-sm text-muted-foreground">None yet.</p>
          )}
          <ul className="mt-2 divide-y divide-border text-sm">
            {(remote?.backups ?? []).map((b) => (
              <li key={b.key} className="flex flex-wrap items-center justify-between gap-2 py-2">
                <span>
                  {new Date(b.at).toLocaleString()} <span className="text-muted-foreground">· {fmtSize(b.size)}</span>
                </span>
                <span className="flex gap-2">
                  <a href={`/api/backups/download?key=${encodeURIComponent(b.key)}`} className="inline-flex items-center gap-1 rounded-sm border border-border px-2 py-1 text-xs hover:bg-secondary">
                    <Download className="size-3.5" /> Download
                  </a>
                  <Button size="sm" variant="outline" disabled={!!busy} onClick={() => restore(b.key, "merge")}>
                    <RotateCcw className="size-3.5" /> Restore (merge)
                  </Button>
                  <Button size="sm" variant="outline" disabled={!!busy} onClick={() => restore(b.key, "replace")}>
                    Replace all
                  </Button>
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
