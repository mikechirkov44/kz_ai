import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, type Me } from "./api";

type AuthState = {
  me: Me | null;
  loading: boolean;
  refreshMe: () => Promise<Me | null>;
};

const AuthContext = createContext<AuthState>({
  me: null,
  loading: true,
  refreshMe: async () => null,
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshMe = useCallback(async () => {
    try {
      const next = await api<Me>("/api/v1/auth/me");
      setMe(next);
      return next;
    } catch {
      setMe(null);
      return null;
    }
  }, []);

  useEffect(() => {
    refreshMe().finally(() => setLoading(false));
  }, [refreshMe]);

  return <AuthContext.Provider value={{ me, loading, refreshMe }}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  return useContext(AuthContext);
}
