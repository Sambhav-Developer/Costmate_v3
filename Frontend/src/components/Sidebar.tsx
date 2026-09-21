'use client';

import React, { useState, useEffect, useCallback } from 'react';
import {
  Upload,
  CheckCircle2,
  Clock,
  HelpCircle,
  FolderOpen,
  FolderClosed,
  Trash2,
  FileText,
  AlertTriangle,
  Loader2,
  FileImage,
  FileSpreadsheet,
  BookOpen,
  ChevronRight,
  PanelLeftClose,
  PanelLeftOpen,
  Settings2,
  X,
  AlertCircle,
} from 'lucide-react';
import { api } from '../lib/api';
import SetupWizardModal from './SetupWizardModal';
import { motion, AnimatePresence } from 'framer-motion';

type FileType = 'plan' | 'excel' | 'readme' | 'parameters';

interface EstimationSession {
  id: string;
  filename: string;
  date: string;
  status: string;
}

interface SidebarProps {
  activeSessionId: string | null;
  onSelectSession: (sessionId: string | null) => void;
  onNewSessionCreated: (sessionId: string, filename: string) => void;
  sessionsList: EstimationSession[];
  setSessionsList: React.Dispatch<React.SetStateAction<EstimationSession[]>>;
  onSelectFile?: (sessionId: string, fileType: FileType, sessionName: string) => void;
  activeFile?: { sessionId: string; fileType: FileType } | null;
}

function StatusBadge({ status }: { status: string }) {
  if (status === 'completed')
    return (
      <span className="flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full pill-success">
        <CheckCircle2 className="w-2.5 h-2.5" /> Done
      </span>
    );
  if (status === 'paused_qa')
    return (
      <span className="flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full pill-warning">
        <Clock className="w-2.5 h-2.5" /> Review
      </span>
    );
  if (status === 'failed')
    return (
      <span className="flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full pill-danger">
        <AlertTriangle className="w-2.5 h-2.5" /> Failed
      </span>
    );
  return (
    <span className="flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full pill-accent">
      <Loader2 className="w-2.5 h-2.5 animate-spin" /> Running
    </span>
  );
}

interface SubItem {
  type: FileType;
  label: string;
  icon: React.ReactNode;
  available: boolean;
}

function getSubItems(session: EstimationSession): SubItem[] {
  const done = session.status === 'completed';
  const hasQA = session.status === 'completed' || session.status === 'paused_qa';
  return [
    {
      type: 'plan',
      label: 'Floor Plan',
      icon: <FileImage className="w-3 h-3" />,
      available: true,
    },
    {
      type: 'parameters',
      label: 'Parameters',
      icon: <Settings2 className="w-3 h-3" />,
      available: hasQA,
    },
    {
      type: 'excel',
      label: 'BOQ Excel',
      icon: <FileSpreadsheet className="w-3 h-3" />,
      available: done,
    },
  ];
}

