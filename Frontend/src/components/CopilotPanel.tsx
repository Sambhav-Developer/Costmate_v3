'use client';

import React, { useState, useRef, useEffect } from 'react';
import {
  Send,
  Terminal as TerminalIcon,
  Sparkles,
  User,
  Loader2,
  ChevronsLeft,
  ChevronsRight,
  Bot,
} from 'lucide-react';
import { api } from '../lib/api';

interface ChatMessage {
  role: 'user' | 'assistant';
  message: string;
  timestamp: string;
}

interface CopilotPanelProps {
  sessionId: string;
  sessionState: any;
  refreshSession: () => void;
  progress: number;
  status: string;
  step: string;
  isCollapsed?: boolean;
  onCollapseChange?: (collapsed: boolean) => void;
}

export default function CopilotPanel({
  sessionId,
  sessionState,
  refreshSession,
  progress,
  status,
  step,
  isCollapsed: controlledCollapsed,
  onCollapseChange,
}: CopilotPanelProps) {
  const [internalCollapsed, setInternalCollapsed] = useState(false);
  const collapsed = controlledCollapsed !== undefined ? controlledCollapsed : internalCollapsed;
  const setCollapsed = (v: boolean) => {
    setInternalCollapsed(v);
    onCollapseChange?.(v);
  };
  const [message, setMessage] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const feedEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (sessionState?.chat_history && sessionState.chat_history.length > 0) {
      setChatHistory(sessionState.chat_history);
    } else {
      setChatHistory([{
        role: 'assistant',
        message: `Hello! I'm your Civil Work Estimation AI Copilot. You can ask me anything about your drawing, takeoff estimations, materials, or dimensions. I'm here to help you review parameters, query plan details, or modify any value to update your estimate instantly!`,
        timestamp: new Date().toISOString(),
      }]);
    }
  }, [sessionState]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatHistory, submitting]);

  useEffect(() => {
    feedEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [step, status, progress]);

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!message.trim() || submitting) return;

    const userMessage = message.trim();
    setMessage('');
    setSubmitting(true);

    const tempHistory: ChatMessage[] = [
      ...chatHistory,
      { role: 'user', message: userMessage, timestamp: new Date().toISOString() },
    ];
    setChatHistory(tempHistory);

    try {
      const response = await api.sendChatMessage(sessionId, userMessage);
      if (response?.chat_history) {
        setChatHistory(response.chat_history);
      } else {
        setChatHistory([
          ...tempHistory,
          {
            role: 'assistant',
            message: response.ai_response || "I've processed your request.",
            timestamp: new Date().toISOString(),
          },
        ]);
      }
      if (response?.has_updates) refreshSession();
    } catch (err: any) {
      setChatHistory([
        ...tempHistory,
        {
          role: 'assistant',
          message: `Sorry, I encountered an error: ${err.message || 'Unable to reach backend copilot.'}`,
          timestamp: new Date().toISOString(),
        },
      ]);
    } finally {
      setSubmitting(false);
    }
  };

  const getAgentLogs = () => {
    const logs: { id: string; time: string; tag: string; text: string; type: string }[] = [];
    if (progress >= 5)  logs.push({ id: 'l1', time: '—', tag: 'INGEST',       text: 'Drawing ingestion pipeline initialized.', type: 'info' });
    if (progress >= 15) logs.push({ id: 'l2', time: '—', tag: 'OCR_AGENT',    text: 'Vision OCR scan complete. Title blocks cataloged.', type: 'success' });
    if (progress >= 35) logs.push({ id: 'l3', time: '—', tag: 'VISION_SWARM', text: 'Spatial columns & rooms mapped.', type: 'success' });
    if (progress >= 45) logs.push({ id: 'l4', time: '—', tag: 'ORCHESTRATOR', text: 'Parameters extracted. Form pre-filled.', type: 'info' });
    if (status === 'paused_qa')
      logs.push({ id: 'lp', time: 'NOW', tag: 'HUMAN_GATE', text: 'HIL Gate active — waiting for parameter review...', type: 'warning' });
    if ((status === 'processing' || status === 'calculating') && progress >= 70)
      logs.push({ id: 'lc', time: 'NOW', tag: 'CALC_SWARM', text: 'Computing civil quantities and volumes...', type: 'info' });
    if (status === 'completed') {
      logs.push({ id: 'ld1', time: '✓', tag: 'CALC_SWARM',   text: 'Quantities computed successfully.', type: 'success' });
      logs.push({ id: 'ld2', time: '✓', tag: 'EXCEL_WRITER', text: 'BOQ Excel generated and ready.', type: 'success' });
    }
    if (status === 'failed')
      logs.push({ id: 'le', time: '✕', tag: 'ERROR', text: sessionState?.error || 'Agent run failed.', type: 'error' });
    return logs;
  };

  const agentLogs = getAgentLogs();

  const panelBg    = 'var(--panel)';
  const panelBorder = 'var(--panel-border)';
  const headerBg   = 'var(--panel-header)';

  return (
    <div className={`shrink-0 border-r flex flex-col h-full select-none transition-all duration-300`}
      style={{
        width: collapsed ? 44 : 360,
        background: panelBg,
        borderColor: panelBorder,
        overflow: 'hidden',
      }}>

      {/* ── Header ── */}
      <div className="px-3 py-3.5 border-b flex items-center justify-between shrink-0"
        style={{ borderColor: panelBorder, background: headerBg }}>
        {!collapsed && (
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-[#d946ef]" />
            <span className="font-bold text-xs tracking-wider uppercase" style={{ color: 'var(--foreground)' }}>
              AI Swarm Copilot
            </span>
          </div>
        )}
        {collapsed && (
          <button onClick={() => setCollapsed(false)}
            className="w-8 h-8 flex items-center justify-center rounded-xl cursor-pointer transition-all border text-[#d946ef]" title="Expand Copilot">
            <Bot className="w-4 h-4" />
          </button>
        )}
        {!collapsed && (
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[9px] font-mono font-bold pill-accent">
              <span className="w-1.5 h-1.5 rounded-full animate-pulse bg-gradient-accent" />
              LIVE
            </div>
            <button onClick={() => setCollapsed(true)}
              className="w-7 h-7 flex items-center justify-center rounded-lg cursor-pointer transition-all"
              style={{ color: 'var(--muted)' }} title="Collapse Copilot">
              <ChevronsLeft className="w-4 h-4" />
            </button>
          </div>
        )}
      </div>

      {/* ── Chat ── */}
      {!collapsed && (
      <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-4 min-h-0">
        {chatHistory.map((msg, idx) => (
          <div key={idx}
            className={`flex flex-col gap-1 max-w-[88%] animate-fade-in ${
              msg.role === 'user' ? 'self-end items-end' : 'self-start items-start'
            }`}>
            {/* Sender label */}
            <div className="flex items-center gap-1 text-[10px] font-semibold px-1" style={{ color: 'var(--muted)' }}>
              {msg.role === 'user' ? (
                <><span>Engineer</span><User className="w-2.5 h-2.5" /></>
              ) : (
                <><Sparkles className="w-2.5 h-2.5 text-[#d946ef]" /><span className="text-gradient-accent">Copilot</span></>
              )}
            </div>

            {/* Bubble */}
            <div className={`p-3 rounded-2xl text-xs leading-relaxed border ${
              msg.role === 'user' ? 'rounded-tr-none bg-gradient-accent border-transparent shadow-md text-white' : 'rounded-tl-none'
            }`}
              style={msg.role !== 'user' ? {
                background: 'var(--panel-header)',
                borderColor: 'var(--panel-border)',
                color: 'var(--foreground)',
              } : undefined}>
              {msg.message}
            </div>

            {/* Timestamp */}
            <span className="text-[8px] font-mono px-1.5" style={{ color: 'var(--muted)' }}>
              {msg.timestamp ? new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}
            </span>
          </div>
        ))}

        {/* Typing indicator */}
        {submitting && (
          <div className="self-start flex flex-col gap-1 max-w-[88%] animate-pulse">
            <div className="flex items-center gap-1 text-[10px] font-semibold px-1 text-gradient-accent">
              <Sparkles className="w-2.5 h-2.5 animate-spin" />
              <span>Copilot is writing…</span>
            </div>
            <div className="p-3 rounded-2xl rounded-tl-none flex items-center justify-center h-9"
              style={{ background: 'var(--panel-header)', border: '1px solid var(--panel-border)' }}>
              <span className="flex gap-1">
                {[0, 150, 300].map(delay => (
                  <span key={delay} className="w-1.5 h-1.5 rounded-full animate-bounce"
                    style={{ background: 'var(--accent)', animationDelay: `${delay}ms` }} />
                ))}
              </span>
            </div>
          </div>
        )}
        <div ref={chatEndRef} />
      </div>
      )} {/* end !collapsed chat */}

      {/* ── Input ── */}
      {!collapsed && (
      <form onSubmit={handleSendMessage} className="p-3 border-t flex gap-2"
        style={{ borderColor: panelBorder, background: headerBg }}>
        <input
          type="text"
          value={message}
          onChange={e => setMessage(e.target.value)}
          placeholder="Ask Copilot or modify a parameter…"
          disabled={submitting}
          className="flex-1 border rounded-xl px-3.5 py-2 text-xs focus:outline-none disabled:opacity-50 transition-colors"
          style={{
            background: 'var(--input-bg)',
            borderColor: 'var(--input-border)',
            color: 'var(--input-fg)',
          }}
          onFocus={e => (e.target.style.borderColor = 'var(--accent)')}
          onBlur={e => (e.target.style.borderColor = 'var(--input-border)')}
        />
        <button type="submit" disabled={submitting || !message.trim()}
          className="flex items-center justify-center w-8 h-8 rounded-xl transition-all disabled:opacity-50 cursor-pointer shrink-0 bg-gradient-accent"
          style={{
            color: 'white',
            boxShadow: '0 4px 12px rgba(255,81,47,.3)',
          }}>
          {submitting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
        </button>
      </form>
      )}

      {/* ── Agent Log Terminal ── */}
      {!collapsed && (
      <div className="h-44 border-t flex flex-col shrink-0"
        style={{ borderColor: panelBorder, background: 'var(--term)' }}>
        {/* Log header */}
        <div className="px-3 py-2 border-b flex items-center justify-between"
          style={{ borderColor: 'rgba(255,255,255,0.06)' }}>
          <div className="flex items-center gap-1.5 text-gradient-accent">
            <TerminalIcon className="w-3 h-3" />
            <span className="font-mono text-[10px] font-semibold uppercase">
              Agent Activity Log
            </span>
          </div>
          <div className="flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full animate-pulse bg-gradient-accent" />
            <span className="text-[8px] font-mono" style={{ color: 'var(--muted)' }}>LIVE</span>
          </div>
        </div>

        {/* Log entries */}
        <div className="flex-1 overflow-y-auto p-3 font-mono text-[9px] flex flex-col gap-1.5">
          {agentLogs.length === 0 ? (
            <div className="h-full flex items-center justify-center italic" style={{ color: 'var(--muted)' }}>
              Awaiting pipeline events…
            </div>
          ) : (
            agentLogs.map(log => (
              <div key={log.id} className="flex gap-2 items-start leading-relaxed animate-slide-in">
                <span style={{ color: 'var(--muted)' }} className="select-none">[{log.time}]</span>
                <span className={`font-bold select-none ${!['success', 'warning', 'error'].includes(log.type) ? 'text-gradient-accent' : ''}`} style={{
                  color: log.type === 'success' ? '#10b981'
                    : log.type === 'warning' ? '#f59e0b'
                    : log.type === 'error' ? '#ef4444'
                    : undefined,
                }}>
                  [{log.tag}]
                </span>
                <span className="flex-1" style={{ color: 'var(--term-fg)', opacity: 0.8 }}>{log.text}</span>
              </div>
            ))
          )}
          <div ref={feedEndRef} />
        </div>
      </div>
      )}
    </div>
  );
}
