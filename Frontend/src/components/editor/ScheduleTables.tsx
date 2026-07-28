'use client';
import React from 'react';
import { Plus, Trash2 } from 'lucide-react';
import { Door, Window } from './types';

// ─── Shared tiny inline input ──────────────────────────────────
function TdInput({ value, onChange, disabled, type = 'number', step, width = 64, placeholder }: any) {
  return (
    <input
      type={type}
      step={step}
      value={value}
      placeholder={placeholder}
      onChange={onChange}
      disabled={disabled}
      className="inline-edit-input text-center"
      style={{ width, color: 'var(--input-fg)' }}
    />
  );
}

function TdTextInput({ value, onChange, disabled, width = 80, placeholder }: any) {
  return (
    <input
      type="text"
      value={value}
      placeholder={placeholder}
      onChange={onChange}
      disabled={disabled}
      className="inline-edit-input"
      style={{ width, color: 'var(--input-fg)' }}
    />
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
              <th key={h} className="py-2.5 px-3 text-[10px] font-bold uppercase tracking-wide select-none"
                style={{ color: 'var(--muted)' }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}

function ScheduleRow({ children }: { children: React.ReactNode }) {
  return (
    <tr className="border-b group transition-colors"
      style={{ borderColor: 'var(--panel-border)' }}
      onMouseOver={e => (e.currentTarget.style.background = 'var(--panel-header)')}
      onMouseOut={e => (e.currentTarget.style.background = 'transparent')}>
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
  return (
    <div className="flex flex-col gap-4">
      <ScheduleTable headers={['Code', 'Width m', 'Height m', 'Material', 'Count', '']}>
        {doors.length === 0 && <EmptyRow colSpan={6} label="No doors added yet." />}
        {doors.map((d, idx) => (
          <ScheduleRow key={idx}>
            <td className="py-2.5 px-3 font-bold text-xs" style={{ color: 'var(--foreground)' }}><TdTextInput value={d.type || 'Door'} disabled={!editable} onChange={(e: any) => onChange(idx, 'type', e.target.value)} /></td>
            <td className="py-2.5 px-2"><TdInput value={d.width_m} step={0.01} disabled={!editable} onChange={(e: any) => onChange(idx, 'width_m', parseFloat(e.target.value) || 0)} /></td>
            <td className="py-2.5 px-2"><TdInput value={d.height_m} step={0.01} disabled={!editable} onChange={(e: any) => onChange(idx, 'height_m', parseFloat(e.target.value) || 0)} /></td>
            <td className="py-2.5 px-2"><TdTextInput value={d.material || d.frame_material || 'Teak'} disabled={!editable} onChange={(e: any) => onChange(idx, 'material', e.target.value)} /></td>
            <td className="py-2.5 px-2"><TdInput value={d.count} disabled={!editable} onChange={(e: any) => onChange(idx, 'count', parseInt(e.target.value) || 0)} /></td>
            <td className="py-2.5 px-2 text-center opacity-0 group-hover:opacity-100 transition-opacity">
              {editable && (
                <button type="button" onClick={() => onRemove(idx)}
                  className="text-red-400 hover:text-red-300 hover:bg-red-400/10 p-1.5 rounded-lg cursor-pointer transition-all">
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              )}
            </td>
          </ScheduleRow>
        ))}
      </ScheduleTable>
      {editable && (
        <AddRowForm title="Add New Door" onAdd={onAdd} values={newDoor} setValues={setNewDoor}
          fields={[
            { label: 'Code', key: 'type', type: 'text', width: 80 },
            { label: 'Width m', key: 'width_m', type: 'number', step: 0.1, width: 70 },
            { label: 'Height m', key: 'height_m', type: 'number', step: 0.1, width: 70 },
            { label: 'Material', key: 'material', type: 'text', width: 100 },
            { label: 'Count', key: 'count', type: 'number', width: 60 },
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
  return (
    <div className="flex flex-col gap-4">
      <ScheduleTable headers={['Code', 'Width m', 'Height m', 'Material', 'Count', '']}>
        {windows.length === 0 && <EmptyRow colSpan={6} label="No windows added yet." />}
        {windows.map((w, idx) => (
          <ScheduleRow key={idx}>
            <td className="py-2.5 px-3 font-bold text-xs" style={{ color: 'var(--foreground)' }}><TdTextInput value={w.type || 'Window'} disabled={!editable} onChange={(e: any) => onChange(idx, 'type', e.target.value)} /></td>
            <td className="py-2.5 px-2"><TdInput value={w.width_m} step={0.01} disabled={!editable} onChange={(e: any) => onChange(idx, 'width_m', parseFloat(e.target.value) || 0)} /></td>
            <td className="py-2.5 px-2"><TdInput value={w.height_m} step={0.01} disabled={!editable} onChange={(e: any) => onChange(idx, 'height_m', parseFloat(e.target.value) || 0)} /></td>
            <td className="py-2.5 px-2"><TdTextInput value={w.material || 'UPVC'} disabled={!editable} onChange={(e: any) => onChange(idx, 'material', e.target.value)} /></td>
            <td className="py-2.5 px-2"><TdInput value={w.count} disabled={!editable} onChange={(e: any) => onChange(idx, 'count', parseInt(e.target.value) || 0)} /></td>
            <td className="py-2.5 px-2 text-center opacity-0 group-hover:opacity-100 transition-opacity">
              {editable && (
                <button type="button" onClick={() => onRemove(idx)}
                  className="text-red-400 hover:text-red-300 hover:bg-red-400/10 p-1.5 rounded-lg cursor-pointer transition-all">
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              )}
            </td>
          </ScheduleRow>
        ))}
      </ScheduleTable>
      {editable && (
        <AddRowForm title="Add New Window" onAdd={onAdd} values={newWindow} setValues={setNewWindow}
          fields={[
            { label: 'Code', key: 'type', type: 'text', width: 80 },
            { label: 'Width m', key: 'width_m', type: 'number', step: 0.1, width: 70 },
            { label: 'Height m', key: 'height_m', type: 'number', step: 0.1, width: 70 },
            { label: 'Material', key: 'material', type: 'text', width: 100 },
            { label: 'Count', key: 'count', type: 'number', width: 60 },
          ]} />
      )}
    </div>
  );
}
