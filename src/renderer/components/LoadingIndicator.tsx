import { useState, useEffect } from "react";
import { GENERATION_MESSAGES, EVALUATION_MESSAGES } from "../constants/loadingMessages";

interface LoadingIndicatorProps {
  type?: "generation" | "evaluation";
  className?: string;
}

export default function LoadingIndicator({ type = "generation", className = "" }: LoadingIndicatorProps) {
  const [messageIndex, setMessageIndex] = useState(0);
  const messages = type === "generation" ? GENERATION_MESSAGES : EVALUATION_MESSAGES;

  useEffect(() => {
    const interval = setInterval(() => {
      setMessageIndex((prev) => (prev + 1) % messages.length);
    }, 2500);
    return () => clearInterval(interval);
  }, [messages]);

  return (
    <div className={`flex flex-col items-center justify-center space-y-6 py-12 ${className}`}>
      {/* The Animated Highlighter Scanning Effect */}
      <div className="relative w-48 h-1 bg-surface-container-highest overflow-hidden">
        <div 
          className="absolute inset-0 bg-tertiary-fixed shadow-[0_0_12px_rgba(218,224,88,0.8)] animate-scan"
          style={{ width: '40%' }}
        />
      </div>

      <div className="text-center space-y-2">
        <p className="font-headline text-title-lg text-primary animate-pulse-slow">
          {messages[messageIndex]}
        </p>
        <p className="font-label text-label-sm text-on-surface-variant tracking-[0.2em]">
          Loading...
        </p>
      </div>

      <style dangerouslySetInnerHTML={{ __html: `
        @keyframes scan {
          0% { transform: translateX(-150%); }
          100% { transform: translateX(250%); }
        }
        @keyframes pulse-slow {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.6; }
        }
        .animate-scan {
          animation: scan 2s cubic-bezier(0.4, 0, 0.2, 1) infinite;
        }
        .animate-pulse-slow {
          animation: pulse-slow 3s ease-in-out infinite;
        }
      `}} />
    </div>
  );
}
