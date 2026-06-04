/**
 * components/ErrorBoundary.tsx
 * Captura errores en el árbol de componentes y muestra un fallback
 * en lugar de dejar la pantalla en negro.
 */
import { Component, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: { componentStack: string }) {
    console.error('[Iosef ErrorBoundary]', error.message, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback ?? (
        <div style={{
          display: 'flex', flexDirection: 'column', alignItems: 'center',
          justifyContent: 'center', height: '100%', gap: 12,
          color: 'var(--text-secondary)', padding: 32,
        }}>
          <span style={{ fontSize: 32 }}>⚠️</span>
          <strong style={{ color: 'var(--text-primary)' }}>Error en el componente</strong>
          <code style={{
            fontSize: 11, color: 'var(--red)', background: 'var(--bg-0)',
            padding: '6px 10px', borderRadius: 4, maxWidth: 480, textAlign: 'center'
          }}>
            {this.state.error?.message ?? 'Error desconocido'}
          </code>
          <button
            style={{
              marginTop: 8, padding: '6px 16px', borderRadius: 4,
              border: '1px solid var(--border)', background: 'var(--bg-1)',
              color: 'var(--text-primary)', cursor: 'pointer', fontSize: 12
            }}
            onClick={() => this.setState({ hasError: false, error: null })}
          >
            Reintentar
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
