'use client';
import React from 'react';
import { Download, FileSpreadsheet, CheckCircle2 } from 'lucide-react';

const LINE_ITEMS = [
  { id: '1.1', desc: 'Excavation in foundation trenches or over-sites for footings', quantKey: 'excavation_volume_cum', unit: 'Cum' },
  { id: '1.2', desc: 'Providing and laying PCC M10 in foundation & plinth', quantKey: 'pcc_volume_cum', unit: 'Cum' },
  { id: '1.3', desc: 'Providing and laying RCC M20 in footing, columns, beams & slab', quantKey: 'rcc_volume_cum', unit: 'Cum' },
  { id: '1.4', desc: 'Brick masonry walls in CM 1:6 above plinth', quantKey: 'brickwork_volume_cum', unit: 'Cum' },
  { id: '1.5', desc: 'Plastering internal walls 12mm thick CM 1:6', quantKey: 'plaster_area_sqm', unit: 'Sqm' },
  { id: '1.6', desc: 'Vitrified tile flooring (600×600) including bedding', quantKey: 'flooring_area_sqm', unit: 'Sqm' },
];

interface ResultPanelProps {
  sessionState: any;
  sessionId: string;
  downloadUrl: string;
}

export default function ResultPanel({ sessionState, sessionId, downloadUrl }: ResultPanelProps) {
  const cq = sessionState?.civil_quantities || {};
  const hasAny = LINE_ITEMS.some(item => cq[item.quantKey] !== undefined && cq[item.quantKey] !== null);

  return (
    <div className="flex flex-col gap-5 w-full max-w-5xl mx-auto animate-fade-in">

      {/* ── Summary Banner ── */}
      <div className="rounded-2xl p-5 flex items-center justify-between gap-4"
        style={{
          background: 'linear-gradient(135deg, rgba(255,81,47,0.08) 0%, rgba(139,92,246,0.06) 100%)',
          border: '1px solid rgba(139,92,246,0.15)',
        }}>
        <div className="flex items-center gap-4">
          <div className="w-11 h-11 rounded-2xl flex items-center justify-center bg-gradient-accent bg-opacity-10 text-white">
            <FileSpreadsheet className="w-5 h-5" />
          </div>
          <div>
            <p className="font-bold text-sm" style={{ color: 'var(--foreground)' }}>Bill of Quantities — Ready</p>
            <p className="text-[11px] mt-0.5" style={{ color: 'var(--muted)' }}>
              Civil work quantities extracted and verified from your floor plan
            </p>
          </div>
        </div>
        <a
          href={downloadUrl}
          download
          className="btn-accent flex items-center gap-2 text-sm px-5 py-2.5 rounded-xl no-underline"
        >
          <Download className="w-4 h-4" />
          Download Excel
        </a>
      </div>

      {/* ── BOQ Table ── */}
      <div className="rounded-2xl overflow-hidden shadow-sm"
        style={{ background: 'var(--panel)', border: '1px solid var(--panel-border)' }}>

        {/* Table Header */}
        <div className="px-6 py-4 border-b" style={{ borderColor: 'var(--panel-border)', background: 'var(--panel-header)' }}>
          <p className="font-bold text-sm" style={{ color: 'var(--foreground)' }}>Line Items — Quantity Schedule</p>
          <p className="text-[11px] mt-0.5" style={{ color: 'var(--muted)' }}>Standard work items with computed quantities</p>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-xs text-left border-collapse">
            <thead>
              <tr className="border-b" style={{ borderColor: 'var(--panel-border)', background: 'var(--panel-header)' }}>
                {[
                  { label: 'No.', cls: 'w-14 text-center' },
                  { label: 'Description of Work', cls: '' },
                  { label: 'Quantity', cls: 'w-28 text-right' },
                  { label: 'Unit', cls: 'w-20' },
                ].map(({ label, cls }) => (
                  <th key={label} className={`py-3 px-4 text-[10px] font-bold uppercase tracking-wide select-none ${cls}`}
                    style={{ color: 'var(--muted)' }}>
                    {label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {LINE_ITEMS.map((item, i) => {
                const qty = cq[item.quantKey];
                const hasData = qty !== undefined && qty !== null;
                return (
                  <tr key={item.id}
                    className="border-b transition-colors"
                    style={{ borderColor: 'var(--panel-border)' }}
                    onMouseOver={e => (e.currentTarget.style.background = 'var(--panel-header)')}
                    onMouseOut={e => (e.currentTarget.style.background = 'transparent')}>

                    {/* Item No */}
                    <td className="py-3.5 px-4 text-center">
                      <span className="text-[11px] font-bold px-2 py-0.5 rounded-md bg-gradient-accent bg-opacity-10 text-white">
                        {item.id}
                      </span>
                    </td>

                    {/* Description */}
                    <td className="py-3.5 px-4 leading-relaxed" style={{ color: 'var(--foreground)' }}>
                      {item.desc}
                    </td>

                    {/* Quantity */}
                    <td className="py-3.5 px-4 text-right">
                      {hasData ? (
                        <span className="font-mono font-bold text-sm" style={{ color: 'var(--foreground)' }}>
                          {Number(qty).toFixed(2)}
                        </span>
                      ) : (
                        <span className="font-mono" style={{ color: 'var(--muted)' }}>—</span>
                      )}
                    </td>

                    {/* Unit */}
                    <td className="py-3.5 px-4" style={{ color: 'var(--muted)' }}>{item.unit}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Footer note */}
        <div className="px-6 py-3 flex items-center gap-2 border-t"
          style={{ borderColor: 'var(--panel-border)', background: 'var(--panel-header)' }}>
          <CheckCircle2 className="w-3.5 h-3.5 shrink-0" style={{ color: 'var(--success)' }} />
          <p className="text-[11px]" style={{ color: 'var(--muted)' }}>
            All quantities validated against CHOPS civil engineering benchmarks. Download the Excel for full item-wise breakdown.
          </p>
        </div>
      </div>
    </div>
  );
}
