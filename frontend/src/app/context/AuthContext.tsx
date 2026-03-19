import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import {
  type ApiUser,
  authApi,
  clearToken,
  getApiErrorMessage,
  getToken,
  setToken,
  type AuthRegisterPayload,
} from "../lib/api";

interface AuthContextValue {
  user: ApiUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (username: string, password: string, role?: ApiUser["role"]) => Promise<ApiUser>;
  register: (payload: AuthRegisterPayload) => Promise<ApiUser>;
  refreshMe: () => Promise<ApiUser | null>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<ApiUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const refreshMe = useCallback(async (): Promise<ApiUser | null> => {
    const token = getToken();
    if (!token) {
      setUser(null);
      return null;
    }

    try {
      const me = await authApi.getMe();
      setUser(me);
      return me;
    } catch {
      clearToken();
      setUser(null);
      return null;
    }
  }, []);

  useEffect(() => {
    let mounted = true;

    async function bootstrap() {
      if (!getToken()) {
        if (mounted) {
          setIsLoading(false);
        }
        return;
      }

      await refreshMe();
      if (mounted) {
        setIsLoading(false);
      }
    }

    bootstrap();

    return () => {
      mounted = false;
    };
  }, [refreshMe]);

  useEffect(() => {
    const handleAuthInvalid = () => {
      setUser(null);
    };

    window.addEventListener("cdas-auth-invalid", handleAuthInvalid);
    return () => {
      window.removeEventListener("cdas-auth-invalid", handleAuthInvalid);
    };
  }, []);

  const login = useCallback(async (username: string, password: string, role?: ApiUser["role"]): Promise<ApiUser> => {
    const tokenResp = await authApi.login(username, password, role);
    setToken(tokenResp.access_token);

    const me = await authApi.getMe();
    setUser(me);
    return me;
  }, []);

  const register = useCallback(
    async (payload: AuthRegisterPayload): Promise<ApiUser> => {
      await authApi.register(payload);
      try {
        return await login(payload.username, payload.password, payload.role);
      } catch (error) {
        throw new Error(getApiErrorMessage(error, "注册成功，但自动登录失败，请手动登录"));
      }
    },
    [login],
  );

  const logout = useCallback(() => {
    clearToken();
    setUser(null);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      isAuthenticated: Boolean(user),
      isLoading,
      login,
      register,
      refreshMe,
      logout,
    }),
    [user, isLoading, login, register, refreshMe, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used inside AuthProvider");
  }
  return context;
}
