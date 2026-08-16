import { useEffect, useRef, useState } from "react";
import { GOOGLE_CLIENT_ID, useAuth } from "../lib/auth";
import Brand from "./Brand";

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (cfg: { client_id: string; callback: (r: { credential: string }) => void }) => void;
          renderButton: (el: HTMLElement, cfg: Record<string, unknown>) => void;
        };
      };
    };
  }
}

export default function LoginScreen() {
  const { loginGoogle } = useAuth();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const gisRef = useRef<HTMLDivElement>(null);
  const googleReady = Boolean(GOOGLE_CLIENT_ID);

  // Load Google Identity Services (required — only when a client id is configured).
  useEffect(() => {
    if (!googleReady || !gisRef.current) return;
    let cancelled = false;
    const script = document.createElement("script");
    script.src = "https://accounts.google.com/gsi/client";
    script.async = true;
    script.onload = () => {
      if (cancelled || !gisRef.current || !window.google) return;
      window.google.accounts.id.initialize({
        client_id: GOOGLE_CLIENT_ID,
        callback: async (res) => {
          setBusy(true);
          try {
            await loginGoogle(res.credential);
          } catch (e: any) {
            setError(e?.message || "Google sign-in failed.");
          } finally {
            setBusy(false);
          }
        },
      });
      window.google.accounts.id.renderButton(gisRef.current, {
        theme: "filled_black",
        size: "large",
        width: 320,
        text: "signin_with",
      });
    };
    document.head.appendChild(script);
    return () => {
      cancelled = true;
      script.remove();
    };
  }, [googleReady, loginGoogle]);

  return (
    <div className="card mx-auto max-w-md overflow-hidden p-8 shadow-float">
      {/* header */}
      <div className="flex items-center justify-between">
        <Brand />
        <span className="chip border-signal/30 text-signal bg-signal/5">Sign in with Google</span>
      </div>

      <h1 className="mt-6 font-display text-2xl font-semibold text-busy">Sign in to your Schedule</h1>
      <p className="mt-1.5 text-sm text-mist">
        Connect with Google to access your calendar. Your events stay private — everything runs on this machine, scoped to your account.
      </p>

      {googleReady ? (
        <>
          <div className="mt-6 flex justify-center" ref={gisRef} />
        </>
      ) : (
        <div className="mt-6 rounded-lg border border-alert/40 bg-alert/10 px-4 py-3 text-sm text-alert">
          Google Sign-In is not configured. Please set VITE_GOOGLE_CLIENT_ID in your frontend .env file.
        </div>
      )}

      {error && <p className="mt-3 text-sm text-alert">{error}</p>}

      <div className="mt-6 rounded-lg border border-line bg-ink/50 p-4 text-xs text-mist">
        <div className="font-mono text-[10px] uppercase tracking-widest text-free">How it works</div>
        <ul className="mt-2 space-y-1">
          <li>· Sign in with your Google account</li>
          <li>· Grant calendar access to sync your events</li>
          <li>· Ask by text or voice — the agent reads & writes your calendar</li>
          <li>· All data stays on this server</li>
        </ul>
      </div>
    </div>
  );
}
