import { useEffect, useRef } from "react";

// Loads the Cloudflare Turnstile script once and explicitly renders a widget (recommended for
// SPAs). Reports the token up via onToken; clears it on expiry/error so a fresh token is required.
type Props = {
  siteKey: string;
  onToken: (token: string | null) => void;
};

let scriptPromise: Promise<void> | undefined;

function loadTurnstileOnce(): Promise<void> {
  if (window.turnstile) return Promise.resolve();
  if (scriptPromise) return scriptPromise;
  scriptPromise = new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";
    script.async = true;
    script.defer = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("Turnstile script failed to load"));
    document.head.appendChild(script);
  });
  return scriptPromise;
}

export default function TurnstileWidget({ siteKey, onToken }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const widgetIdRef = useRef<string | undefined>(undefined);

  useEffect(() => {
    let cancelled = false;
    loadTurnstileOnce()
      .then(() => new Promise<void>((resolve) => window.turnstile!.ready(() => resolve())))
      .then(() => {
        if (cancelled || !containerRef.current || !window.turnstile) return;
        widgetIdRef.current = window.turnstile.render(containerRef.current, {
          sitekey: siteKey,
          action: "submit-story",
          theme: "auto",
          callback: (token) => onToken(token),
          "error-callback": () => onToken(null),
          "expired-callback": () => {
            onToken(null);
            if (widgetIdRef.current) window.turnstile!.reset(widgetIdRef.current);
          },
          "timeout-callback": () => onToken(null),
        });
      })
      .catch(() => onToken(null));

    return () => {
      cancelled = true;
      if (widgetIdRef.current && window.turnstile) {
        window.turnstile.remove(widgetIdRef.current);
        widgetIdRef.current = undefined;
      }
    };
  }, [siteKey, onToken]);

  return <div ref={containerRef} data-testid="turnstile-widget" className="min-h-[65px]" />;
}
