import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, AUTH_EXPIRED_EVENT, ApiError, User } from "./api";

const TOKEN_KEY = "synqra_token";
const USER_KEY = "synqra_user";

// Google Sign-In (required — VITE_GOOGLE_CLIENT_ID must be set).
export const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID || "";

interface AuthContextValue {
  user: User | null;
  token: string | null;
  loading: boolean;
  loginGoogle: (idToken: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  token: null,
  loading: true,
  loginGoogle: async () => {},
  logout: async () => {},
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(TOKEN_KEY));
  const [user, setUser] = useState<User | null>(() => {
    try {
      return JSON.parse(localStorage.getItem(USER_KEY) || "null");
    } catch {
      return null;
    }
  });
  const [loading, setLoading] = useState(true);

  const clearSession = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    setToken(null);
    setUser(null);
  }, []);

  useEffect(() => {
    // Validate the stored session on mount. Only a 401 (expired token) clears
    // it — a transient network failure must NOT log the user out.
    let active = true;
    (async () => {
      const t = localStorage.getItem(TOKEN_KEY);
      if (t) {
        try {
          const me = await api.me(t);
          if (active) {
            setUser(me);
            setToken(t);
          }
        } catch (e) {
          if (e instanceof ApiError && e.status === 401) {
            if (active) clearSession();
          }
          // else: leave the session alone; it may be a temporary outage.
        }
      }
      if (active) setLoading(false);
    })();
    return () => {
      active = false;
    };
  }, [clearSession]);

  useEffect(() => {
    // Any API call that comes back 401 mid-session signs the user out.
    const onExpired = () => clearSession();
    window.addEventListener(AUTH_EXPIRED_EVENT, onExpired);
    return () => window.removeEventListener(AUTH_EXPIRED_EVENT, onExpired);
  }, [clearSession]);

  const persist = useCallback((t: string, u: User) => {
    localStorage.setItem(TOKEN_KEY, t);
    localStorage.setItem(USER_KEY, JSON.stringify(u));
    setToken(t);
    setUser(u);
  }, []);

  const loginGoogle = useCallback(
    async (idToken: string) => {
      const res = await api.loginGoogle(idToken);
      persist(res.token, res.user);
    },
    [persist]
  );

  const logout = useCallback(async () => {
    const t = localStorage.getItem(TOKEN_KEY);
    if (t) {
      try {
        await api.logout(t);
      } catch {
        /* ignore */
      }
    }
    clearSession();
  }, [clearSession]);

  const value = useMemo(
    () => ({ user, token, loading, loginGoogle, logout }),
    [user, token, loading, loginGoogle, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
