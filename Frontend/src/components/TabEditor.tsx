'use client';
import React, { useState, useEffect } from 'react';
import { CheckCircle2, Clock, Play, AlertTriangle, Building2, FileSpreadsheet, Settings2, FileImage, Layers, RefreshCw } from 'lucide-react';
import { api } from '../lib/api';
import ResultPanel from './editor/ResultPanel';
import { Door, Window } from './editor/types';
import { DoorsSchedule, WindowsSchedule } from './editor/ScheduleTables';

interface TabEditorProps {
  activeTab?: 'qa' | 'result';
  setActiveTab?: (tab: 'qa' | 'result') => void;
  sessionId: string | null;
  sessionState: any;
  refreshSession: () => void;
  displayName?: string;
  progress?: number;
  status?: string;
  step?: string;
}

// ─── Tab Button ────────────────────────────────────────────────
function TabBtn({ active, disabled, onClick, icon, label, badge }: {
  active: boolean; disabled?: boolean; onClick: () => void;
  icon: React.ReactNode; label: string; badge?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`flex items-center gap-2 px-6 py-3 font-bold text-xs transition-all ${active ? 'bg-gradient-accent text-white shadow-md rounded-t-xl -mb-px' : 'text-foreground hover:bg-panel-hover rounded-t-xl -mb-px'}`}
      style={active ? { boxShadow: '0 -4px 12px rgba(255,81,47,.2)' } : undefined}
    >
      {icon}
      {label}
      {badge && (
        <span className={`text-[9px] px-1.5 py-0.5 rounded-full font-bold ${active ? 'bg-white/20 text-white' : 'bg-gradient-accent bg-opacity-10 text-white'}`}>
          {badge}
        </span>
      )}
    </button>
  );
}

