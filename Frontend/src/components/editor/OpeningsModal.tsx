'use client';
import React from 'react';
import { X, Plus, Trash2, DoorOpen } from 'lucide-react';
import { Room } from './types';

interface OpeningsModalProps {
  room: Room;
  modal: 'doors' | 'windows';
  floorIdx: number;
  roomIdx: number;
  editable: boolean;
  onClose: () => void;
  onAddDoor: (floorIdx: number, roomIdx: number) => void;
  onRemoveDoor: (floorIdx: number, roomIdx: number, doorIdx: number) => void;
  onDoorChange: (floorIdx: number, roomIdx: number, doorIdx: number, key: string, value: any) => void;
  onAddWindow: (floorIdx: number, roomIdx: number) => void;
  onRemoveWindow: (floorIdx: number, roomIdx: number, winIdx: number) => void;
  onWindowChange: (floorIdx: number, roomIdx: number, winIdx: number, key: string, value: any) => void;
}

function FieldLabel({ children }: { children: React.ReactNode }) {
  return <label className="field-label block mb-1">{children}</label>;
}

function SmallInput({ value, onChange, disabled, type = 'number', step, width }: any) {
  return (
    <input
      type={type}
      step={step}
      value={value}
      disabled={disabled}
      onChange={onChange}
      className="bg-bg border border-border rounded-lg px-2.5 py-1.5 text-xs focus:border-accent focus:outline-none w-full"
      style={width ? { width } : undefined}
    />
  );
}

function SmallSelect({ value, onChange, disabled, options }: any) {
  return (
    <select
      value={value}
      disabled={disabled}
      onChange={onChange}
      className="bg-bg border border-border rounded-lg px-2.5 py-1.5 text-xs focus:border-accent focus:outline-none w-full cursor-pointer"
    >
      {options.map((o: string) => <option key={o}>{o}</option>)}
    </select>
  );
}

