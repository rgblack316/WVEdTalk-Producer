// Cloudflare Turnstile global (loaded via the explicit-render script).
declare global {
  interface Window {
    turnstile?: {
      ready(callback: () => void): void;
      render(
        container: HTMLElement | string,
        options: {
          sitekey: string;
          action?: string;
          theme?: "auto" | "light" | "dark";
          appearance?: "always" | "execute" | "interaction-only";
          callback?: (token: string) => void;
          "error-callback"?: (code?: string) => void;
          "expired-callback"?: () => void;
          "timeout-callback"?: () => void;
        },
      ): string;
      reset(widgetId?: string): void;
      remove(widgetId: string): void;
    };
  }
}

export {};