export default function Sidebar({
  activeSessionId,
  onSelectSession,
  onNewSessionCreated,
  sessionsList,
  setSessionsList,
  onSelectFile,
  activeFile,
}: SidebarProps) {
  const [isWizardOpen, setIsWizardOpen] = useState(false);

  // Custom event listener to trigger modal from page.tsx
  useEffect(() => {
    const handleOpenModal = () => setIsWizardOpen(true);
    window.addEventListener('open-new-project', handleOpenModal);
    return () => window.removeEventListener('open-new-project', handleOpenModal);
  }, []);
  const [collapsed, setCollapsed] = useState(false);
  // Track which sessions are expanded (showing sub-items)
  const [expandedSessions, setExpandedSessions] = useState<Set<string>>(new Set());

  // Toast state
  type Toast = { id: string; type: 'confirm' | 'success' | 'error'; message: string; sessionId?: string; sessionName?: string; timer?: ReturnType<typeof setTimeout>; };
  const [toasts, setToasts] = useState<Toast[]>([]);

  const dismissToast = useCallback((id: string) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  const showToast = useCallback((toast: Omit<Toast, 'id' | 'timer'>) => {
    const id = Math.random().toString(36).slice(2);
    const timer = toast.type !== 'confirm' ? setTimeout(() => dismissToast(id), 3000) : undefined;
    setToasts(prev => [...prev.filter(t => t.type !== 'confirm'), { ...toast, id, timer }]);
  }, [dismissToast]);

  const toggleExpand = (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setExpandedSessions(prev => {
      const next = new Set(prev);
      if (next.has(sessionId)) {
        next.delete(sessionId);
      } else {
        next.add(sessionId);
      }
      return next;
    });
  };

  const handleSessionClick = (sessionId: string) => {
    // Select session (loads main panel) AND expand sub-items
    onSelectSession(sessionId);
    setExpandedSessions(prev => {
      const next = new Set(prev);
      next.add(sessionId); // auto-expand on select
      return next;
    });
  };

  const handleDeleteSession = async (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation();
    const session = sessionsList.find(s => s.id === sessionId);
    showToast({ type: 'confirm', message: `Delete "${session?.filename || 'this estimation'}" and all its data?`, sessionId, sessionName: session?.filename });
  };

  const confirmDelete = async (sessionId: string, toastId: string) => {
    dismissToast(toastId);
    try { await api.deleteSession(sessionId); } catch { /* ignore */ }
    setSessionsList(prev => {
      const updated = prev.filter(s => s.id !== sessionId);
      localStorage.setItem('costmate_sessions_history', JSON.stringify(updated));
      return updated;
    });
    if (activeSessionId === sessionId) onSelectSession(null);
    setExpandedSessions(prev => { const n = new Set(prev); n.delete(sessionId); return n; });
    showToast({ type: 'success', message: 'Estimation deleted successfully.' });
  };

  return (
    <>
      <motion.aside
        layout
        initial={false}
        animate={{ width: collapsed ? 64 : 280 }}
        transition={{ type: 'spring', stiffness: 300, damping: 30 }}
        className="flex flex-col h-[calc(100%-2rem)] shrink-0 font-sans select-none minimal-glass my-4 ml-4 rounded-[2rem] shadow-2xl"
        style={{ overflow: 'hidden' }}>

      {/* ── Collapsed Strip ── */}
      {collapsed && (
        <div className="flex flex-col items-center gap-3 py-4">
          {/* Expand button */}
          <button onClick={() => setCollapsed(false)}
            className="w-10 h-10 flex items-center justify-center rounded-2xl cursor-pointer transition-all text-accent hover:scale-110 bg-white/50 border border-white/60 shadow-sm" title="Expand Sidebar">
            <PanelLeftOpen className="w-5 h-5" />
          </button>
          {/* Session dots */}
          <div className="flex flex-col gap-2 mt-2">
            {sessionsList.map((s) => {
              // Generate clever 1-2 letter initials
              const initials = s.filename.split(/[\s-_]+/).filter(w => w.length > 0).slice(0, 2).map(w => w[0]).join('').toUpperCase().substring(0, 2);
              return (
                <button key={s.id} onClick={() => { setCollapsed(false); handleSessionClick(s.id); }}
                  className="w-8 h-8 rounded-xl flex items-center justify-center text-[11px] font-extrabold cursor-pointer transition-all hover:scale-110 shadow-sm"
                  title={s.filename}
                  style={{
                    background: activeSessionId === s.id ? 'var(--accent)' : 'var(--panel-header)',
                    color: activeSessionId === s.id ? '#ffffff' : 'var(--muted)',
                    border: `1px solid ${activeSessionId === s.id ? 'var(--accent)' : 'var(--panel-border)'}`,
                    boxShadow: activeSessionId === s.id ? '0 4px 12px var(--accent-subtle)' : 'none'
                  }}>
                  {initials || 'P'}
                </button>
              );
            })}
          </div>
          {/* New Project */}
          <button onClick={() => { setCollapsed(false); setIsWizardOpen(true); }}
            className="w-8 h-8 flex items-center justify-center rounded-xl cursor-pointer transition-all mt-2 bg-gradient-accent text-white" title="New Project">
            <Upload className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* ── Expanded View ── */}
      {!collapsed && (
        <>
          {/* Header with New Project + Collapse */}
          <div className="px-3 py-3 border-b border-border/40 flex items-center gap-2">
            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              onClick={() => setIsWizardOpen(true)}
              className="btn-accent flex-1 flex items-center justify-center gap-2 py-2 px-3 text-xs rounded-full"
            >
              <Upload className="w-3.5 h-3.5" />
              New Project
            </motion.button>
            <button onClick={() => setCollapsed(true)}
              className="w-8 h-8 flex items-center justify-center rounded-xl cursor-pointer transition-all shrink-0"
              style={{ color: 'var(--muted)', border: '1px solid var(--panel-border)' }}
              title="Collapse Sidebar">
              <PanelLeftClose className="w-4 h-4" />
            </button>
          </div>

          {/* Section heading */}
          <div className="px-4 py-2.5 flex items-center gap-2 border-b border-border/30">
            <FolderOpen className="w-3 h-3 text-accent" />
            <span className="section-label text-gradient-accent">Drawings &amp; Estimations</span>
          </div>

          {/* Session list */}
          <div className="flex-1 overflow-y-auto p-2.5 flex flex-col gap-1">
            {sessionsList.length === 0 ? (
              <div className="flex flex-col items-center justify-center text-center p-8 gap-3 mt-6 opacity-50">
                <FileText className="w-10 h-10 stroke-1" style={{ color: 'var(--muted)' }} />
                <p className="text-xs leading-relaxed" style={{ color: 'var(--muted)' }}>
                  No plans yet.<br />Click <strong>New Project</strong> to begin.
                </p>
              </div>
            ) : (
              sessionsList.map((s, index) => {
                const isActive = activeSessionId === s.id;
                const isExpanded = expandedSessions.has(s.id);
                const subItems = getSubItems(s);

                return (
                  <motion.div layout key={s.id} className="flex flex-col stagger-item" style={{ animationDelay: `${index * 0.1}s` }}>
                    {/* ── Session Row ── */}
                    <motion.div
                      layout
                      whileHover={{ scale: 1.01 }}
                      whileTap={{ scale: 0.99 }}
                      onClick={() => handleSessionClick(s.id)}
                      className={`group flex flex-col gap-2 p-3 rounded-2xl border cursor-pointer transition-all duration-150 ${
                        isActive
                          ? 'border-accent text-fg'
                          : 'border-transparent hover:border-border/60'
                      }`}
                      style={{ background: isActive ? 'var(--panel)' : 'transparent' }}
                    >
                      <div className="flex items-start justify-between gap-1">
                        <button type="button" onClick={(e) => toggleExpand(s.id, e)}
                          className="mt-0.5 w-5 h-5 flex items-center justify-center rounded shrink-0 transition-transform duration-200 cursor-pointer"
                          style={{ color: isActive ? 'var(--accent)' : 'var(--muted)' }}>
                          <ChevronRight className="w-3.5 h-3.5 transition-transform duration-200"
                            style={{ transform: isExpanded ? 'rotate(90deg)' : 'rotate(0deg)' }} />
                        </button>
                        <span className={`font-semibold text-xs truncate leading-snug flex-1 ${isActive ? 'text-gradient-accent text-glow' : 'text-foreground'}`}
                          title={s.filename}>
                          {s.filename}
                        </span>
                        <button onClick={(e) => handleDeleteSession(e, s.id)}
                          className="opacity-0 group-hover:opacity-100 p-1 rounded-lg transition-all hover:bg-red-500/10 hover:text-red-400 cursor-pointer shrink-0"
                          style={{ color: 'var(--muted)' }} title="Delete">
                          <Trash2 className="w-3 h-3" />
                        </button>
                      </div>
                      <div className="flex items-center justify-between pl-5">
                        <span className="text-[10px] font-mono" style={{ color: 'var(--muted)' }}>{s.date}</span>
                        <StatusBadge status={s.status} />
                      </div>
                    </motion.div>

                    {/* ── Sub-items ── */}
                    <AnimatePresence initial={false}>
                    {isExpanded && (
                      <motion.div 
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: 'auto', opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.2 }}
                        className="ml-4 mb-1 flex flex-col gap-0.5 pl-3 border-l-2 overflow-hidden"
                        style={{ borderColor: 'rgba(139,92,246,0.25)' }}>
                        {subItems.map((item) => {
                          const isFileActive = activeFile?.sessionId === s.id && activeFile?.fileType === item.type;
                          return (
                            <motion.button key={item.type} type="button" disabled={!item.available}
                              whileHover={item.available ? { scale: 1.02, x: 4 } : {}}
                              whileTap={item.available ? { scale: 0.98 } : {}}
                              onClick={() => item.available && onSelectFile?.(s.id, item.type, s.filename)}
                              className={`flex items-center gap-2.5 px-3 py-2.5 mt-1.5 rounded-2xl text-xs font-bold transition-all duration-300 cursor-pointer text-left w-full border ${
                                !item.available ? 'opacity-35 cursor-not-allowed' : ''
                              } ${
                                isFileActive 
                                  ? 'bg-gradient-accent text-white border-transparent shadow-md' 
                                  : 'bg-panel border-border text-fg hover:border-[#e05a33]/30 hover:shadow-md hover:-translate-y-0.5'
                              }`}
                              style={{}}
                              onMouseOver={undefined}
                              onMouseOut={undefined}>
                              <span className={isFileActive ? 'text-white' : 'text-[#FF512F]'} style={{ opacity: item.available ? 1 : 0.5 }}>
                                {item.icon}
                              </span>
                              <span className="truncate">{item.label}</span>
                              {!item.available && (
                                <span className="ml-auto text-[9px] px-1.5 py-0.5 rounded font-bold"
                                  style={{ background: 'var(--panel)', color: 'var(--muted)', border: '1px solid var(--panel-border)' }}>
                                  N/A
                                </span>
                              )}
                            </motion.button>
                          );
                        })}
                      </motion.div>
                    )}
                    </AnimatePresence>
                  </motion.div>
                );
              })
            )}
          </div>

          {/* Footer */}
          <div className="p-3 border-t border-border/40 flex items-center gap-2 justify-center">
            <HelpCircle className="w-3 h-3" style={{ color: 'var(--muted)' }} />
            <span className="text-[11px]" style={{ color: 'var(--muted)', opacity: 0.6 }}>Need help? Contact support</span>
          </div>
        </>
      )}
      </motion.aside>

      <AnimatePresence>
        {isWizardOpen && (
          <SetupWizardModal
            isOpen={true}
            onClose={() => setIsWizardOpen(false)}
            onTakeoffStarted={onNewSessionCreated}
          />
        )}
      </AnimatePresence>

      {/* ── Toast Notifications ── */}
      {toasts.length > 0 && (
        <div
          style={{
            position: 'fixed',
            top: 72,
            right: 24,
            zIndex: 9999,
            display: 'flex',
            flexDirection: 'column',
            gap: 10,
            width: 300,
            pointerEvents: 'none',
          }}
        >
          {toasts.map(toast => (
            <div
              key={toast.id}
              style={{
                pointerEvents: 'all',
                background: toast.type === 'confirm'
                  ? 'linear-gradient(135deg, #1e1a2e 0%, #241b36 100%)'
                  : toast.type === 'success'
                  ? 'linear-gradient(135deg, #0d2018 0%, #0f2920 100%)'
                  : 'linear-gradient(135deg, #2a1010 0%, #2e1212 100%)',
                border: `1px solid ${toast.type === 'confirm' ? '#7c3aed55' : toast.type === 'success' ? '#16a34a55' : '#dc262655'}`,
                borderRadius: 14,
                padding: '14px 16px',
                boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
                animation: 'slideUpToast 0.25s cubic-bezier(0.16,1,0.3,1)',
              }}
            >
              {toast.type === 'confirm' ? (
                <>
                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10, marginBottom: 12 }}>
                    <div style={{
                      width: 32, height: 32, borderRadius: 8, flexShrink: 0,
                      background: 'rgba(239,68,68,0.15)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center'
                    }}>
                      <Trash2 style={{ width: 15, height: 15, color: '#f87171' }} />
                    </div>
                    <div>
                      <p style={{ fontSize: 12, fontWeight: 700, color: '#f1f5f9', margin: 0 }}>Delete Estimation?</p>
                      <p style={{ fontSize: 11, color: '#94a3b8', margin: '3px 0 0', lineHeight: 1.4 }}>{toast.message}</p>
                    </div>
                    <button
                      onClick={() => dismissToast(toast.id)}
                      style={{ marginLeft: 'auto', background: 'none', border: 'none', cursor: 'pointer', color: '#64748b', padding: 2 }}
                    >
                      <X style={{ width: 13, height: 13 }} />
                    </button>
                  </div>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <button
                      onClick={() => toast.sessionId && confirmDelete(toast.sessionId, toast.id)}
                      style={{
                        flex: 1, padding: '7px 0', borderRadius: 8, border: 'none', cursor: 'pointer',
                        background: 'linear-gradient(135deg, #dc2626, #b91c1c)',
                        color: '#fff', fontSize: 12, fontWeight: 700,
                        boxShadow: '0 2px 8px rgba(220,38,38,0.35)',
                        transition: 'opacity 0.15s',
                      }}
                      onMouseEnter={e => (e.currentTarget.style.opacity = '0.85')}
                      onMouseLeave={e => (e.currentTarget.style.opacity = '1')}
                    >
                      Yes, Delete
                    </button>
                    <button
                      onClick={() => dismissToast(toast.id)}
                      style={{
                        flex: 1, padding: '7px 0', borderRadius: 8, cursor: 'pointer',
                        background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.1)',
                        color: '#94a3b8', fontSize: 12, fontWeight: 600,
                        transition: 'opacity 0.15s',
                      }}
                      onMouseEnter={e => (e.currentTarget.style.opacity = '0.7')}
                      onMouseLeave={e => (e.currentTarget.style.opacity = '1')}
                    >
                      Cancel
                    </button>
                  </div>
                </>
              ) : (
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <div style={{
                    width: 28, height: 28, borderRadius: 7, flexShrink: 0,
                    background: toast.type === 'success' ? 'rgba(22,163,74,0.2)' : 'rgba(220,38,38,0.2)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center'
                  }}>
                    {toast.type === 'success'
                      ? <CheckCircle2 style={{ width: 14, height: 14, color: '#4ade80' }} />
                      : <AlertCircle style={{ width: 14, height: 14, color: '#f87171' }} />
                    }
                  </div>
                  <p style={{ fontSize: 12, color: '#e2e8f0', margin: 0, flex: 1 }}>{toast.message}</p>
                  <button
                    onClick={() => dismissToast(toast.id)}
                    style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#64748b', padding: 2, flexShrink: 0 }}
                  >
                    <X style={{ width: 12, height: 12 }} />
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      <style>{`
        @keyframes slideUpToast {
          from { opacity: 0; transform: translateY(-16px) scale(0.97); }
          to   { opacity: 1; transform: translateY(0) scale(1); }
        }
      `}</style>
    </>
  );
}