export default function OpeningsModal({
  room, modal, floorIdx, roomIdx, editable, onClose,
  onAddDoor, onRemoveDoor, onDoorChange,
  onAddWindow, onRemoveWindow, onWindowChange,
}: OpeningsModalProps) {
  const isDoors = modal === 'doors';
  const items = isDoors ? (room.doors || []) : (room.windows || []);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgba(0,0,0,0.65)', backdropFilter: 'blur(6px)' }}>

      <div className="w-full max-w-2xl max-h-[88vh] flex flex-col rounded-2xl shadow-2xl animate-scale-in"
        style={{ background: 'var(--panel)', border: '1px solid var(--panel-border)' }}>

        {/* ── Header ── */}
        <div className="flex items-center justify-between px-6 py-4 border-b shrink-0"
          style={{ borderColor: 'var(--panel-border)', background: 'var(--panel-header)' }}>
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl flex items-center justify-center text-lg"
              className="bg-gradient-accent bg-opacity-10 text-white">
              {isDoors ? '🚪' : '🪟'}
            </div>
            <div>
              <h3 className="font-bold text-sm" style={{ color: 'var(--foreground)' }}>
                {isDoors ? 'Doors' : 'Windows'} — <span className="text-gradient-accent">{room.name}</span>
              </h3>
              <p className="text-[11px] mt-0.5" style={{ color: 'var(--muted)' }}>
                {items.length} {isDoors ? 'door' : 'window'} spec(s) configured
              </p>
            </div>
          </div>
          <button onClick={onClose}
            className="w-8 h-8 flex items-center justify-center rounded-xl transition-all cursor-pointer"
            style={{ color: 'var(--muted)' }}
            onMouseOver={e => (e.currentTarget.style.background = 'var(--panel-header)')}
            onMouseOut={e => (e.currentTarget.style.background = 'transparent')}>
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* ── Body ── */}
        <div className="flex-1 overflow-y-auto p-5 flex flex-col gap-3">

          {/* Action bar */}
          <div className="flex items-center justify-between mb-1">
            <p className="text-xs font-semibold" style={{ color: 'var(--label)' }}>
              {isDoors ? 'Door profiles for this room' : 'Window & ventilator profiles'}
            </p>
            {editable && (
              <button type="button"
                onClick={() => isDoors ? onAddDoor(floorIdx, roomIdx) : onAddWindow(floorIdx, roomIdx)}
                className="btn-accent flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg">
                <Plus className="w-3.5 h-3.5" />
                {isDoors ? 'Add Door' : 'Add Window'}
              </button>
            )}
          </div>

          {/* Empty state */}
          {items.length === 0 && (
            <div className="flex flex-col items-center justify-center py-12 gap-3 rounded-xl"
              style={{ background: 'var(--panel-header)', border: '1px dashed var(--panel-border)' }}>
              <span className="text-3xl opacity-30">{isDoors ? '🚪' : '🪟'}</span>
              <p className="text-xs" style={{ color: 'var(--muted)' }}>
                No {isDoors ? 'doors' : 'windows'} configured yet.
                {editable && ' Use the button above to add one.'}
              </p>
            </div>
          )}

          {/* Doors */}
          {isDoors && (room.doors || []).map((door, dIdx) => (
            <div key={dIdx} className="rounded-xl p-4 flex flex-wrap gap-3 items-end"
              style={{ background: 'var(--panel-header)', border: '1px solid var(--panel-border)' }}>
              <div className="w-8 h-8 rounded-xl flex items-center justify-center text-xs font-extrabold shrink-0"
                className="bg-gradient-accent bg-opacity-10 text-white">
                D{dIdx + 1}
              </div>

              <div className="flex flex-col gap-0.5 w-16">
                <FieldLabel>Width m</FieldLabel>
                <SmallInput value={door.width_m} step={0.01} disabled={!editable}
                  onChange={(e: any) => onDoorChange(floorIdx, roomIdx, dIdx, 'width_m', parseFloat(e.target.value) || 0)} />
              </div>
              <div className="flex flex-col gap-0.5 w-16">
                <FieldLabel>Height m</FieldLabel>
                <SmallInput value={door.height_m} step={0.01} disabled={!editable}
                  onChange={(e: any) => onDoorChange(floorIdx, roomIdx, dIdx, 'height_m', parseFloat(e.target.value) || 0)} />
              </div>
              <div className="flex flex-col gap-0.5 flex-1 min-w-[100px]">
                <FieldLabel>Shutter Material</FieldLabel>
                <SmallInput type="text" value={door.material} disabled={!editable}
                  onChange={(e: any) => onDoorChange(floorIdx, roomIdx, dIdx, 'material', e.target.value)} />
              </div>
              <div className="flex flex-col gap-0.5 w-28">
                <FieldLabel>Frame Type</FieldLabel>
                <SmallSelect value={door.frame_type} disabled={!editable}
                  options={['Teak Wood', 'Granite', 'RCC']}
                  onChange={(e: any) => onDoorChange(floorIdx, roomIdx, dIdx, 'frame_type', e.target.value)} />
              </div>
              <div className="flex flex-col gap-0.5 w-14">
                <FieldLabel>Count</FieldLabel>
                <SmallInput value={door.count} type="number" disabled={!editable} width={56}
                  onChange={(e: any) => onDoorChange(floorIdx, roomIdx, dIdx, 'count', parseInt(e.target.value) || 1)} />
              </div>
              {editable && (
                <button type="button" onClick={() => onRemoveDoor(floorIdx, roomIdx, dIdx)}
                  className="p-2 rounded-lg cursor-pointer transition-all text-red-400 hover:text-red-300 hover:bg-red-500/10">
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          ))}

          {/* Windows */}
          {!isDoors && (room.windows || []).map((win, wIdx) => (
            <div key={wIdx} className="rounded-xl p-4 flex flex-wrap gap-3 items-end"
              style={{ background: 'var(--panel-header)', border: '1px solid var(--panel-border)' }}>
              <div className="w-8 h-8 rounded-xl flex items-center justify-center text-xs font-extrabold shrink-0"
                className="bg-gradient-accent bg-opacity-10 text-white">
                W{wIdx + 1}
              </div>

              <div className="flex flex-col gap-0.5 w-16">
                <FieldLabel>Width m</FieldLabel>
                <SmallInput value={win.width_m} step={0.01} disabled={!editable}
                  onChange={(e: any) => onWindowChange(floorIdx, roomIdx, wIdx, 'width_m', parseFloat(e.target.value) || 0)} />
              </div>
              <div className="flex flex-col gap-0.5 w-16">
                <FieldLabel>Height m</FieldLabel>
                <SmallInput value={win.height_m} step={0.01} disabled={!editable}
                  onChange={(e: any) => onWindowChange(floorIdx, roomIdx, wIdx, 'height_m', parseFloat(e.target.value) || 0)} />
              </div>
              <div className="flex flex-col gap-0.5 flex-1 min-w-[80px]">
                <FieldLabel>Material</FieldLabel>
                <SmallInput type="text" value={win.material} disabled={!editable}
                  onChange={(e: any) => onWindowChange(floorIdx, roomIdx, wIdx, 'material', e.target.value)} />
              </div>
              <div className="flex flex-col gap-0.5 w-28">
                <FieldLabel>Grills / Gate</FieldLabel>
                <SmallSelect value={win.has_grill_or_gate} disabled={!editable}
                  options={['Grill', 'Channel Gate', 'None']}
                  onChange={(e: any) => onWindowChange(floorIdx, roomIdx, wIdx, 'has_grill_or_gate', e.target.value)} />
              </div>

              {/* Sill & Jamb toggle */}
              <div className="flex items-center gap-2 pb-1.5">
                <input type="checkbox" id={`jam-${wIdx}`} checked={win.has_seal_jam} disabled={!editable}
                  onChange={e => onWindowChange(floorIdx, roomIdx, wIdx, 'has_seal_jam', e.target.checked)}
                  className="w-4 h-4 cursor-pointer accent-accent" />
                <label htmlFor={`jam-${wIdx}`} className="text-xs font-semibold cursor-pointer select-none" style={{ color: 'var(--label)' }}>
                  Sill &amp; Jamb
                </label>
              </div>
              {win.has_seal_jam && (
                <>
                  <div className="flex flex-col gap-0.5 w-20">
                    <FieldLabel>Sill Width m</FieldLabel>
                    <SmallInput value={win.sill_width_m ?? win.seal_jam_width_m ?? 0.1} step={0.01} disabled={!editable} width={80}
                      onChange={(e: any) => onWindowChange(floorIdx, roomIdx, wIdx, 'sill_width_m', parseFloat(e.target.value) || 0)} />
                  </div>
                  <div className="flex flex-col gap-0.5 w-20">
                    <FieldLabel>Jamb Width m</FieldLabel>
                    <SmallInput value={win.jamb_width_m ?? win.seal_jam_width_m ?? 0.15} step={0.01} disabled={!editable} width={80}
                      onChange={(e: any) => onWindowChange(floorIdx, roomIdx, wIdx, 'jamb_width_m', parseFloat(e.target.value) || 0)} />
                  </div>
                </>
              )}
              <div className="flex flex-col gap-0.5 w-12">
                <FieldLabel>Qty</FieldLabel>
                <SmallInput value={win.count} type="number" disabled={!editable} width={48}
                  onChange={(e: any) => onWindowChange(floorIdx, roomIdx, wIdx, 'count', parseInt(e.target.value) || 1)} />
              </div>
              {editable && (
                <button type="button" onClick={() => onRemoveWindow(floorIdx, roomIdx, wIdx)}
                  className="p-2 rounded-lg cursor-pointer transition-all text-red-400 hover:text-red-300 hover:bg-red-500/10">
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          ))}
        </div>

        {/* ── Footer ── */}
        <div className="px-6 py-4 border-t flex justify-end shrink-0"
          style={{ borderColor: 'var(--panel-border)', background: 'var(--panel-header)' }}>
          <button type="button" onClick={onClose}
            className="font-bold text-sm px-6 py-2 rounded-xl transition-all cursor-pointer"
            className="bg-gradient-accent text-white">
            Done
          </button>
        </div>
      </div>
    </div>
  );
}
