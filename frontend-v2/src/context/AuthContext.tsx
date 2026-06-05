import React, { createContext, useContext, useState, useEffect } from 'react';

interface AuthContextType {
  token: string | null;
  isAuthenticated: boolean;
  login: (token: string) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [token, setToken] = useState<string | null>(null);
  const [isInitializing, setIsInitializing] = useState(true);

  useEffect(() => {
    // Luis (QA/Sec): Use sessionStorage instead of localStorage to mitigate XSS persistence.
    const storedToken = sessionStorage.getItem('iosef_auth_token');
    if (storedToken) {
      setToken(storedToken);
    }
    setIsInitializing(false);
  }, []);

  const login = (newToken: string) => {
    sessionStorage.setItem('iosef_auth_token', newToken);
    setToken(newToken);
  };

  const logout = () => {
    sessionStorage.removeItem('iosef_auth_token');
    setToken(null);
  };

  if (isInitializing) {
    return <div>Cargando...</div>;
  }

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
