'use client';
import React from 'react';
import { QaForm, Footing, Column, Beam } from './types';
import { FootingsSchedule, ColumnsSchedule, BeamsSchedule } from './ScheduleTables';

// ─── Field components ──────────────────────────────────────────
function FieldGroup({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1.5">
      <label className="field-label">{label}</label>
      {children}
    </div>
  );
}

const inputCls = "border rounded-xl px-3.5 py-2.5 text-sm focus:outline-none focus:border-accent transition-colors w-full";
const inputStyle = {
  background: 'var(--input-bg)',
  borderColor: 'var(--input-border)',
  color: 'var(--input-fg)',
};

function TextInput({ value, onChange, disabled, placeholder }: any) {
  return (
    <input type="text" value={value || ''} onChange={onChange} disabled={disabled} placeholder={placeholder}
      className={`${inputCls} disabled:opacity-60`} style={inputStyle} />
  );
}

function NumberInput({ value, onChange, disabled, step, min }: any) {
  return (
    <input type="number" value={value} step={step} min={min} onChange={onChange} disabled={disabled}
      className={`${inputCls} disabled:opacity-60`} style={inputStyle} />
  );
}

function SelectInput({ value, onChange, disabled, options }: { value: string; onChange: any; disabled?: boolean; options: string[] }) {
  return (
    <select value={value} onChange={onChange} disabled={disabled}
      className={`${inputCls} disabled:opacity-60 cursor-pointer`} style={inputStyle}>
      {options.map(o => <option key={o}>{o}</option>)}
    </select>
  );
}

// ─── Section Card ──────────────────────────────────────────────
interface SectionCardProps {
  icon: string;
  title: string;
  description?: string;
  badge?: string;
  children: React.ReactNode;
}

function SectionCard({ icon, title, description, badge, children }: SectionCardProps) {
  return (
    <div className="rounded-2xl overflow-hidden shadow-sm"
      style={{ background: 'var(--panel)', border: '1px solid var(--panel-border)' }}>
      <div className="px-6 py-4 border-b flex items-center gap-3"
        style={{ borderColor: 'var(--panel-border)', background: 'var(--panel-header)' }}>
        <span className="text-xl">{icon}</span>
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <span className="font-bold text-sm" style={{ color: 'var(--foreground)' }}>{title}</span>
            {badge && (
              <span className="text-[10px] font-bold px-2 py-0.5 rounded-full pill-accent">{badge}</span>
            )}
          </div>
          {description && (
            <p className="text-[11px] mt-0.5" style={{ color: 'var(--muted)' }}>{description}</p>
          )}
        </div>
      </div>
      <div className="p-6">{children}</div>
    </div>
  );
}

// ─── BasicsPanel ───────────────────────────────────────────────
interface BasicsPanelProps {
  form: QaForm;
  editable: boolean;
  updateField: (key: string, value: any) => void;
  newFooting: Footing;
  setNewFooting: React.Dispatch<React.SetStateAction<Footing>>;
  onAddFooting: () => void;
  onRemoveFooting: (idx: number) => void;
  onFootingChange: (idx: number, key: string, value: any) => void;
  newColumn: Column;
  setNewColumn: React.Dispatch<React.SetStateAction<Column>>;
  onAddColumn: () => void;
  onRemoveColumn: (idx: number) => void;
  onColumnChange: (idx: number, key: string, value: any) => void;
  newBeam: Beam;
  setNewBeam: React.Dispatch<React.SetStateAction<Beam>>;
  onAddBeam: () => void;
  onRemoveBeam: (idx: number) => void;
  onBeamChange: (idx: number, key: string, value: any) => void;
}

