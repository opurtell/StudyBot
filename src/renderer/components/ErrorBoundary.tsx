import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("ErrorBoundary caught:", error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-background text-on-surface flex items-center justify-center p-8">
          <div className="max-w-md space-y-4 text-center">
            <h2 className="font-headline text-display-lg text-primary">
              Something went wrong
            </h2>
            <p className="font-body text-body-sm text-on-surface-variant">
              An unexpected error occurred. Please try reloading the page.
            </p>
            {this.state.error && (
              <pre className="font-mono text-[10px] text-status-critical bg-surface-container p-3 rounded overflow-auto text-left max-h-32">
                {this.state.error.message}
              </pre>
            )}
            <button
              onClick={() => window.location.reload()}
              className="px-6 py-2 bg-primary text-on-primary font-label text-label-sm uppercase tracking-wider"
            >
              Reload
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
