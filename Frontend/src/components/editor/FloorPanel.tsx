'use client';
import React from 'react';
import { Plus, Trash2, Building2, ChevronRight, ChevronLeft } from 'lucide-react';
import { Floor, Room } from './types';

const ROOM_TYPES = ['Room', 'Bedroom', 'Kitchen', 'Toilet', 'Balcony', 'Hall', 'Lobby', 'Store', 'Drawing Room', 'Pooja Room'];
const TILE_TYPES  = ['Normal tiles', 'Marble', 'Granite', 'Ceramic', 'None'];
const RAILING_TYPES = ['None', 'Brick', 'Glass', 'MS', 'Stainless Steel'];

// ─── Room Card ─────────────────────────────────────────────────
interface RoomRowProps {
  room: Room;
  floorIdx: number;
  roomIdx: number;
  editable: boolean;
  onFieldChange: (fi: number, ri: number, key: string, value: any) => void;
  onRemove: (fi: number, ri: number) => void;
  onOpenDoors: () => void;
  onOpenWindows: () => void;
}

function RoomRow({ room, floorIdx, roomIdx, editable, onFieldChange, onRemove, onOpenDoors, onOpenWindows }: RoomRowProps) {
  return (
    <tr className="group border-b transition-colors"
      style={{ borderColor: 'var(--panel-border)' }}
      onMouseOver={e => (e.currentTarget.style.background = 'var(--panel-header)')}
      onMouseOut={e => (e.currentTarget.style.background = 'transparent')}>

      {/* Name */}
      <td className="py-3 px-4">
        <input type="text" value={room.name || ''} disabled={!editable}
          onChange={e => onFieldChange(floorIdx, roomIdx, 'name', e.target.value)}
          className="inline-edit-input font-semibold w-24" style={{ color: 'var(--foreground)' }} />
      </td>

      {/* Type */}
      <td className="py-3 px-2">
        <select value={room.type} disabled={!editable}
          onChange={e => onFieldChange(floorIdx, roomIdx, 'type', e.target.value)}
          className="border rounded-lg px-2 py-1 text-xs cursor-pointer focus:outline-none w-32"
          style={{ borderColor: 'var(--panel-border)', background: 'var(--panel)', color: 'var(--foreground)' }}>
          {ROOM_TYPES.map(t => <option key={t}>{t}</option>)}
        </select>
      </td>

      {/* Shape */}
      <td className="py-3 px-2">
        <select value={room.is_regular ? 'Regular' : 'Irregular'} disabled={!editable}
          onChange={e => onFieldChange(floorIdx, roomIdx, 'is_regular', e.target.value === 'Regular')}
          className="border rounded-lg px-2 py-1 text-xs cursor-pointer focus:outline-none"
          style={{ borderColor: 'var(--panel-border)', background: 'var(--panel)', color: 'var(--foreground)' }}>
          <option>Regular</option>
          <option>Irregular</option>
        </select>
      </td>

      {/* Dimensions */}
      <td className="py-3 px-2">
        <div className="flex items-center gap-0.5">
          {(['length_m', 'width_m', 'height_m'] as const).map((key, i) => (
            <React.Fragment key={key}>
              {i > 0 && <span className="text-[10px] font-bold px-0.5" style={{ color: 'var(--muted)' }}>×</span>}
              <input type="number" step="0.01" value={(room as any)[key] ?? ''} disabled={!editable}
                onChange={e => onFieldChange(floorIdx, roomIdx, key, parseFloat(e.target.value) || 0)}
                className="inline-edit-input text-center" style={{ width: 44, color: 'var(--foreground)' }} />
            </React.Fragment>
          ))}
        </div>
      </td>

      {/* Openings */}
      <td className="py-3 px-2">
        <div className="flex gap-1.5">
          <button type="button" onClick={onOpenDoors}
            className="flex items-center gap-1 text-[10px] font-bold px-2.5 py-1.5 rounded-lg border cursor-pointer transition-all"
            style={{ background: 'var(--panel)', borderColor: 'var(--panel-border)', color: 'var(--foreground)' }}
            onMouseOver={e => { e.currentTarget.style.borderColor = 'var(--accent)'; e.currentTarget.style.color = 'var(--accent)'; }}
            onMouseOut={e => { e.currentTarget.style.borderColor = 'var(--panel-border)'; e.currentTarget.style.color = 'var(--foreground)'; }}>
            🚪 <span className="font-mono">{room.doors?.length || 0}</span>
          </button>
          <button type="button" onClick={onOpenWindows}
            className="flex items-center gap-1 text-[10px] font-bold px-2.5 py-1.5 rounded-lg border cursor-pointer transition-all"
            style={{ background: 'var(--panel)', borderColor: 'var(--panel-border)', color: 'var(--foreground)' }}
            onMouseOver={e => { e.currentTarget.style.borderColor = 'var(--accent)'; e.currentTarget.style.color = 'var(--accent)'; }}
            onMouseOut={e => { e.currentTarget.style.borderColor = 'var(--panel-border)'; e.currentTarget.style.color = 'var(--foreground)'; }}>
            🪟 <span className="font-mono">{room.windows?.length || 0}</span>
          </button>
        </div>
      </td>

      {/* Flooring */}
      <td className="py-3 px-2">
        {room.tiles_enabled ? (
          <select value={room.tiles_type} disabled={!editable}
            onChange={e => onFieldChange(floorIdx, roomIdx, 'tiles_type', e.target.value)}
            className="border rounded-lg px-2 py-1 text-xs cursor-pointer focus:outline-none w-24"
            style={{ borderColor: 'var(--panel-border)', background: 'var(--panel)', color: 'var(--foreground)' }}>
            {TILE_TYPES.map(t => <option key={t}>{t}</option>)}
          </select>
        ) : (
          <button type="button" disabled={!editable}
            onClick={() => onFieldChange(floorIdx, roomIdx, 'tiles_enabled', true)}
            className="text-[10px] font-semibold hover:underline disabled:opacity-30 cursor-pointer text-gradient-accent">
            + Add
          </button>
        )}
      </td>

      {/* PUP Ceiling */}
      <td className="py-3 px-3 text-center">
        <input type="checkbox" checked={!!room.pup_fall_ceiling} disabled={!editable}
          onChange={e => onFieldChange(floorIdx, roomIdx, 'pup_fall_ceiling', e.target.checked)}
          className="w-4 h-4 cursor-pointer accent-accent" />
      </td>

      {/* Skirting Height */}
      <td className="py-3 px-2">
        <input type="number" step="0.01" value={room.skirting_height_m ?? 0.1}
          disabled={!editable}
          onChange={e => onFieldChange(floorIdx, roomIdx, 'skirting_height_m', parseFloat(e.target.value) || 0)}
          className="inline-edit-input text-center" style={{ width: 52, color: 'var(--foreground)' }} />
      </td>

      {/* Dado */}
      <td className="py-3 px-2">
        <input type="number" step="0.1" value={room.dado_height_m ?? 0}
          disabled={!editable || !(room.type === 'Toilet' || room.type === 'Kitchen')}
          onChange={e => onFieldChange(floorIdx, roomIdx, 'dado_height_m', parseFloat(e.target.value) || 0)}
          className="inline-edit-input text-center disabled:opacity-25" style={{ width: 48, color: 'var(--foreground)' }} />
      </td>

      {/* Railing */}
      <td className="py-3 px-2">
        <div className="flex flex-col gap-1">
          <select value={room.railing_material} disabled={!editable}
            onChange={e => onFieldChange(floorIdx, roomIdx, 'railing_material', e.target.value)}
            className="border rounded-lg px-2 py-1 text-[11px] cursor-pointer focus:outline-none"
            style={{ borderColor: 'var(--panel-border)', background: 'var(--panel)', color: 'var(--foreground)' }}>
            {RAILING_TYPES.map(r => <option key={r}>{r}</option>)}
          </select>
          {room.railing_material !== 'None' && (
            <input type="number" step="0.1" value={room.railing_length_m || ''} placeholder="len m" disabled={!editable}
              onChange={e => onFieldChange(floorIdx, roomIdx, 'railing_length_m', parseFloat(e.target.value) || null)}
              className="inline-edit-input text-center text-[10px]" style={{ width: 60, color: 'var(--foreground)' }} />
          )}
        </div>
      </td>



      {/* Delete */}
      <td className="py-3 px-2 text-center opacity-0 group-hover:opacity-100 transition-opacity">
        {editable && (
          <button type="button" onClick={() => onRemove(floorIdx, roomIdx)}
            className="text-red-400 hover:text-red-300 hover:bg-red-400/10 p-1.5 rounded-lg cursor-pointer transition-all">
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        )}
      </td>
    </tr>
  );
}

