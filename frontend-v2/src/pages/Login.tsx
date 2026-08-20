import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Shield, Lock } from 'lucide-react';
import { apiFetchForm } from '../lib/api';

const LoginPage: React.FC = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError('');

    try {
      // Using standard OAuth2 form-urlencoded payload for FastAPI
      const formData = new URLSearchParams();
      formData.append('username', email);
      formData.append('password', password);

      await apiFetchForm('/auth/token', formData);
      login();
      navigate('/dashboard');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div style={styles.container}>
      <div style={styles.glassCard}>
        <div style={styles.logoContainer}>
          <Shield color="#D4AF37" size={48} />
          <h1 style={styles.title}>IOSEF <span style={styles.subtitle}>FINANCE</span></h1>
          <p style={styles.tagline}>Institutional Quantitative Terminal</p>
        </div>

        <form onSubmit={handleLogin} style={styles.form}>
          {error && <div style={styles.error}>{error}</div>}
          
          <div style={styles.inputGroup}>
            <label style={styles.label}>Email Corporativo</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              style={styles.input}
              placeholder="analista@fondo.com"
              required
            />
          </div>

          <div style={styles.inputGroup}>
            <label style={styles.label}>Contraseña</label>
            <div style={styles.passwordContainer}>
              <Lock color="#555" size={20} style={styles.icon} />
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                style={{...styles.input, paddingLeft: '40px'}}
                placeholder="••••••••"
                required
              />
            </div>
          </div>

          <button type="submit" style={styles.button} disabled={isLoading}>
            {isLoading ? 'Autenticando...' : 'Acceder al Terminal'}
          </button>
        </form>
      </div>
    </div>
  );
};

const styles: { [key: string]: React.CSSProperties } = {
  container: {
    minHeight: '100vh',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#0A0A0A',
    backgroundImage: 'radial-gradient(circle at 50% -20%, #1a1a2e 0%, #0A0A0A 80%)',
    fontFamily: '"Inter", "Roboto", sans-serif',
    color: '#E0E0E0',
  },
  glassCard: {
    background: 'rgba(20, 20, 25, 0.6)',
    backdropFilter: 'blur(16px)',
    WebkitBackdropFilter: 'blur(16px)',
    border: '1px solid rgba(255, 255, 255, 0.05)',
    borderRadius: '16px',
    padding: '40px',
    width: '100%',
    maxWidth: '420px',
    boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.1)',
  },
  logoContainer: {
    textAlign: 'center',
    marginBottom: '32px',
  },
  title: {
    margin: '16px 0 4px 0',
    fontSize: '28px',
    fontWeight: 700,
    letterSpacing: '2px',
    color: '#FFF',
  },
  subtitle: {
    color: '#D4AF37', // Gold accent
  },
  tagline: {
    margin: 0,
    fontSize: '12px',
    color: '#888',
    textTransform: 'uppercase',
    letterSpacing: '1px',
  },
  form: {
    display: 'flex',
    flexDirection: 'column',
    gap: '20px',
  },
  inputGroup: {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
  },
  label: {
    fontSize: '13px',
    fontWeight: 500,
    color: '#AAA',
  },
  passwordContainer: {
    position: 'relative',
    display: 'flex',
    alignItems: 'center',
  },
  icon: {
    position: 'absolute',
    left: '12px',
  },
  input: {
    width: '100%',
    padding: '12px 16px',
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    border: '1px solid rgba(255, 255, 255, 0.1)',
    borderRadius: '8px',
    color: '#FFF',
    fontSize: '15px',
    outline: 'none',
    transition: 'border-color 0.2s',
    boxSizing: 'border-box',
  },
  button: {
    marginTop: '10px',
    padding: '14px',
    backgroundColor: '#D4AF37',
    color: '#0A0A0A',
    border: 'none',
    borderRadius: '8px',
    fontSize: '16px',
    fontWeight: 600,
    cursor: 'pointer',
    transition: 'transform 0.1s, background-color 0.2s',
    boxShadow: '0 4px 14px 0 rgba(212, 175, 55, 0.39)',
  },
  error: {
    backgroundColor: 'rgba(255, 50, 50, 0.1)',
    border: '1px solid rgba(255, 50, 50, 0.3)',
    color: '#ff6b6b',
    padding: '12px',
    borderRadius: '8px',
    fontSize: '14px',
    textAlign: 'center',
  }
};

export default LoginPage;
