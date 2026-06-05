import React, { createContext, useContext, useState, useEffect } from 'react';

interface AuthContextType {
  token: string | null;
  isAuthenticated: boolean;
  login: (token: string) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const TOKEN_KEY = 'iosef_auth_token';

// Safari-safe token storage: localStorage persists across tabs and navigations.
// sessionStorage was causing 401s in Safari due to aggressive per-tab isolation.
const storage = {
  get: (): string | null => {
    try { return localStorage.getItem(TOKEN_KEY); }
    catch { return null; }
  },
  set: (token: string) => {
    try { localStorage.setItem(TOKEN_KEY, token); }
    catch { /* private browsing / storage full */ }
  },
  remove: () => {
    try { localStorage.removeItem(TOKEN_KEY); }
    catch { /* ignore */ }
  },
};

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  // Initialize synchronously from storage — avoids the "flash → redirect" Safari race
  const [token, setToken] = useState<string | null>(() => storage.get());

  // Keep storage in sync whenever token changes
  useEffect(() => {
    if (token) {
      storage.set(token);
    } else {
      storage.remove();
    }
  }, [token]);

  const login = (newToken: string) => {
    storage.set(newToken);   // write immediately (Safari guard)
    setToken(newToken);
  };

  const logout = () => {
    storage.remove();
    setToken(null);
  };

  return (
    <AuthContext.Provider value={{ token, isAuthenticated: !!token, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