export default function BasicsPanel({
  form, editable, updateField,
  newFooting, setNewFooting, onAddFooting, onRemoveFooting, onFootingChange,
  newColumn, setNewColumn, onAddColumn, onRemoveColumn, onColumnChange,
  newBeam, setNewBeam, onAddBeam, onRemoveBeam, onBeamChange,
}: BasicsPanelProps) {
  return (
    <div className="flex flex-col gap-5 animate-fade-in">

      {/* ── Project Information ── */}
      <SectionCard icon="🏗️" title="Project Information" description="Basic details about this building project">
        <div className="grid grid-cols-2 gap-x-6 gap-y-4">
          <div className="col-span-2">
            <FieldGroup label="Project / Work Name">
              <TextInput value={form.project_name}
                onChange={(e: any) => updateField('project_name', e.target.value)}
                disabled={!editable} placeholder="e.g. Sharma Residence Construction" />
            </FieldGroup>
          </div>
          <div className="col-span-2">
            <FieldGroup label="Sub-Work Name">
              <TextInput value={form.sub_work_name}
                onChange={(e: any) => updateField('sub_work_name', e.target.value)}
                disabled={!editable} placeholder="e.g. Ground Floor Shell Construction" />
            </FieldGroup>
          </div>
          <FieldGroup label="Building Type">
            <SelectInput
              value={form.plan_type || 'Residential'}
              onChange={(e: any) => updateField('plan_type', e.target.value)}
              disabled={!editable}
              options={['Residential', 'Commercial', 'Industrial', 'Mixed Use', 'Institutional']}
            />
          </FieldGroup>
          <FieldGroup label="Standard Floor-to-Floor Height (m)">
            <NumberInput value={form.floor_height_m || 3.0} step="0.01"
              onChange={(e: any) => updateField('floor_height_m', parseFloat(e.target.value) || 3.0)}
              disabled={!editable} />
          </FieldGroup>
        </div>
      </SectionCard>

      {/* ── Building Configuration ── */}
      <SectionCard icon="🏢" title="Building Configuration" description="Number of floors and basement details">
        <div className="grid grid-cols-3 gap-4">
          <FieldGroup label="Total Floors (incl. Ground Floor)">
            <NumberInput value={form.num_floors ?? 1} min="1"
              onChange={(e: any) => updateField('num_floors', parseInt(e.target.value) || 1)}
              disabled={!editable} />
          </FieldGroup>
          <FieldGroup label="Floors Above Ground Floor">
            <div className="border rounded-xl px-3.5 py-2.5 text-sm font-semibold flex items-center gap-2"
              style={{ background: 'var(--accent-subtle)', borderColor: 'var(--accent-ring)', color: 'var(--accent)' }}>
              <span>{Math.max(0, (form.num_floors ?? 1) - 1)}</span>
              <span className="text-xs font-normal opacity-70">(auto calculated)</span>
            </div>
          </FieldGroup>
          <FieldGroup label="Has Basements?">
            <SelectInput
              value={form.has_basement ? 'Yes' : 'No'}
              onChange={(e: any) => {
                const has = e.target.value === 'Yes';
                updateField('has_basement', has);
                if (!has) updateField('num_basements', 0);
              }}
              disabled={!editable}
              options={['No', 'Yes']}
            />
          </FieldGroup>
          {form.has_basement && (
            <FieldGroup label="Number of Basements">
              <NumberInput value={form.num_basements ?? 1} min="1"
                onChange={(e: any) => updateField('num_basements', parseInt(e.target.value) || 1)}
                disabled={!editable} />
            </FieldGroup>
          )}
        </div>
      </SectionCard>

      {/* ── Footings Schedule ── */}
      <SectionCard
        icon="⛏️"
        title="Footings Schedule"
        description="Define isolated footing types used in this building"
        badge={`${(form.footings || []).length} types`}
      >
        <FootingsSchedule
          footings={form.footings || []}
          editable={editable}
          onRemove={onRemoveFooting}
          onChange={onFootingChange}
          onAdd={onAddFooting}
          newFooting={newFooting}
          setNewFooting={setNewFooting}
        />
      </SectionCard>

      {/* ── Columns Schedule ── */}
      <SectionCard
        icon="🏛️"
        title="Columns Schedule"
        description="Column cross-section types in this structure"
        badge={`${(form.columns || []).length} types`}
      >
        <ColumnsSchedule
          columns={form.columns || []}
          editable={editable}
          onRemove={onRemoveColumn}
          onChange={onColumnChange}
          onAdd={onAddColumn}
          newColumn={newColumn}
          setNewColumn={setNewColumn}
        />
      </SectionCard>

      {/* ── Beams Schedule ── */}
      <SectionCard
        icon="🔩"
        title="Beams Schedule"
        description="Beam types spanning between columns"
        badge={`${(form.beams || []).length} types`}
      >
        <BeamsSchedule
          beams={form.beams || []}
          editable={editable}
          onRemove={onRemoveBeam}
          onChange={onBeamChange}
          onAdd={onAddBeam}
          newBeam={newBeam}
          setNewBeam={setNewBeam}
        />
      </SectionCard>
    </div>
  );
}