// ─── Processing Screen ─────────────────────────────────────────
function ProcessingScreen({ step, pct }: { step: string; pct: number }) {
  const desc: Record<string, string> = {
    upload_completed: 'Initializing Civil Work Estimator pipeline...',
    specs_analyzed: 'Analyzing project specifications...',
    schedule_parsed: 'Parsing door & window schedules...',
    ocr_completed: 'Reading annotations & layout marks...',
    cv_detector_completed: 'Detecting callout elements on drawings...',
    reconciliation_completed: 'Reconciling schedule items...',
    quantities_calculated: 'Formatting schedules & calculating quantities...',
    validation_completed: 'Running final validation check...',
  };

  return (
    <div className="flex-1 flex flex-col items-center justify-center p-8 select-none"
      style={{ background: 'var(--background)' }}>
      <div className="w-full max-w-sm rounded-2xl shadow-xl p-8 flex flex-col gap-6 items-center animate-fade-in"
        style={{ background: 'var(--panel)', border: '1px solid var(--panel-border)' }}>
        <div className="relative w-16 h-16">
          <div className="w-16 h-16 rounded-2xl flex items-center justify-center bg-gradient-accent text-white" style={{ opacity: 0.8 }}>
            <Building2 className="w-7 h-7" />
          </div>
          <span className="absolute inset-0 rounded-2xl border-2 border-t-transparent animate-spin"
            style={{ borderColor: 'var(--accent)', borderTopColor: 'transparent' }} />
        </div>
        <div className="text-center flex flex-col gap-1.5 w-full">
          <h3 className="text-base font-bold" style={{ color: 'var(--foreground)' }}>Running AI Estimate Agents…</h3>
          <p className="text-xs leading-relaxed" style={{ color: 'var(--muted)' }}>
            {desc[step] || 'Running background AI agents…'}
          </p>
        </div>
        <div className="w-full flex flex-col gap-1.5">
          <div className="w-full h-2 rounded-full overflow-hidden"
            style={{ background: 'var(--background)', border: '1px solid var(--panel-border)' }}>
            <div className="h-full bg-gradient-accent rounded-full transition-all duration-300 ease-out"
               style={{ width: `${Math.round(pct)}%` }} />
          </div>
          <div className="flex justify-between text-[10px] font-semibold">
            <span style={{ color: 'var(--muted)' }}>Takeoff Pipeline</span>
            <span className="font-bold text-gradient-accent">{Math.round(pct)}%</span>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Drawing Tab ───────────────────────────────────────────────
function DrawingTab({ sessionState }: { sessionState: any }) {
  const pages = sessionState?.uploaded_page_paths || [];
  const singlePath = sessionState?.uploaded_file_path;
  const imgUrl = (p: string) => p.startsWith('http') ? p : `${api.baseUrl}/static/uploads/${p.split(/[/\\]/).pop()}`;

  const renderBoundingBoxes = () => {
    const doors = sessionState?.qa_prefilled?.doors || [];
    const windows = sessionState?.qa_prefilled?.windows || [];
    const boxes: React.ReactNode[] = [];
    
    doors.forEach((d: any) => {
      if (d.bounding_boxes) {
        d.bounding_boxes.forEach((box: number[], idx: number) => {
          if (box.length === 4) {
            const [ymin, xmin, ymax, xmax] = box;
            const isUnknown = d.type === 'UNKNOWN';
            boxes.push(
              <div 
                key={`door-${d.type}-${idx}`}
                title={isUnknown ? "UNKNOWN Door" : `Door Type ${d.type}`}
                className="absolute border-2 rounded-sm cursor-help transition-all"
                style={{
                  top: `${ymin * 100}%`,
                  left: `${xmin * 100}%`,
                  height: `${(ymax - ymin) * 100}%`,
                  width: `${(xmax - xmin) * 100}%`,
                  borderColor: isUnknown ? '#ef4444' : '#818cf8',
                  backgroundColor: isUnknown ? 'rgba(239, 68, 68, 0.15)' : 'rgba(129, 140, 248, 0.15)',
                  zIndex: isUnknown ? 20 : 10
                }}
              >
                {isUnknown && <span className="absolute -top-5 left-0 whitespace-nowrap text-[9px] font-bold text-white bg-red-500 px-1.5 py-0.5 rounded shadow-sm">UNKNOWN</span>}
              </div>
            );
          }
        });
      }
    });

    windows.forEach((w: any) => {
      if (w.bounding_boxes) {
        w.bounding_boxes.forEach((box: number[], idx: number) => {
          if (box.length === 4) {
            const [ymin, xmin, ymax, xmax] = box;
            const isUnknown = w.type === 'UNKNOWN';
            boxes.push(
              <div 
                key={`window-${w.type}-${idx}`}
                title={isUnknown ? "UNKNOWN Window" : `Window Type ${w.type}`}
                className="absolute border-2 rounded-sm cursor-help transition-all"
                style={{
                  top: `${ymin * 100}%`,
                  left: `${xmin * 100}%`,
                  height: `${(ymax - ymin) * 100}%`,
                  width: `${(xmax - xmin) * 100}%`,
                  borderColor: isUnknown ? '#f59e0b' : '#34d399',
                  backgroundColor: isUnknown ? 'rgba(245, 158, 11, 0.15)' : 'rgba(52, 211, 153, 0.15)',
                  zIndex: isUnknown ? 20 : 10
                }}
              >
                {isUnknown && <span className="absolute -top-5 left-0 whitespace-nowrap text-[9px] font-bold text-white bg-amber-500 px-1.5 py-0.5 rounded shadow-sm">UNKNOWN</span>}
              </div>
            );
          }
        });
      }
    });
    
    return boxes;
  };

  if (pages.length > 0) {
    return (
      <div className="flex flex-col gap-6 rounded-2xl p-6 shadow-sm"
        style={{ background: 'var(--panel)', border: '1px solid var(--panel-border)', minHeight: 500 }}>
        {pages.map((path: string, i: number) => (
          <div key={i} className="flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold" style={{ color: 'var(--muted)' }}>
                Page {i + 1} of {pages.length}
              </span>
              <a href={imgUrl(path)} target="_blank" rel="noopener noreferrer"
                className="text-xs font-bold flex items-center gap-1 cursor-pointer hover:underline text-gradient-accent">
                🔎 Full resolution
              </a>
            </div>
            <div className="rounded-xl overflow-hidden border p-3"
              style={{ background: '#ffffff', borderColor: 'var(--panel-border)' }}>
              <div className="flex justify-center w-full">
                <div className="relative inline-block">
                  <img src={imgUrl(path)} alt={`Page ${i + 1}`} className="max-w-full block" />
                  <div className="absolute top-0 left-0 w-full h-full pointer-events-none">
                    {renderBoundingBoxes()}
                  </div>
                </div>
              </div>
            </div>
            {i < pages.length - 1 && <div className="border-b pt-3" style={{ borderColor: 'var(--panel-border)' }} />}
          </div>
        ))}
      </div>
    );
  }
  if (singlePath) {
    return (
      <div className="flex flex-col gap-3 rounded-2xl p-6 shadow-sm"
        style={{ background: 'var(--panel)', border: '1px solid var(--panel-border)' }}>
        <div className="flex justify-end">
          <a href={imgUrl(singlePath)} target="_blank" rel="noopener noreferrer"
            className="text-xs font-bold flex items-center gap-1 cursor-pointer hover:underline text-gradient-accent">
            🔎 Full resolution
          </a>
        </div>
        <div className="rounded-xl overflow-hidden border p-3"
          style={{ background: '#ffffff', borderColor: 'var(--panel-border)' }}>
          <div className="flex justify-center w-full">
            <div className="relative inline-block">
              <img src={imgUrl(singlePath)} alt="Floor Plan" className="max-w-full block" />
              <div className="absolute top-0 left-0 w-full h-full pointer-events-none">
                {renderBoundingBoxes()}
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }
  return (
    <p className="text-sm italic text-center py-16" style={{ color: 'var(--muted)' }}>
      Rendering design plan preview…
    </p>
  );
}

// ─── Status Chip ───────────────────────────────────────────────
function StatusChip({ status }: { status: string }) {
  if (status === 'completed')
    return (
      <span className="flex items-center gap-1.5 text-[10px] font-bold px-2.5 py-1 rounded-full pill-success">
        <CheckCircle2 className="w-3 h-3" /> Complete
      </span>
    );
  if (status === 'failed')
    return (
      <span className="flex items-center gap-1.5 text-[10px] font-bold px-2.5 py-1 rounded-full pill-danger">
        <AlertTriangle className="w-3 h-3" /> Failed
      </span>
    );
  return (
    <span className="flex items-center gap-1.5 text-[10px] font-bold px-2.5 py-1 rounded-full pill-warning">
      <Clock className="w-3 h-3" /> Review
    </span>
  );
}

// ─── Main TabEditor ────────────────────────────────────────────
export default function TabEditor({
  sessionId,
  sessionState,
  refreshSession,
  displayName,
  progress = 0,
  status = 'idle',
  step = ''
}: TabEditorProps) {
  const [qaForm, setQaForm] = useState<any>(null);
  const [submittingQA, setSubmittingQA] = useState(false);
  const [hasSubmittedQA, setHasSubmittedQA] = useState(false);
  const [qaError, setQaError] = useState<string | null>(null);

  const getFilename = () =>
    displayName || sessionState?.original_filename ||
    (sessionState?.uploaded_file_path || '').split(/[/\\]/).pop() || 'drawing.png';

  // Add forms
  const [newDoor, setNewDoor] = useState<Door>({ type: 'D1', width_m: 0.9, height_m: 2.1, material: 'Teak Wood', count: 1 });
  const [newWindow, setNewWindow] = useState<Window>({ type: 'W1', width_m: 1.2, height_m: 1.5, material: 'UPVC', count: 1 });

  const lastLoadedSessionId = React.useRef<string | null>(null);
  const lastLoadedStep = React.useRef<string | null>(null);
  const lastLoadedChatLen = React.useRef<number>(0);

  useEffect(() => {
    if (sessionState?.status === 'completed' || sessionState?.status === 'failed') {
      setHasSubmittedQA(false);
    }
  }, [sessionState?.status]);

  useEffect(() => {
    if (!sessionId) {
      setQaForm(null);
      setHasSubmittedQA(false);
      lastLoadedSessionId.current = null;
      lastLoadedStep.current = null;
      lastLoadedChatLen.current = 0;
      return;
    }

    let verified = sessionState?.qa_verified;
    let prefilled = sessionState?.qa_prefilled;

    console.log("DEBUG sessionState.qa_prefilled:", prefilled);
    console.log("DEBUG typeof prefilled:", typeof prefilled);

    if (typeof verified === 'string') {
      try { 
        verified = JSON.parse(verified.replace(/```json/g, '').replace(/```/g, '').trim()); 
      } catch (e) {
        console.error("Failed to parse verified:", e, verified);
      }
    }
    if (typeof prefilled === 'string') {
      try { 
        prefilled = JSON.parse(prefilled.replace(/```json/g, '').replace(/```/g, '').trim()); 
      } catch (e) {
        console.error("Failed to parse prefilled:", e, prefilled);
      }
    }

    const hasVerified = verified && typeof verified === 'object' && Object.keys(verified || {}).length > 0;
    const hasPreFilled = prefilled && typeof prefilled === 'object' && Object.keys(prefilled || {}).length > 0;
    const currentStep = sessionState?.current_step || '';
    const chatLen = sessionState?.chat_history?.length || 0;

    const isFormEmpty = !qaForm || Object.keys(qaForm).length === 0;
    const isMissingDoors = hasPreFilled && (!qaForm?.doors || qaForm.doors.length === 0) && (prefilled?.doors?.length > 0);
    const isMissingWindows = hasPreFilled && (!qaForm?.windows || qaForm.windows.length === 0) && (prefilled?.windows?.length > 0);

    const shouldLoad = 
      (lastLoadedSessionId.current !== sessionId) || 
      (isFormEmpty && (hasVerified || hasPreFilled)) ||
      isMissingDoors || 
      isMissingWindows ||
      (currentStep && currentStep !== lastLoadedStep.current && (currentStep === 'paused_qa' || currentStep === 'qa_prefilled')) ||
      (chatLen > lastLoadedChatLen.current);

    if (shouldLoad) {
      let finalForm: any = {};
      if (hasPreFilled) finalForm = JSON.parse(JSON.stringify(prefilled));
      if (hasVerified) {
        const parsedVerified = JSON.parse(JSON.stringify(verified));
        finalForm = { ...finalForm, ...parsedVerified };
        if (!parsedVerified.doors || parsedVerified.doors.length === 0) {
          finalForm.doors = prefilled?.doors || [];
        }
        if (!parsedVerified.windows || parsedVerified.windows.length === 0) {
          finalForm.windows = prefilled?.windows || [];
        }
      }
      setQaForm(finalForm);
      lastLoadedSessionId.current = sessionId;
      lastLoadedStep.current = currentStep;
      lastLoadedChatLen.current = chatLen;
    }
  }, [sessionState, sessionId]);

  const handleFieldChange = (key: string, value: any) => {
    setQaForm((prev: any) => ({ ...prev, [key]: value }));
  };

  const handleListChange = (listKey: 'doors' | 'windows', index: number, key: string, value: any) => {
    setQaForm((prev: any) => {
      const list = [...(prev?.[listKey] || [])];
      list[index] = { ...list[index], [key]: value };
      return { ...prev, [listKey]: list };
    });
  };

  const updateField = (key: string, val: any) => setQaForm((prev: any) => ({ ...prev, [key]: val }));

  const handleAddDoor = () => {
    const list = [...(qaForm?.doors || [])];
    list.push({ ...newDoor });
    updateField('doors', list);
    setNewDoor({ type: `D${list.length + 1}`, width_m: 0.9, height_m: 2.1, material: 'Teak Wood', count: 1 });
  };
  const handleRemoveDoor = (i: number) => updateField('doors', (qaForm?.doors || []).filter((_: any, idx: number) => idx !== i));
  const handleDoorChange = (i: number, k: string, v: any) => handleListChange('doors', i, k, v);

  const handleAddWindow = () => {
    const list = [...(qaForm?.windows || [])];
    list.push({ ...newWindow });
    updateField('windows', list);
    setNewWindow({ type: `W${list.length + 1}`, width_m: 1.2, height_m: 1.5, material: 'UPVC', count: 1 });
  };
  const handleRemoveWindow = (i: number) => updateField('windows', (qaForm?.windows || []).filter((_: any, idx: number) => idx !== i));
  const handleWindowChange = (i: number, k: string, v: any) => handleListChange('windows', i, k, v);

  const handleQASubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmittingQA(true);
    setHasSubmittedQA(true);
    setQaError(null);
    try {
      await api.submitQA(sessionId!, qaForm);
      refreshSession();
    } catch (err: any) {
      setQaError(err.message || 'Submission failed');
      setHasSubmittedQA(false);
    } finally {
      setSubmittingQA(false);
    }
  };

  const activeStatus = status !== 'idle' ? status : sessionState?.status;
  const activeStep = step || sessionState?.current_step || 'upload_completed';
  const activePct = progress > 0 ? progress : (sessionState?.progress_pct || 0);

  const hasPrefilledData =
    (sessionState?.qa_prefilled?.doors && sessionState.qa_prefilled.doors.length > 0) ||
    (sessionState?.qa_prefilled?.windows && sessionState.qa_prefilled.windows.length > 0) ||
    (sessionState?.qa_verified?.doors && sessionState.qa_verified.doors.length > 0) ||
    (sessionState?.qa_verified?.windows && sessionState.qa_verified.windows.length > 0);

  const isCompletedOrFailed =
    sessionState?.status === 'completed' ||
    sessionState?.status === 'failed' ||
    activeStatus === 'completed' ||
    activeStatus === 'failed';

  const isTrulyPausedQA =
    !submittingQA &&
    !hasSubmittedQA &&
    (activeStatus === 'paused_qa' || sessionState?.status === 'paused_qa') &&
    hasPrefilledData;

  const isQAStage = (isCompletedOrFailed || isTrulyPausedQA) && !submittingQA && !hasSubmittedQA;

  if (!sessionId) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-8 text-center select-none"
        style={{ background: 'var(--background)' }}>
        <div className="w-16 h-16 rounded-2xl flex items-center justify-center mb-5 bg-gradient-accent bg-opacity-10 text-white">
          <Layers className="w-8 h-8" />
        </div>
        <h3 className="text-lg font-bold" style={{ color: 'var(--foreground)' }}>No drawing selected</h3>
        <p className="text-sm mt-1 max-w-sm leading-relaxed" style={{ color: 'var(--muted)' }}>
          Select an estimation from the sidebar or upload a new floor plan to begin.
        </p>
      </div>
    );
  }

  const isPhase2Active = submittingQA || hasSubmittedQA;
  const displayPct = isPhase2Active ? Math.max(activePct, 75) : activePct;

  if (isPhase2Active || (!isQAStage && (activeStatus === 'processing' || activeStatus === 'calculating' || displayPct < 100))) {
    return <ProcessingScreen step={isPhase2Active ? 'quantities_calculated' : activeStep} pct={displayPct} />;
  }

  return (
    <div className="flex-1 flex flex-col overflow-hidden font-sans" style={{ background: 'var(--background)' }}>
      <div className="h-14 border-b flex items-center px-5 justify-between shrink-0 shadow-sm select-none"
        style={{ borderColor: 'var(--panel-border)', background: 'var(--panel)' }}>
        <span className="font-bold text-sm truncate max-w-[200px]" style={{ color: 'var(--foreground)' }}
          title={getFilename()}>
          {getFilename()}
        </span>
        <div className="shrink-0">
          <StatusChip status={sessionState?.status || 'processing'} />
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-6 selection:bg-accent/20">
        {qaForm && (
          <form onSubmit={handleQASubmit} className="w-full mx-auto flex flex-col gap-5">
            {!sessionState?.qa_verified?.project_name && (
              <div className="flex items-center gap-3 rounded-xl px-4 py-3 text-xs border border-[#8b5cf6]/20" style={{ background: 'rgba(139, 92, 246, 0.08)' }}>
                <span className="w-6 h-6 rounded-full flex items-center justify-center text-[9px] font-bold shrink-0 text-gradient-accent" style={{ background: 'rgba(139, 92, 246, 0.15)' }}>AI</span>
                <span className="flex-1" style={{ color: 'var(--foreground)' }}>
                  <strong className="text-gradient-accent">Auto-filled from OCR analysis</strong> — Review and edit values, then click Verify.
                </span>
                <button type="button" onClick={refreshSession}
                  className="flex items-center gap-1 text-[10px] font-bold px-2.5 py-1 rounded-lg cursor-pointer transition-colors shrink-0"
                  style={{ color: 'var(--accent)', border: '1px solid rgba(139,92,246,.25)' }}>
                  <RefreshCw className="w-3 h-3" /> Reload
                </button>
              </div>
            )}

            <div className="flex flex-col gap-6 bg-panel border-panel-border border rounded-2xl p-6 shadow-sm">
              <h2 className="text-lg font-bold text-foreground">Project Details</h2>
              <div className="grid grid-cols-2 gap-4">
                <div className="flex flex-col gap-1.5">
                  <label className="text-xs font-bold text-muted uppercase tracking-wider">Project Name</label>
                  <input type="text" value={qaForm.project_name || ''} onChange={e => updateField('project_name', e.target.value)} disabled={!isQAStage}
                    className="border rounded-xl px-3 py-2 text-sm bg-background border-panel-border text-foreground" />
                </div>
                <div className="flex flex-col gap-1.5">
                  <label className="text-xs font-bold text-muted uppercase tracking-wider">Sub Work Name</label>
                  <input type="text" value={qaForm.sub_work_name || ''} onChange={e => updateField('sub_work_name', e.target.value)} disabled={!isQAStage}
                    className="border rounded-xl px-3 py-2 text-sm bg-background border-panel-border text-foreground" />
                </div>
              </div>

              <h2 className="text-lg font-bold text-foreground mt-4">Doors & Windows</h2>
              <DoorsSchedule
                doors={qaForm.doors || []}
                editable={isQAStage}
                onRemove={handleRemoveDoor}
                onChange={handleDoorChange}
                onAdd={handleAddDoor}
                newDoor={newDoor}
                setNewDoor={setNewDoor}
              />

              <WindowsSchedule
                windows={qaForm.windows || []}
                editable={isQAStage}
                onRemove={handleRemoveWindow}
                onChange={handleWindowChange}
                onAdd={handleAddWindow}
                newWindow={newWindow}
                setNewWindow={setNewWindow}
              />
            </div>

            {qaError && (
              <div className="text-xs p-3.5 rounded-xl leading-snug flex items-center gap-2 pill-danger">
                <AlertTriangle className="w-4 h-4 shrink-0" /> {qaError}
              </div>
            )}

            {isQAStage ? (
              <button type="submit" disabled={submittingQA}
                className="btn-accent font-bold py-3 px-8 rounded-xl text-sm flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50 self-end">
                <Play className="w-4 h-4" />
                {submittingQA ? 'Processing Quantities…' : sessionState?.status === 'completed' ? 'Recalculate Estimate' : 'Verify & Run Estimate'}
              </button>
            ) : (
              <div className="flex items-center gap-2 font-bold text-xs px-4 py-3 rounded-xl select-none pill-success">
                <CheckCircle2 className="w-4 h-4" /> Estimation parameters verified and locked.
              </div>
            )}
          </form>
        )}
      </div>
    </div>
  );
}
