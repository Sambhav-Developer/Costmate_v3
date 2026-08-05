'use client';

import React, { useState, useEffect } from 'react';
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
} from 'lucide-react';
import { api } from '../lib/api';
import SetupWizardModal from './SetupWizardModal';

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
    if (!confirm('Delete this estimation and all its data?')) return;
    try { await api.deleteSession(sessionId); } catch { /* ignore */ }
    setSessionsList(prev => {
      const updated = prev.filter(s => s.id !== sessionId);
      localStorage.setItem('costmate_sessions_history', JSON.stringify(updated));
      return updated;
    });
    if (activeSessionId === sessionId) onSelectSession(null);
    setExpandedSessions(prev => { const n = new Set(prev); n.delete(sessionId); return n; });
  };

  return (
    <aside
      className="flex flex-col h-full shrink-0 font-sans select-none border-r border-border/50 transition-all duration-300"
      style={{ width: collapsed ? 44 : 270, background: 'var(--cm-sidebar)', overflow: 'hidden' }}>

      {/* ── Collapsed Strip ── */}
      {collapsed && (
        <div className="flex flex-col items-center gap-3 py-4">
          {/* Expand button */}
          <button onClick={() => setCollapsed(false)}
            className="w-8 h-8 flex items-center justify-center rounded-xl cursor-pointer transition-all text-[#d946ef] hover:scale-110" title="Expand Sidebar">
            <PanelLeftOpen className="w-4 h-4" />
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
            <button
              onClick={() => setIsWizardOpen(true)}
              className="btn-accent flex-1 flex items-center justify-center gap-2 py-2 px-3 text-xs rounded-xl"
            >
              <Upload className="w-3.5 h-3.5" />
              New Project
            </button>
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
              sessionsList.map((s) => {
                const isActive = activeSessionId === s.id;
                const isExpanded = expandedSessions.has(s.id);
                const subItems = getSubItems(s);

                return (
                  <div key={s.id} className="flex flex-col">
                    {/* ── Session Row ── */}
                    <div
                      onClick={() => handleSessionClick(s.id)}
                      className={`group flex flex-col gap-2 p-3 rounded-xl border cursor-pointer transition-all duration-150 ${
                        isActive
                          ? 'border-[#8b5cf6]/30 shadow-sm shadow-[#8b5cf6]/5 bg-gradient-accent bg-opacity-10 text-white'
                          : 'border-transparent hover:border-border/60'
                      }`}
                      style={{ background: isActive ? 'transparent' : 'transparent' }}
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
                    </div>

                    {/* ── Sub-items ── */}
                    {isExpanded && (
                      <div className="ml-4 mb-1 flex flex-col gap-0.5 pl-3 border-l-2 animate-fade-in"
                        style={{ borderColor: 'rgba(139,92,246,0.25)' }}>
                        {subItems.map((item) => {
                          const isFileActive = activeFile?.sessionId === s.id && activeFile?.fileType === item.type;
                          return (
                            <button key={item.type} type="button" disabled={!item.available}
                              onClick={() => item.available && onSelectFile?.(s.id, item.type, s.filename)}
                              className={`flex items-center gap-2.5 px-3 py-2.5 mt-1.5 rounded-xl text-xs font-bold transition-all duration-300 cursor-pointer text-left w-full border ${
                                !item.available ? 'opacity-35 cursor-not-allowed' : ''
                              } ${
                                isFileActive 
                                  ? 'bg-gradient-accent text-white border-transparent shadow-md' 
                                  : 'bg-panel border-border text-fg hover:border-[#8b5cf6]/30 hover:shadow-md hover:-translate-y-0.5'
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
                            </button>
                          );
                        })}
                      </div>
                    )}
                  </div>
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

      <SetupWizardModal
        isOpen={isWizardOpen}
        onClose={() => setIsWizardOpen(false)}
        onTakeoffStarted={onNewSessionCreated}
      />
    </aside>
  );
}

