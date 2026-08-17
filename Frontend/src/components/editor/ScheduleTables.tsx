'use client';
import React from 'react';
import { Plus, Trash2, AlertTriangle, CheckCircle2 } from 'lucide-react';
import { Door, Window } from './types';

// ─── Shared tiny inline input ──────────────────────────────────
function TdInput({ value, onChange, disabled, readOnly, type = 'number', step, width = 64, placeholder }: any) {
  return (
    <input
      type={type}
      step={step}
      value={value}
      placeholder={placeholder}
      onChange={onChange}
      disabled={disabled}
      readOnly={readOnly}
      className="inline-edit-input text-center"
      style={{ width, color: 'var(--input-fg)' }}
    />
  );
}

function TdTextInput({ value, onChange, disabled, readOnly, width = '100%', minWidth = '120px', placeholder }: any) {
  return (
    <input
      type="text"
      value={value}
      placeholder={placeholder}
      onChange={onChange}
      disabled={disabled}
      readOnly={readOnly}
      className="inline-edit-input"
      style={{ width, minWidth, color: 'var(--input-fg)' }}
    />
  );
}

// ─── Review Status Badge (2nd column after MARK) ───────────────
function ReviewBadge({ needsReview }: { needsReview: boolean }) {
  if (needsReview) {
    return (
      <div
        title="This row could not be cross-verified. Please double-check the values."
        className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md text-[9px] font-bold uppercase tracking-wide cursor-help select-none"
        style={{ background: 'rgba(251,191,36,0.15)', color: '#fbbf24', border: '1px solid rgba(251,191,36,0.3)' }}
      >
        <AlertTriangle className="w-2.5 h-2.5 shrink-0" />
        Check
      </div>
    );
  }
  return (
    <div
      title="Row verified by consensus."
      className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md text-[9px] font-bold uppercase tracking-wide cursor-default select-none"
      style={{ background: 'rgba(52,211,153,0.12)', color: '#34d399', border: '1px solid rgba(52,211,153,0.2)' }}
    >
      <CheckCircle2 className="w-2.5 h-2.5 shrink-0" />
      OK
    </div>
  );
}

