import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api, type Me } from "./api";

type AuthState = { me: Me | null; loading: boolean };

const AuthContext = createContext<AuthState>({ me: null, loading: true });

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api<Me>("/api/v1/auth/me")
      .then(setMe)
      .catch(() => setMe(null))
      .finally(() => setLoading(false));
  }, []);

  return <AuthContext.Provider value={{ me, loading }}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  return useContext(AuthContext);
}
