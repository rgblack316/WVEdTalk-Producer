// Renders the recording script with chapter headers: any line formatted as "## Title"
// (emitted by the producer between story segments) becomes a styled chapter heading and
// doubles as a podcast chapter title. A quick chapter list is shown above the script.
export function ScriptView({ script, chapters }: { script: string; chapters?: string[] }) {
  const lines = (script || "").split("\n");
  return (
    <div>
      {chapters && chapters.length > 0 && (
        <div
          className="mb-4 rounded-md border border-border bg-secondary/40 p-4"
          data-testid="episode-chapters"
        >
          <p className="text-xs tracking-[0.14em] text-accent uppercase">Chapters</p>
          <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm">
            {chapters.map((c, i) => (
              <li key={`${c}-${i}`} data-testid={`chapter-${i}`}>
                {c}
              </li>
            ))}
          </ol>
        </div>
      )}
      <div className="rounded-md border border-border bg-card p-6 font-sans text-[15px] leading-7 text-foreground/90">
        {lines.map((ln, i) => {
          const h = ln.match(/^\s*##\s+(.+?)\s*$/);
          if (h) {
            return (
              <h4
                key={i}
                className="mt-6 mb-2 border-b border-border pb-1 font-heading text-lg font-bold text-primary first:mt-0"
                data-testid="script-chapter-heading"
              >
                {h[1]}
              </h4>
            );
          }
          if (!ln.trim()) return <div key={i} className="h-3" />;
          return (
            <p key={i} className="whitespace-pre-wrap">
              {ln}
            </p>
          );
        })}
      </div>
    </div>
  );
}
