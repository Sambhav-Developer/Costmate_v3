'use client';

import React, { useEffect, useRef } from 'react';
import { Terminal as TermIcon, ShieldCheck, Cpu } from 'lucide-react';

interface TerminalLog {
  timestamp: string;
  message: string;
  type: 'info' | 'success' | 'warn' | 'error' | 'stdout';
}

interface TerminalProps {
  logs: TerminalLog[];
  progressPct: number;
  status: string;
}

export default function Terminal({ logs, progressPct, status }: TerminalProps) {
  const terminalEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    terminalEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  // Colorize log text based on message categories or direct type
  const getLogColor = (type: string) => {
    switch (type) {
      case 'success':
        return 'text-emerald-400 font-semibold';
      case 'error':
        return 'text-red-400 font-bold';
      case 'warn':
        return 'text-amber-400';
      case 'info':
        return 'text-cyan-400';
      default:
        return 'text-slate-300';
    }
  };

  return (
    <div className="h-72 bg-term text-term-fg border-t border-border flex flex-col shrink-0 font-mono text-xs select-none">
      {/* Console Tab Headers */}
      <div className="h-9 border-b border-border flex items-center px-4 justify-between bg-header select-none">
        <div className="flex gap-4">
          <span className="flex items-center gap-1.5 border-b-2 border-accent text-slate-200 px-1 py-1 font-bold">
            <TermIcon className="w-3.5 h-3.5 text-accent" />
            AGENT_STREAM_CONSOLES
          </span>
        </div>
        
        {/* Status indicator */}
        <div className="flex items-center gap-4 text-[10px]">
          <span className="flex items-center gap-1.5">
            <Cpu className="w-3 h-3 text-cyan-400 animate-spin" />
            ENGINE_STATUS: <span className="font-bold text-slate-200 uppercase">{status || 'IDLE'}</span>
          </span>
          <span className="flex items-center gap-1.5">
            <ShieldCheck className="w-3 h-3 text-emerald-400" />
            INTEGRITY: <span className="font-bold text-emerald-400">PASSED</span>
          </span>
        </div>
      </div>

      {/* Terminal Viewport */}
      <div className="flex-1 overflow-y-auto p-4 bg-black/40 flex flex-col gap-1 font-mono leading-relaxed select-text select-all selection:bg-slate-700">
        {logs.length === 0 ? (
          <div className="text-slate-500 italic py-2">
            No active agent tasks. Import a floor plan drawing to spin up the estimation nodes.
          </div>
        ) : (
          logs.map((log, index) => (
            <div key={index} className="flex gap-2.5 items-start">
              <span className="text-slate-600 shrink-0 select-none">[{log.timestamp}]</span>
              <span className={getLogColor(log.type)}>{log.message}</span>
            </div>
          ))
        )}
        <div ref={terminalEndRef} />
      </div>

      {/* Status Progress Bar Footer */}
      <div className="h-6 bg-header border-t border-border flex items-center px-4 justify-between text-[11px] text-slate-500 dark:text-slate-400">
        <div className="flex items-center gap-3">
          <span className="bg-accent/10 text-accent font-bold px-1.5 py-0.5 rounded text-[10px]">
            {progressPct}% RUNNING
          </span>
          <span className="truncate">Pipeline Swarm Execution Tasks</span>
        </div>
        
        {/* Visual Progress Bar tracker */}
        <div className="w-64 bg-slate-700/50 rounded-full h-1.5 overflow-hidden flex relative border border-slate-600/30">
          <div 
            className="bg-accent h-full transition-all duration-300 ease-out"
            style={{ width: `${progressPct}%` }}
          />
        </div>
      </div>
    </div>
  );
}