// ─── Staircase & Midlanding Cards ──────────────────────────────
function StaircaseMidlandingCards({ floor, floorIdx, editable, onToggleStaircase, onToggleMidlanding, onNestedChange }: {
  floor: Floor; floorIdx: number; editable: boolean;
  onToggleStaircase: (fi: number, e: boolean) => void;
  onToggleMidlanding: (fi: number, e: boolean) => void;
  onNestedChange: (fi: number, pk: 'staircase' | 'midlanding', k: string, v: any) => void;
}) {
  const cardStyle = {
    background: 'var(--panel)',
    border: '1px solid var(--panel-border)',
    borderRadius: 16,
  };
  const selectStyle = {
    background: 'var(--background)',
    border: '1px solid var(--panel-border)',
    color: 'var(--foreground)',
    borderRadius: 8,
    padding: '6px 10px',
    fontSize: '0.75rem',
    cursor: 'pointer',
  };

  return (
    <div className="grid grid-cols-2 gap-4">
      {/* Staircase */}
      <div className="flex flex-col gap-4 p-5" style={cardStyle}>
        <div className="flex justify-between items-center">
          <span className="section-label">Staircase</span>
          <select value={floor.staircase ? 'Yes' : 'No'} disabled={!editable}
            onChange={e => onToggleStaircase(floorIdx, e.target.value === 'Yes')}
            style={selectStyle}>
            <option value="No">No Staircase</option>
            <option value="Yes">Has Staircase</option>
          </select>
        </div>
        {floor.staircase && (
          <div className="grid grid-cols-2 gap-3 animate-fade-in">
            {[
              { label: 'Step Count', key: 'step_count', type: 'number' },
              { label: 'Tread Run m', key: 'tread_m', type: 'number', step: 0.01 },
              { label: 'Rise Height m', key: 'rise_m', type: 'number', step: 0.01 },
            ].map(({ label, key, type, step }) => (
              <div key={key} className="flex flex-col gap-1">
                <label className="field-label">{label}</label>
                <input type={type} step={step} value={(floor.staircase as any)[key]} disabled={!editable}
                  onChange={e => onNestedChange(floorIdx, 'staircase', key, type === 'number' ? parseFloat(e.target.value) || 0 : e.target.value)}
                  className="border rounded-lg px-2.5 py-2 text-xs focus:border-accent focus:outline-none"
                  style={{ background: 'var(--background)', borderColor: 'var(--panel-border)', color: 'var(--foreground)' }} />
              </div>
            ))}
            <div className="flex flex-col gap-1">
              <label className="field-label">Tread Finish Material</label>
              <select value={floor.staircase.tread_material || floor.staircase.material || 'Granite'} disabled={!editable}
                onChange={e => {
                  onNestedChange(floorIdx, 'staircase', 'tread_material', e.target.value);
                  onNestedChange(floorIdx, 'staircase', 'material', e.target.value);
                }}
                className="border rounded-lg px-2.5 py-2 text-xs focus:outline-none cursor-pointer"
                style={{ background: 'var(--background)', borderColor: 'var(--panel-border)', color: 'var(--foreground)' }}>
                {['Ceramic', 'Granite', 'Marble'].map(m => <option key={m}>{m}</option>)}
              </select>
            </div>
            <div className="flex flex-col gap-1">
              <label className="field-label">Riser Finish Material</label>
              <select value={floor.staircase.rise_material || floor.staircase.material || 'Granite'} disabled={!editable}
                onChange={e => onNestedChange(floorIdx, 'staircase', 'rise_material', e.target.value)}
                className="border rounded-lg px-2.5 py-2 text-xs focus:outline-none cursor-pointer"
                style={{ background: 'var(--background)', borderColor: 'var(--panel-border)', color: 'var(--foreground)' }}>
                {['Ceramic', 'Granite', 'Marble'].map(m => <option key={m}>{m}</option>)}
              </select>
            </div>
          </div>
        )}
      </div>

      {/* Midlanding */}
      <div className="flex flex-col gap-4 p-5" style={cardStyle}>
        <div className="flex justify-between items-center">
          <span className="section-label">Midlanding</span>
          <select value={floor.midlanding ? 'Yes' : 'No'} disabled={!editable}
            onChange={e => onToggleMidlanding(floorIdx, e.target.value === 'Yes')}
            style={selectStyle}>
            <option value="No">No Midlanding</option>
            <option value="Yes">Has Midlanding</option>
          </select>
        </div>
        {floor.midlanding && (
          <div className="grid grid-cols-2 gap-3 animate-fade-in">
            {[
              { label: 'Length m', key: 'length_m', step: 0.05 },
              { label: 'Width m', key: 'width_m', step: 0.05 },
            ].map(({ label, key, step }) => (
              <div key={key} className="flex flex-col gap-1">
                <label className="field-label">{label}</label>
                <input type="number" step={step} value={(floor.midlanding as any)[key]} disabled={!editable}
                  onChange={e => onNestedChange(floorIdx, 'midlanding', key, parseFloat(e.target.value) || 0)}
                  className="border rounded-lg px-2.5 py-2 text-xs focus:border-accent focus:outline-none"
                  style={{ background: 'var(--background)', borderColor: 'var(--panel-border)', color: 'var(--foreground)' }} />
              </div>
            ))}
            <div className="flex flex-col gap-1 col-span-2">
              <label className="field-label">Finish Material</label>
              <select value={floor.midlanding.material} disabled={!editable}
                onChange={e => onNestedChange(floorIdx, 'midlanding', 'material', e.target.value)}
                className="border rounded-lg px-2.5 py-2 text-xs focus:outline-none cursor-pointer"
                style={{ background: 'var(--background)', borderColor: 'var(--panel-border)', color: 'var(--foreground)' }}>
                {['Ceramic', 'Granite', 'Marble'].map(m => <option key={m}>{m}</option>)}
              </select>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Floor Panel ───────────────────────────────────────────────
interface FloorPanelProps {
  floors: Floor[];
  activeFloorIdx: number;
  setActiveFloorIdx: (idx: number) => void;
  editable: boolean;
  onAddRoom: (fi: number) => void;
  onRemoveRoom: (fi: number, ri: number) => void;
  onRoomFieldChange: (fi: number, ri: number, key: string, value: any) => void;
  onToggleStaircase: (fi: number, e: boolean) => void;
  onToggleMidlanding: (fi: number, e: boolean) => void;
  onFloorNestedChange: (fi: number, pk: 'staircase' | 'midlanding', k: string, v: any) => void;
  onReplicateFloor: (src: number, targetsStr: string) => void;
  onOpenDoors: (ri: number) => void;
  onOpenWindows: (ri: number) => void;
  onDeleteFloor?: (fi: number) => void;
  onMoveFloor?: (fi: number, direction: 'left' | 'right') => void;
  onReorderFloors?: (dragIdx: number, dropIdx: number) => void;
  onAddFloor?: () => void;
  onRenameFloor?: (fi: number, name: string) => void;
}

export default function FloorPanel({
  floors, activeFloorIdx, setActiveFloorIdx, editable,
  onAddRoom, onRemoveRoom, onRoomFieldChange,
  onToggleStaircase, onToggleMidlanding, onFloorNestedChange, onReplicateFloor,
  onOpenDoors, onOpenWindows, onDeleteFloor, onMoveFloor, onReorderFloors, onAddFloor, onRenameFloor,
}: FloorPanelProps) {
  const floor = floors[activeFloorIdx];
  const [replicateTargets, setReplicateTargets] = React.useState('');
  const [draggedIdx, setDraggedIdx] = React.useState<number | null>(null);
  const [dragOverIdx, setDragOverIdx] = React.useState<number | null>(null);

  if (!floors || floors.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center gap-4">
        <div className="w-14 h-14 rounded-2xl flex items-center justify-center bg-gradient-accent bg-opacity-10 text-white">
          <Building2 className="w-6 h-6" />
        </div>
        <div>
          <p className="font-bold text-sm" style={{ color: 'var(--foreground)' }}>No floor data found</p>
          <p className="text-xs mt-1" style={{ color: 'var(--muted)' }}>The AI did not extract any floors from this drawing.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-5 animate-fade-in">

      {/* ── Floor Tabs ── */}
      <div className="flex flex-col gap-2">
        <p className="section-label">Select floor to review &amp; edit</p>
        <div className="flex flex-wrap gap-2">
          {floors.map((fl, idx) => {
            const rc = (fl.rooms || []).length;
            const isActive = activeFloorIdx === idx;
            return (
              <button key={idx} type="button" onClick={() => setActiveFloorIdx(idx)}
                draggable={editable}
                onDragStart={(e) => {
                  setDraggedIdx(idx);
                  e.dataTransfer.effectAllowed = 'move';
                  e.dataTransfer.setData('text/plain', idx.toString());
                }}
                onDragOver={(e) => {
                  e.preventDefault();
                  if (draggedIdx !== null && draggedIdx !== idx) {
                    setDragOverIdx(idx);
                  }
                }}
                onDragLeave={() => setDragOverIdx(null)}
                onDrop={(e) => {
                  e.preventDefault();
                  if (draggedIdx !== null && draggedIdx !== idx && onReorderFloors) {
                    onReorderFloors(draggedIdx, idx);
                  }
                  setDraggedIdx(null);
                  setDragOverIdx(null);
                }}
                onDragEnd={() => {
                  setDraggedIdx(null);
                  setDragOverIdx(null);
                }}
                className={`flex items-center gap-2.5 px-4 py-2.5 rounded-xl text-xs font-bold transition-all border ${draggedIdx === idx ? 'opacity-50' : ''} ${dragOverIdx === idx ? 'ring-2 scale-105' : ''} ${isActive ? 'bg-gradient-accent text-white border-transparent shadow-md' : 'bg-panel text-fg border-border'}`}
                style={{
                  boxShadow: isActive ? '0 4px 16px rgba(255,81,47,.3)' : undefined,
                  cursor: editable ? 'grab' : 'pointer',
                }}>
                <span className="w-6 h-6 rounded-lg flex items-center justify-center text-[10px] font-extrabold"
                  style={{
                    background: isActive ? 'rgba(255,255,255,0.2)' : 'var(--accent-subtle)',
                    color: isActive ? 'white' : 'var(--accent)',
                  }}>
                  {idx + 1}
                </span>
                <span>{fl.floor_name || `Floor ${fl.floor_number}`}</span>
                <span className="text-[10px] px-2 py-0.5 rounded-full font-bold"
                  style={{
                    background: isActive ? 'rgba(255,255,255,0.2)' : rc > 0 ? 'var(--accent-subtle)' : 'rgba(100,116,139,0.12)',
                    color: isActive ? 'white' : rc > 0 ? 'var(--accent)' : 'var(--muted)',
                  }}>
                  {rc} {rc === 1 ? 'room' : 'rooms'}
                </span>
              </button>
            );
          })}
          {editable && onAddFloor && (
            <button type="button" onClick={onAddFloor}
              className="flex items-center gap-1.5 px-4 py-2.5 rounded-xl text-xs font-bold transition-all border border-dashed"
              style={{
                background: 'transparent',
                borderColor: 'var(--panel-border)',
                color: 'var(--muted)',
              }}
              onMouseOver={e => { e.currentTarget.style.borderColor = 'var(--accent)'; e.currentTarget.style.color = 'var(--accent)'; }}
              onMouseOut={e => { e.currentTarget.style.borderColor = 'var(--panel-border)'; e.currentTarget.style.color = 'var(--muted)'; }}
            >
              <Plus className="w-4 h-4" /> Add Floor
            </button>
          )}
        </div>
      </div>

      {floor && (
        <div className="flex flex-col gap-4 animate-slide-up">

          {/* ── Rooms Card ── */}
          <div className="rounded-2xl overflow-hidden shadow-sm transition-all duration-300 hover:shadow-xl hover:shadow-[#8b5cf6]/10 hover:-translate-y-0.5 cursor-default"
            style={{ background: 'var(--panel)', border: '1px solid var(--panel-border)' }}>

            {/* Header */}
            <div className="flex justify-between items-center px-6 py-4 border-b"
              style={{ borderColor: 'var(--panel-border)', background: 'var(--panel-header)' }}>
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-xl flex items-center justify-center bg-gradient-accent bg-opacity-10 text-white">
                  <Building2 className="w-4 h-4" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <input 
                      type="text"
                      value={floor.floor_name || ''}
                      placeholder={`Floor ${floor.floor_number}`}
                      disabled={!editable}
                      onChange={(e) => onRenameFloor && onRenameFloor(activeFloorIdx, e.target.value)}
                      className="font-bold text-sm bg-transparent border-b border-transparent focus:border-accent focus:outline-none hover:border-gray-500 transition-colors w-32"
                      style={{ color: 'var(--foreground)' }}
                    />
                    <span className="font-bold text-sm" style={{ color: 'var(--foreground)' }}>— Rooms &amp; Spaces</span>
                  </div>
                  <p className="text-[11px] mt-0.5" style={{ color: 'var(--muted)' }}>
                    {(floor.rooms || []).length} spaces extracted by AI vision
                  </p>
                </div>
              </div>
              {editable && (
                <div className="flex items-center gap-2">
                  {onMoveFloor && (
                    <div className="flex items-center rounded-lg border mr-2" style={{ borderColor: 'var(--panel-border)', background: 'var(--panel)' }}>
                      <button type="button" onClick={() => onMoveFloor(activeFloorIdx, 'left')} disabled={activeFloorIdx === 0}
                        title="Move Left"
                        className="p-1.5 hover:bg-white/5 disabled:opacity-30 cursor-pointer transition-colors border-r"
                        style={{ borderColor: 'var(--panel-border)' }}>
                        <ChevronLeft className="w-4 h-4 text-[var(--muted)] hover:text-white" />
                      </button>
                      <button type="button" onClick={() => onMoveFloor(activeFloorIdx, 'right')} disabled={activeFloorIdx === floors.length - 1}
                        title="Move Right"
                        className="p-1.5 hover:bg-white/5 disabled:opacity-30 cursor-pointer transition-colors">
                        <ChevronRight className="w-4 h-4 text-[var(--muted)] hover:text-white" />
                      </button>
                    </div>
                  )}
                  {onDeleteFloor && (
                    <button type="button" onClick={() => { if(confirm('Are you sure you want to delete this floor?')) onDeleteFloor(activeFloorIdx); }}
                      title="Delete Floor"
                      className="text-red-400 hover:text-red-300 hover:bg-red-400/10 p-2 rounded-xl cursor-pointer transition-all border mr-2"
                      style={{ borderColor: 'var(--panel-border)' }}>
                      <Trash2 className="w-4 h-4" />
                    </button>
                  )}
                  <button type="button" onClick={() => onAddRoom(activeFloorIdx)}
                    className="btn-accent flex items-center gap-1.5 text-xs px-4 py-2 rounded-xl">
                    <Plus className="w-3.5 h-3.5" /> Add Room
                  </button>
                </div>
              )}
            </div>

            {/* Empty state */}
            {(floor.rooms || []).length === 0 ? (
              <div className="flex flex-col items-center justify-center py-16 gap-4 text-center px-6">
                <div className="w-14 h-14 rounded-2xl flex items-center justify-center bg-gradient-accent bg-opacity-10 text-white border border-[#8b5cf6]/20">
                  <Building2 className="w-6 h-6" />
                </div>
                <div>
                  <p className="font-bold" style={{ color: 'var(--foreground)' }}>No rooms on this floor</p>
                  <p className="text-xs mt-1 max-w-sm leading-relaxed" style={{ color: 'var(--muted)' }}>
                    The AI didn't find rooms here. If they exist in the plan, add them manually.
                  </p>
                </div>
                {editable && (
                  <button type="button" onClick={() => onAddRoom(activeFloorIdx)}
                    className="btn-accent flex items-center gap-2 text-sm px-6 py-2.5 rounded-xl">
                    <Plus className="w-4 h-4" /> Add First Room
                  </button>
                )}
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-xs text-left border-collapse" style={{ minWidth: 820 }}>
                  <thead>
                    <tr className="border-b" style={{ borderColor: 'var(--panel-border)', background: 'var(--panel-header)' }}>
                      {['Name', 'Type', 'Shape', 'L×W×H (m)', 'Openings', 'Flooring', 'PUP', 'Skirting m', 'Dado H', 'Railing', ''].map(h => (
                        <th key={h} className="py-3 px-3 text-[10px] font-bold uppercase tracking-wide select-none"
                          style={{ color: 'var(--muted)' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {(floor.rooms || []).map((room, rIdx) => (
                      <RoomRow
                        key={rIdx}
                        room={room}
                        floorIdx={activeFloorIdx}
                        roomIdx={rIdx}
                        editable={editable}
                        onFieldChange={onRoomFieldChange}
                        onRemove={onRemoveRoom}
                        onOpenDoors={() => onOpenDoors(rIdx)}
                        onOpenWindows={() => onOpenWindows(rIdx)}
                      />
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* ── Staircase & Midlanding ── */}
          <StaircaseMidlandingCards
            floor={floor}
            floorIdx={activeFloorIdx}
            editable={editable}
            onToggleStaircase={onToggleStaircase}
            onToggleMidlanding={onToggleMidlanding}
            onNestedChange={onFloorNestedChange}
          />

          {/* ── Copy Layout Tool ── */}
          {editable && floors.length > 1 && (
            <div className="rounded-xl p-4 flex items-center gap-4 flex-wrap"
              style={{ background: 'var(--panel)', border: '1px solid var(--panel-border)' }}>
              <span className="text-xs font-bold text-gradient-accent">📋 Copy Layout</span>
              <span className="text-xs" style={{ color: 'var(--muted)' }}>
                Replicate <strong style={{ color: 'var(--foreground)' }}>{floor.floor_name}</strong> rooms &amp; staircases to:
              </span>
              <input
                type="text"
                value={replicateTargets}
                onChange={e => setReplicateTargets(e.target.value)}
                placeholder="e.g. 3, 5 or Floor 3, Floor 5"
                className="border rounded-lg px-3 py-1.5 text-xs focus:outline-none focus:border-accent w-56"
                style={{ background: 'var(--background)', borderColor: 'var(--panel-border)', color: 'var(--foreground)' }}
              />
              <button type="button"
                onClick={() => {
                  onReplicateFloor(activeFloorIdx, replicateTargets);
                  setReplicateTargets('');
                }}
                className="text-xs font-bold px-4 py-1.5 rounded-lg cursor-pointer transition-all border border-[#8b5cf6]/20 bg-gradient-accent bg-opacity-10 text-gradient-accent hover:text-white hover:bg-opacity-100"
                style={{}}
                onMouseOver={e => { e.currentTarget.classList.add('text-white'); e.currentTarget.classList.remove('text-gradient-accent'); }}
                onMouseOut={e => { e.currentTarget.classList.remove('text-white'); e.currentTarget.classList.add('text-gradient-accent'); }}>
                Replicate →
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