// ─── Shared table chrome ───────────────────────────────────────
function ScheduleTable({ headers, children }: { headers: string[]; children: React.ReactNode }) {
  return (
    <div className="overflow-x-auto rounded-xl border" style={{ borderColor: 'var(--panel-border)' }}>
      <table className="w-full text-xs text-left border-collapse">
        <thead>
          <tr className="border-b" style={{ borderColor: 'var(--panel-border)', background: 'var(--panel-header)' }}>
            {headers.map(h => (
              <th key={h} className="py-2.5 px-3 text-[10px] font-bold uppercase tracking-wide"
                style={{ color: 'var(--muted)' }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}

function ScheduleRow({ needsReview, children }: { needsReview?: boolean; children: React.ReactNode }) {
  return (
    <tr
      className="border-b group transition-colors"
      style={{
        borderColor: 'var(--panel-border)',
        // Subtly highlight rows that need review
        ...(needsReview ? { background: 'rgba(251,191,36,0.04)' } : {})
      }}
      onMouseOver={e => (e.currentTarget.style.background = needsReview ? 'rgba(251,191,36,0.09)' : 'var(--panel-header)')}
      onMouseOut={e => (e.currentTarget.style.background = needsReview ? 'rgba(251,191,36,0.04)' : 'transparent')}
    >
      {children}
    </tr>
  );
}

function EmptyRow({ colSpan, label }: { colSpan: number; label: string }) {
  return (
    <tr><td colSpan={colSpan} className="py-8 text-center text-xs italic" style={{ color: 'var(--muted)' }}>{label}</td></tr>
  );
}

// ─── Add row form ──────────────────────────────────────────────
function AddRowForm({ title, fields, onAdd, values, setValues }: {
  title: string;
  fields: { label: string; key: string; type: string; step?: number; width: number; options?: string[] }[];
  onAdd: () => void;
  values: any;
  setValues: (v: any) => void;
}) {
  return (
    <div className="flex gap-2 items-end flex-wrap p-3 rounded-xl"
      style={{ background: 'var(--background)', border: '1px solid var(--panel-border)' }}>
      <span className="text-[10px] font-bold uppercase tracking-wide w-full mb-0.5" style={{ color: 'var(--muted)' }}>
        {title}
      </span>
      {fields.map(({ label, key, type, step, width, options }) => (
        <div key={key} className="flex flex-col gap-1">
          <label className="text-[9px] uppercase font-bold" style={{ color: 'var(--muted)' }}>{label}</label>
          {options ? (
            <select value={values[key]}
              onChange={e => setValues((p: any) => ({ ...p, [key]: e.target.value }))}
              className="border rounded-lg px-2 py-1.5 text-xs focus:border-accent focus:outline-none cursor-pointer"
              style={{ width, background: 'var(--panel)', borderColor: 'var(--panel-border)', color: 'var(--foreground)' }}>
              {options.map(o => <option key={o}>{o}</option>)}
            </select>
          ) : (
            <input type={type} step={step} value={values[key]}
              onChange={e => setValues((p: any) => ({ ...p, [key]: type === 'text' ? e.target.value : parseFloat(e.target.value) || 0 }))}
              className="border rounded-lg px-2 py-1.5 text-xs focus:border-accent focus:outline-none"
              style={{ width, background: 'var(--panel)', borderColor: 'var(--panel-border)', color: 'var(--foreground)' }} />
          )}
        </div>
      ))}
      <button type="button" onClick={onAdd}
        className="btn-accent flex items-center gap-1.5 text-xs px-3.5 py-2 rounded-lg self-end">
        <Plus className="w-3.5 h-3.5" /> Add
      </button>
    </div>
  );
}

// Internal keys that should never be shown as generic text columns
// (needs_review is handled as a dedicated visual column, not a generic key)
const INTERNAL_KEYS = new Set(['mark', 'type', 'count', 'needs_review', '_schedule_type']);

/**
 * Returns an ordered list of display column keys.
 * Uses the key order from the first row (since the LLM now produces consistent
 * columns across all rows). Falls back to the union of all rows if needed.
 */
function getOrderedDisplayKeys(rows: any[]): string[] {
  if (rows.length === 0) return [];
  // Use the first row's key order as the canonical order
  const firstRowKeys = Object.keys(rows[0]).filter(k => !INTERNAL_KEYS.has(k));
  // Then add any extra keys from other rows that aren't already included
  const extraKeys = Array.from(
    new Set(rows.slice(1).flatMap(r => Object.keys(r).filter(k => !INTERNAL_KEYS.has(k))))
  ).filter(k => !firstRowKeys.includes(k));
  return [...firstRowKeys, ...extraKeys];
}

// ─── Doors Schedule ─────────────────────────────────────────
interface DoorsProps {
  doors: Door[];
  editable: boolean;
  onRemove: (idx: number) => void;
  onChange: (idx: number, key: string, value: any) => void;
  onAdd: () => void;
  newDoor: Door;
  setNewDoor: React.Dispatch<React.SetStateAction<Door>>;
}

export function DoorsSchedule({ doors, editable, onRemove, onChange, onAdd, newDoor, setNewDoor }: DoorsProps) {
  const defaultKeys = getOrderedDisplayKeys(doors);
  const [customKeys, setCustomKeys] = React.useState<string[]>([]);
  const [editingKey, setEditingKey] = React.useState<string | null>(null);
  const [editingValue, setEditingValue] = React.useState<string>('');
  const [draggedIdx, setDraggedIdx] = React.useState<number | null>(null);

  React.useEffect(() => {
    if (customKeys.length === 0 && defaultKeys.length > 0) {
      setCustomKeys(defaultKeys);
    }
  }, [doors]);

  const displayKeys = customKeys.length > 0 ? customKeys : defaultKeys;
  const totalCols = 2 + displayKeys.length + 1;

  const handleDrop = (targetIdx: number) => {
    if (draggedIdx === null || draggedIdx === targetIdx) return;
    const newKeys = [...displayKeys];
    const [movedKey] = newKeys.splice(draggedIdx, 1);
    newKeys.splice(targetIdx, 0, movedKey);
    setCustomKeys(newKeys);
    setDraggedIdx(null);

    // Reorder underlying object keys for every door row so parent state sends updated key sequence
    doors.forEach((d: any, idx: number) => {
      const copy = { ...d };
      Object.keys(d).forEach(k => {
        if (!INTERNAL_KEYS.has(k)) delete d[k];
      });
      newKeys.forEach(k => {
        d[k] = copy[k] !== undefined ? copy[k] : '';
      });
      onChange(idx, newKeys[0], d[newKeys[0]]);
    });
  };

  const deleteColumn = (keyToDelete: string) => {
    doors.forEach((d: any, idx: number) => {
      delete d[keyToDelete];
      onChange(idx, keyToDelete, undefined);
    });
    setCustomKeys(displayKeys.filter(k => k !== keyToDelete));
  };

  const renameColumn = (oldKey: string, newKey: string) => {
    if (!newKey.trim() || oldKey === newKey.trim()) {
      setEditingKey(null);
      return;
    }
    const cleanKey = newKey.trim();
    doors.forEach((d: any, idx: number) => {
      const val = d[oldKey];
      delete d[oldKey];
      onChange(idx, cleanKey, val);
    });
    setCustomKeys(displayKeys.map(k => k === oldKey ? cleanKey : k));
    setEditingKey(null);
  };

  const addColumn = () => {
    const colName = prompt('Enter new column name:');
    if (!colName || !colName.trim()) return;
    const cleanKey = colName.trim();
    if (displayKeys.includes(cleanKey)) return;
    doors.forEach((d: any, idx: number) => {
      onChange(idx, cleanKey, '');
    });
    setCustomKeys([...displayKeys, cleanKey]);
  };

  return (
    <div className="flex flex-col gap-4">
      {editable && (
        <div className="flex justify-end">
          <button
            type="button"
            onClick={addColumn}
            className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border border-accent/40 bg-accent/10 text-accent font-semibold hover:bg-accent/20 transition-all cursor-pointer"
          >
            <Plus className="w-3.5 h-3.5" /> Add Custom Column
          </button>
        </div>
      )}
      <div className="overflow-x-auto rounded-xl border" style={{ borderColor: 'var(--panel-border)' }}>
        <table className="w-full text-xs text-left border-collapse">
          <thead>
            <tr className="border-b" style={{ borderColor: 'var(--panel-border)', background: 'var(--panel-header)' }}>
              <th className="py-2.5 px-3 text-[10px] font-bold uppercase tracking-wide select-none" style={{ color: 'var(--muted)' }}>MARK</th>
              <th className="py-2.5 px-3 text-[10px] font-bold uppercase tracking-wide text-center select-none" style={{ color: 'var(--muted)' }}>REVIEW</th>
              {displayKeys.map((k, idx) => (
                <th
                  key={k}
                  draggable={editable && editingKey !== k}
                  onDragStart={() => setDraggedIdx(idx)}
                  onDragOver={e => e.preventDefault()}
                  onDrop={() => handleDrop(idx)}
                  className={`py-2.5 px-3 text-[10px] font-bold uppercase tracking-wide group relative select-none transition-all ${
                    editable ? 'cursor-grab active:cursor-grabbing hover:bg-white/5' : ''
                  }`}
                  style={{ color: 'var(--muted)' }}
                >
                  {editingKey === k ? (
                    <input
                      type="text"
                      autoFocus
                      value={editingValue}
                      onChange={e => setEditingValue(e.target.value)}
                      onBlur={() => renameColumn(k, editingValue)}
                      onKeyDown={e => {
                        if (e.key === 'Enter') renameColumn(k, editingValue);
                        if (e.key === 'Escape') setEditingKey(null);
                      }}
                      className="border rounded px-1.5 py-0.5 text-xs text-foreground bg-panel border-accent focus:outline-none w-full min-w-[80px]"
                    />
                  ) : (
                    <div className="flex items-center justify-between gap-1">
                      <span
                        title={editable ? "Double-click to rename, drag to reorder" : ""}
                        onDoubleClick={() => {
                          if (editable) {
                            setEditingKey(k);
                            setEditingValue(k);
                          }
                        }}
                        className="truncate cursor-pointer hover:text-foreground"
                      >
                        {k.toUpperCase().replace(/_/g, ' ')}
                      </span>
                      {editable && (
                        <button
                          type="button"
                          title="Delete Column"
                          onClick={(e) => { e.stopPropagation(); deleteColumn(k); }}
                          className="hidden group-hover:flex items-center justify-center text-red-400 hover:text-red-300 hover:bg-red-500/10 p-1 rounded cursor-pointer transition-all"
                        >
                          <Trash2 className="w-3.5 h-3.5 shrink-0" />
                        </button>
                      )}
                    </div>
                  )}
                </th>
              ))}
              <th className="py-2.5 px-2"></th>
            </tr>
          </thead>
          <tbody>
            {doors.length === 0 && <EmptyRow colSpan={totalCols} label="No doors added yet." />}
            {doors.map((d, idx) => {
              const needsReview = !!(d as any).needs_review;
              return (
                <ScheduleRow key={idx} needsReview={needsReview}>
                  {/* MARK */}
                  <td className="py-2.5 px-3 font-bold text-xs" style={{ color: 'var(--foreground)' }}>
                    <TdTextInput value={(d as any).mark || (d as any).type || 'Door'} readOnly={!editable} onChange={(e: any) => onChange(idx, 'mark', e.target.value)} width={80} />
                  </td>
                  {/* REVIEW status badge */}
                  <td className="py-2 px-3 text-center whitespace-nowrap">
                    <ReviewBadge needsReview={needsReview} />
                  </td>
                  {displayKeys.map(k => (
                    <td key={k} className="py-2.5 px-2">
                      <TdTextInput value={(d as any)[k] || ''} readOnly={!editable} onChange={(e: any) => {
                        const val = e.target.value;
                        const parsed = parseFloat(val);
                        const isNumberField = ['width_m', 'height_m', 'count'].includes(k);
                        onChange(idx, k, isNumberField && !isNaN(parsed) && val.trim() !== '' ? parsed : val);
                      }} />
                    </td>
                  ))}
                  <td className="py-2.5 px-2 text-center opacity-0 group-hover:opacity-100 transition-opacity">
                    {editable && (
                      <button type="button" onClick={() => onRemove(idx)}
                        className="text-red-400 hover:text-red-300 hover:bg-red-400/10 p-1.5 rounded-lg cursor-pointer transition-all">
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </td>
                </ScheduleRow>
              );
            })}
          </tbody>
        </table>
      </div>
      {editable && (
        <AddRowForm title="Add New Door" onAdd={onAdd} values={newDoor} setValues={setNewDoor}
          fields={[
            { label: 'Code', key: 'type', type: 'text', width: 80 },
            ...displayKeys.map(k => ({ label: k.toUpperCase().replace(/_/g, ' '), key: k, type: 'text', width: 100 }))
          ]} />
      )}
    </div>
  );
}

// ─── Windows Schedule ──────────────────────────────────────────
interface WindowsProps {
  windows: Window[];
  editable: boolean;
  onRemove: (idx: number) => void;
  onChange: (idx: number, key: string, value: any) => void;
  onAdd: () => void;
  newWindow: Window;
  setNewWindow: React.Dispatch<React.SetStateAction<Window>>;
}

export function WindowsSchedule({ windows, editable, onRemove, onChange, onAdd, newWindow, setNewWindow }: WindowsProps) {
  const defaultKeys = getOrderedDisplayKeys(windows);
  const [customKeys, setCustomKeys] = React.useState<string[]>([]);
  const [editingKey, setEditingKey] = React.useState<string | null>(null);
  const [editingValue, setEditingValue] = React.useState<string>('');
  const [draggedIdx, setDraggedIdx] = React.useState<number | null>(null);

  React.useEffect(() => {
    if (customKeys.length === 0 && defaultKeys.length > 0) {
      setCustomKeys(defaultKeys);
    }
  }, [windows]);

  const displayKeys = customKeys.length > 0 ? customKeys : defaultKeys;
  const totalCols = 2 + displayKeys.length + 1;

  const handleDrop = (targetIdx: number) => {
    if (draggedIdx === null || draggedIdx === targetIdx) return;
    const newKeys = [...displayKeys];
    const [movedKey] = newKeys.splice(draggedIdx, 1);
    newKeys.splice(targetIdx, 0, movedKey);
    setCustomKeys(newKeys);
    setDraggedIdx(null);

    // Reorder underlying object keys for every window row so parent state sends updated key sequence
    windows.forEach((w: any, idx: number) => {
      const copy = { ...w };
      Object.keys(w).forEach(k => {
        if (!INTERNAL_KEYS.has(k)) delete w[k];
      });
      newKeys.forEach(k => {
        w[k] = copy[k] !== undefined ? copy[k] : '';
      });
      onChange(idx, newKeys[0], w[newKeys[0]]);
    });
  };

  const deleteColumn = (keyToDelete: string) => {
    windows.forEach((w: any, idx: number) => {
      delete w[keyToDelete];
      onChange(idx, keyToDelete, undefined);
    });
    setCustomKeys(displayKeys.filter(k => k !== keyToDelete));
  };

  const renameColumn = (oldKey: string, newKey: string) => {
    if (!newKey.trim() || oldKey === newKey.trim()) {
      setEditingKey(null);
      return;
    }
    const cleanKey = newKey.trim();
    windows.forEach((w: any, idx: number) => {
      const val = w[oldKey];
      delete w[oldKey];
      onChange(idx, cleanKey, val);
    });
    setCustomKeys(displayKeys.map(k => k === oldKey ? cleanKey : k));
    setEditingKey(null);
  };

  const addColumn = () => {
    const colName = prompt('Enter new column name:');
    if (!colName || !colName.trim()) return;
    const cleanKey = colName.trim();
    if (displayKeys.includes(cleanKey)) return;
    windows.forEach((w: any, idx: number) => {
      onChange(idx, cleanKey, '');
    });
    setCustomKeys([...displayKeys, cleanKey]);
  };

  return (
    <div className="flex flex-col gap-4">
      {editable && (
        <div className="flex justify-end">
          <button
            type="button"
            onClick={addColumn}
            className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border border-accent/40 bg-accent/10 text-accent font-semibold hover:bg-accent/20 transition-all cursor-pointer"
          >
            <Plus className="w-3.5 h-3.5" /> Add Custom Column
          </button>
        </div>
      )}
      <div className="overflow-x-auto rounded-xl border" style={{ borderColor: 'var(--panel-border)' }}>
        <table className="w-full text-xs text-left border-collapse">
          <thead>
            <tr className="border-b" style={{ borderColor: 'var(--panel-border)', background: 'var(--panel-header)' }}>
              <th className="py-2.5 px-3 text-[10px] font-bold uppercase tracking-wide select-none" style={{ color: 'var(--muted)' }}>MARK</th>
              <th className="py-2.5 px-3 text-[10px] font-bold uppercase tracking-wide text-center select-none" style={{ color: 'var(--muted)' }}>REVIEW</th>
              {displayKeys.map((k, idx) => (
                <th
                  key={k}
                  draggable={editable && editingKey !== k}
                  onDragStart={() => setDraggedIdx(idx)}
                  onDragOver={e => e.preventDefault()}
                  onDrop={() => handleDrop(idx)}
                  className={`py-2.5 px-3 text-[10px] font-bold uppercase tracking-wide group relative select-none transition-all ${
                    editable ? 'cursor-grab active:cursor-grabbing hover:bg-white/5' : ''
                  }`}
                  style={{ color: 'var(--muted)' }}
                >
                  {editingKey === k ? (
                    <input
                      type="text"
                      autoFocus
                      value={editingValue}
                      onChange={e => setEditingValue(e.target.value)}
                      onBlur={() => renameColumn(k, editingValue)}
                      onKeyDown={e => {
                        if (e.key === 'Enter') renameColumn(k, editingValue);
                        if (e.key === 'Escape') setEditingKey(null);
                      }}
                      className="border rounded px-1.5 py-0.5 text-xs text-foreground bg-panel border-accent focus:outline-none w-full min-w-[80px]"
                    />
                  ) : (
                    <div className="flex items-center justify-between gap-1">
                      <span
                        title={editable ? "Double-click to rename, drag to reorder" : ""}
                        onDoubleClick={() => {
                          if (editable) {
                            setEditingKey(k);
                            setEditingValue(k);
                          }
                        }}
                        className="truncate cursor-pointer hover:text-foreground"
                      >
                        {k.toUpperCase().replace(/_/g, ' ')}
                      </span>
                      {editable && (
                        <button
                          type="button"
                          title="Delete Column"
                          onClick={(e) => { e.stopPropagation(); deleteColumn(k); }}
                          className="hidden group-hover:flex items-center justify-center text-red-400 hover:text-red-300 hover:bg-red-500/10 p-1 rounded cursor-pointer transition-all"
                        >
                          <Trash2 className="w-3.5 h-3.5 shrink-0" />
                        </button>
                      )}
                    </div>
                  )}
                </th>
              ))}
              <th className="py-2.5 px-2"></th>
            </tr>
          </thead>
          <tbody>
            {windows.length === 0 && <EmptyRow colSpan={totalCols} label="No windows added yet." />}
            {windows.map((w, idx) => {
              const needsReview = !!(w as any).needs_review;
              return (
                <ScheduleRow key={idx} needsReview={needsReview}>
                  {/* MARK */}
                  <td className="py-2.5 px-3 font-bold text-xs" style={{ color: 'var(--foreground)' }}>
                    <TdTextInput value={(w as any).mark || (w as any).type || 'Window'} readOnly={!editable} onChange={(e: any) => onChange(idx, 'mark', e.target.value)} width={80} />
                  </td>
                  {/* REVIEW status badge */}
                  <td className="py-2 px-3 text-center whitespace-nowrap">
                    <ReviewBadge needsReview={needsReview} />
                  </td>
                  {displayKeys.map(k => (
                    <td key={k} className="py-2.5 px-2">
                      <TdTextInput value={(w as any)[k] || ''} readOnly={!editable} onChange={(e: any) => {
                        const val = e.target.value;
                        const parsed = parseFloat(val);
                        const isNumberField = ['width_m', 'height_m', 'count'].includes(k);
                        onChange(idx, k, isNumberField && !isNaN(parsed) && val.trim() !== '' ? parsed : val);
                      }} />
                    </td>
                  ))}
                  <td className="py-2.5 px-2 text-center opacity-0 group-hover:opacity-100 transition-opacity">
                    {editable && (
                      <button type="button" onClick={() => onRemove(idx)}
                        className="text-red-400 hover:text-red-300 hover:bg-red-400/10 p-1.5 rounded-lg cursor-pointer transition-all">
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </td>
                </ScheduleRow>
              );
            })}
          </tbody>
        </table>
      </div>
      {editable && (
        <AddRowForm title="Add New Window" onAdd={onAdd} values={newWindow} setValues={setNewWindow}
          fields={[
            { label: 'Code', key: 'type', type: 'text', width: 80 },
            ...displayKeys.map(k => ({ label: k.toUpperCase().replace(/_/g, ' '), key: k, type: 'text', width: 100 }))
          ]} />
      )}
    </div>
  );
}
