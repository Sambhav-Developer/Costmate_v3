'use client';
import React, { useState, useEffect, useMemo } from 'react';
import { ChevronLeft, ChevronRight, Download, ZoomIn, ZoomOut, FileSpreadsheet, FileText, Image, Loader2, RefreshCw, Building2, CheckCircle2, Layers } from 'lucide-react';
import * as XLSX from 'xlsx';
import * as wjcGrid from '@grapecity/wijmo.grid';
import * as wjcGridSheet from '@grapecity/wijmo.react.grid.sheet';
import '@grapecity/wijmo.styles/wijmo.css';
import { api } from '../../lib/api';

import ResultPanel from './ResultPanel';

type FileType = 'plan' | 'excel' | 'readme';

interface FileViewerPanelProps {
  sessionId: string;
  fileType: FileType;
  sessionName: string;
  sessionState?: any;
}

// ── Plan Image Viewer ─────────────────────────────────────────────
function PlanViewer({ sessionId }: { sessionId: string }) {
  const [pageCount, setPageCount] = useState(1);
  const [currentPage, setCurrentPage] = useState(0);
  const [zoom, setZoom] = useState(1);
  const [loading, setLoading] = useState(true);
  const [imgError, setImgError] = useState(false);
  const containerRef = React.useRef<HTMLDivElement>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const handleWheel = (e: WheelEvent) => {
      if (e.ctrlKey) {
        // Prevent native browser page zoom, but do not trigger internal zoom either
        e.preventDefault();
      }
    };

    container.addEventListener('wheel', handleWheel, { passive: false });
    return () => container.removeEventListener('wheel', handleWheel);
  }, []);

  useEffect(() => {
    setLoading(true);
    setImgError(false);
    setCurrentPage(0);
    api.getPlanPageCount(sessionId)
      .then(count => setPageCount(count))
      .catch(() => setPageCount(1));
  }, [sessionId]);

  const imgUrl = pageCount > 1
    ? api.planPageUrl(sessionId, currentPage)
    : api.planImageUrl(sessionId);

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-5 py-3 border-b shrink-0"
        style={{ borderColor: 'var(--panel-border)', background: 'var(--panel-header)' }}>
        <div className="flex items-center gap-2">
          <span className="text-sm font-bold" style={{ color: 'var(--foreground)' }}>
            🏗️ Floor Plan
          </span>
          {pageCount > 1 && (
            <span className="text-xs px-2 py-0.5 rounded-full font-bold pill-accent">
              Page {currentPage + 1} / {pageCount}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {/* Zoom controls */}
          <button onClick={() => setZoom(z => Math.max(0.3, z - 0.2))}
            className="w-8 h-8 flex items-center justify-center rounded-lg cursor-pointer transition-all"
            style={{ background: 'var(--panel)', border: '1px solid var(--panel-border)', color: 'var(--foreground)' }}
            title="Zoom out">
            <ZoomOut className="w-4 h-4" />
          </button>
          <div className="flex items-center gap-0.5" style={{ color: 'var(--muted)' }} title="Click to enter manual zoom">
            <input 
              type="text"
              defaultValue={Math.round(zoom * 100)}
              key={zoom}
              onBlur={(e) => {
                 let v = parseInt(e.target.value);
                 if(!isNaN(v)) setZoom(Math.min(7, Math.max(0.1, v / 100)));
                 else e.target.value = Math.round(zoom * 100).toString();
              }}
              onKeyDown={(e) => {
                 if(e.key === 'Enter') e.currentTarget.blur();
              }}
              className="text-xs font-mono w-8 text-right bg-transparent outline-none border-b border-transparent hover:border-white/20 focus:border-[#8b5cf6] transition-colors"
            />
            <span className="text-xs font-mono">%</span>
          </div>
          <button onClick={() => setZoom(z => Math.min(7, z + 0.2))}
            className="w-8 h-8 flex items-center justify-center rounded-lg cursor-pointer transition-all"
            style={{ background: 'var(--panel)', border: '1px solid var(--panel-border)', color: 'var(--foreground)' }}
            title="Zoom in">
            <ZoomIn className="w-4 h-4" />
          </button>
          <button onClick={() => setZoom(1)}
            className="text-xs px-3 py-1.5 rounded-lg cursor-pointer font-medium transition-all bg-gradient-accent text-white hover:brightness-110">
            Reset
          </button>
        </div>
      </div>

      {/* Page navigation */}
      {pageCount > 1 && (
        <div className="flex items-center justify-center gap-3 py-2 border-b shrink-0"
          style={{ borderColor: 'var(--panel-border)', background: 'var(--panel-header)' }}>
          <button onClick={() => setCurrentPage(p => Math.max(0, p - 1))} disabled={currentPage === 0}
            className="w-8 h-8 flex items-center justify-center rounded-lg cursor-pointer disabled:opacity-40 transition-all"
            style={{ background: 'var(--panel)', border: '1px solid var(--panel-border)', color: 'var(--foreground)' }}>
            <ChevronLeft className="w-4 h-4" />
          </button>
          <div className="flex gap-1">
            {Array.from({ length: pageCount }).map((_, i) => (
              <button key={i} onClick={() => setCurrentPage(i)}
                className="w-6 h-6 rounded-md text-[10px] font-bold cursor-pointer transition-all"
                style={{
                  background: currentPage === i ? 'var(--accent)' : 'var(--panel)',
                  color: currentPage === i ? 'white' : 'var(--muted)',
                  border: `1px solid ${currentPage === i ? 'var(--accent)' : 'var(--panel-border)'}`,
                }}>
                {i + 1}
              </button>
            ))}
          </div>
          <button onClick={() => setCurrentPage(p => Math.min(pageCount - 1, p + 1))} disabled={currentPage === pageCount - 1}
            className="w-8 h-8 flex items-center justify-center rounded-lg cursor-pointer disabled:opacity-40 transition-all"
            style={{ background: 'var(--panel)', border: '1px solid var(--panel-border)', color: 'var(--foreground)' }}>
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Image area */}
      <div ref={containerRef} className="flex-1 overflow-auto p-4 text-center"
        style={{ background: 'var(--background)' }}>
        <div className="inline-block transition-all duration-200" style={{ width: `${zoom * 100}%`, minWidth: '100%' }}>
          {loading && !imgError && (
            <div className="flex flex-col items-center justify-center gap-4 py-20 w-full">
              <Loader2 className="w-8 h-8 animate-spin text-[#8b5cf6]" />
              <p className="text-xs" style={{ color: 'var(--muted)' }}>Loading floor plan...</p>
            </div>
          )}
          {imgError ? (
            <div className="flex flex-col items-center justify-center gap-4 py-20 w-full">
              <Image className="w-12 h-12 opacity-30" style={{ color: 'var(--muted)' }} />
              <p className="text-sm font-semibold" style={{ color: 'var(--foreground)' }}>Plan not available</p>
              <p className="text-xs" style={{ color: 'var(--muted)' }}>The floor plan image could not be loaded.</p>
            </div>
          ) : (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              key={imgUrl}
              src={imgUrl}
              alt="Floor Plan"
              onLoad={() => setLoading(false)}
              onError={() => { setLoading(false); setImgError(true); }}
              style={{
                width: '100%',
                height: 'auto',
                borderRadius: 12,
                boxShadow: '0 8px 40px rgba(0,0,0,0.3)',
                display: loading ? 'none' : 'block',
              }}
            />
          )}
        </div>
      </div>
    </div>
  );
}

// ── Excel Viewer ─────────────────────────────────────────────────
function ExcelViewer({ sessionId, sessionName }: { sessionId: string; sessionName: string }) {
  const downloadUrl = api.downloadUrl(sessionId);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const flexRef = React.useRef<any>(null);

  useEffect(() => {
    setLoading(true);
    fetch(downloadUrl)
      .then(res => {
        if (!res.ok) throw new Error('Failed to load Excel file');
        return res.arrayBuffer();
      })
      .then(buffer => {
        if (flexRef.current) {
          flexRef.current.loadAsync(buffer, () => {
            // Expand grid size to fill viewport for a true full-page experience
            const flex = flexRef.current;
            if (flex && flex.sheets && flex.sheets.length > 0) {
              flex.sheets.forEach((sheet: any) => {
                if (sheet.grid) {
                  // Ensure we have at least columns up to Z (26)
                  while (sheet.grid.columns.length < 26) {
                    sheet.grid.columns.push(new wjcGrid.Column());
                  }
                  // Ensure we have at least 100 rows
                  while (sheet.grid.rows.length < 100) {
                    sheet.grid.rows.push(new wjcGrid.Row());
                  }
                }
              });
            }
            setLoading(false);
          }, (err: any) => {
            console.error(err);
            setError('Failed to load Excel file for preview.');
            setLoading(false);
          });
        }
      })
      .catch(err => {
        console.error(err);
        setError('Failed to load Excel file for preview.');
        setLoading(false);
      });
  }, [downloadUrl]);

  const initGrid = (flex: any) => {
    flexRef.current = flex;
    // Allow editing, remove read-only lock
    flex.isReadOnly = false;
  };

  useEffect(() => {
    // Aggressively remove the Wijmo Evaluation watermark from the DOM
    const interval = setInterval(() => {
      const elements = Array.from(document.querySelectorAll('div, a'));
      elements.forEach(el => {
        if (el.textContent && el.textContent.includes('Evaluation Version')) {
          (el as HTMLElement).style.setProperty('display', 'none', 'important');
          (el as HTMLElement).style.setProperty('opacity', '0', 'important');
        }
      });
    }, 500);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex flex-col h-full relative" style={{ background: 'var(--background)' }}>
      {/* Toolbar */}
      <div className="flex items-center justify-between px-5 py-3 border-b shrink-0 z-10"
        style={{ borderColor: 'var(--panel-border)', background: 'var(--panel-header)' }}>
        <div className="flex items-center gap-2">
          <FileSpreadsheet className="w-4 h-4 text-[#8b5cf6]" />
          <span className="text-sm font-bold" style={{ color: 'var(--foreground)' }}>BOQ Estimate — Excel</span>
        </div>
        <a href={downloadUrl} download
          className="flex items-center gap-1.5 text-xs font-bold px-4 py-2 rounded-xl no-underline transition-all btn-accent">
          <Download className="w-3.5 h-3.5" /> Download Excel
        </a>
      </div>

      {/* Content */}
      <div className="flex-1 w-full relative z-0" style={{ background: 'var(--background)' }}>
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center z-10" style={{ background: 'var(--background)', opacity: 0.8 }}>
            <Loader2 className="w-6 h-6 animate-spin text-accent" />
            <span className="text-sm text-muted font-medium ml-2">Loading Excel preview...</span>
          </div>
        )}
        {error ? (
          <div className="flex items-center justify-center h-full gap-3 text-red-500">
            <span className="text-sm font-medium">{error}</span>
          </div>
        ) : (
          <div className="w-full h-full absolute inset-0">
            <wjcGridSheet.FlexSheet 
              initialized={initGrid}
              style={{ width: '100%', height: '100%', border: 'none' }}
            />
          </div>
        )}
      </div>
    </div>
  );
}

// ── Readme Viewer ─────────────────────────────────────────────────
function ReadmeViewer({ sessionId }: { sessionId: string }) {
  const [readme, setReadme] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    api.getSessionReadme(sessionId)
      .then(data => { setReadme(data); setLoading(false); })
      .catch(err => { setError(err.message || 'Failed to load'); setLoading(false); });
  }, [sessionId]);

  if (loading) return (
    <div className="flex-1 flex items-center justify-center gap-3" style={{ background: 'var(--background)' }}>
      <Loader2 className="w-6 h-6 animate-spin text-[#8b5cf6]" />
      <p className="text-sm" style={{ color: 'var(--muted)' }}>Loading summary...</p>
    </div>
  );

  if (error) return (
    <div className="flex-1 flex flex-col items-center justify-center gap-3 p-8" style={{ background: 'var(--background)' }}>
      <FileText className="w-10 h-10 opacity-30" style={{ color: 'var(--muted)' }} />
      <p className="text-sm" style={{ color: 'var(--muted)' }}>{error}</p>
    </div>
  );

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="flex items-center gap-3 px-5 py-3 border-b shrink-0"
        style={{ borderColor: 'var(--panel-border)', background: 'var(--panel-header)' }}>
        <FileText className="w-4 h-4 text-[#8b5cf6]" />
        <span className="text-sm font-bold" style={{ color: 'var(--foreground)' }}>Project Summary — Readme</span>
      </div>

      <div className="flex-1 overflow-y-auto p-6 flex flex-col gap-5 animate-fade-in" style={{ background: 'var(--background)' }}>

        {/* Project header */}
        <div className="rounded-2xl p-6 transition-all duration-300 hover:shadow-xl hover:shadow-[#8b5cf6]/10 hover:-translate-y-0.5 cursor-default"
          style={{
            background: 'linear-gradient(135deg, rgba(255,81,47,0.08) 0%, rgba(139,92,246,0.06) 100%)',
            border: '1px solid rgba(139,92,246,0.15)',
          }}>
          <div className="flex items-start gap-4">
            <div className="w-12 h-12 rounded-2xl flex items-center justify-center text-2xl shrink-0"
              style={{ background: 'var(--accent-subtle)', border: '1px solid rgba(139,92,246,.2)' }}>
              🏗️
            </div>
            <div className="flex-1">
              <h2 className="font-bold text-lg" style={{ color: 'var(--foreground)' }}>
                {readme.project_name}
              </h2>
              {readme.sub_work_name && readme.sub_work_name !== '—' && (
                <p className="text-sm mt-0.5" style={{ color: 'var(--muted)' }}>{readme.sub_work_name}</p>
              )}
              <div className="flex items-center gap-3 mt-3 flex-wrap">
                <span className="text-xs px-2.5 py-1 rounded-full font-bold pill-accent">{readme.plan_type}</span>
                <span className="text-xs px-2.5 py-1 rounded-full font-bold"
                  style={{ background: 'var(--panel)', color: 'var(--muted)', border: '1px solid var(--panel-border)' }}>
                  📄 {readme.original_filename}
                </span>
                {readme.has_excel && (
                  <span className="text-xs px-2.5 py-1 rounded-full font-bold flex items-center gap-1"
                    style={{ background: 'rgba(34,197,94,0.12)', color: 'rgb(74,222,128)', border: '1px solid rgba(34,197,94,0.2)' }}>
                    <CheckCircle2 className="w-3 h-3" /> Excel Ready
                  </span>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Stats row */}
        <div className="grid grid-cols-3 gap-3">
          {[
            { icon: <Layers className="w-5 h-5" />, label: 'Total Floors', value: readme.num_floors },
            { icon: <Building2 className="w-5 h-5" />, label: 'Total Rooms', value: readme.total_rooms },
            { icon: '🏛️', label: 'Columns', value: readme.columns_count },
          ].map((stat, i) => (
            <div key={i} className="rounded-xl p-4 flex flex-col gap-2 transition-all duration-300 hover:shadow-lg hover:shadow-[#FF512F]/10 hover:-translate-y-1 cursor-default hover:border-[#8b5cf6]/30"
              style={{ background: 'var(--panel)', border: '1px solid var(--panel-border)' }}>
              <div className="w-8 h-8 rounded-lg flex items-center justify-center bg-gradient-accent bg-opacity-10 text-white">
                {typeof stat.icon === 'string' ? stat.icon : stat.icon}
              </div>
              <p className="text-xl font-extrabold" style={{ color: 'var(--foreground)' }}>{stat.value}</p>
              <p className="text-[11px]" style={{ color: 'var(--muted)' }}>{stat.label}</p>
            </div>
          ))}
        </div>

        {/* Floor breakdown */}
        {readme.floors && readme.floors.length > 0 && (
          <div className="rounded-2xl overflow-hidden shadow-sm"
            style={{ background: 'var(--panel)', border: '1px solid var(--panel-border)' }}>
            <div className="px-5 py-3 border-b"
              style={{ borderColor: 'var(--panel-border)', background: 'var(--panel-header)' }}>
              <p className="font-bold text-sm" style={{ color: 'var(--foreground)' }}>Floor-wise Breakdown</p>
            </div>
            <div className="divide-y" style={{ borderColor: 'var(--panel-border)' }}>
              {readme.floors.map((fl: any, i: number) => (
                <div key={i} className="px-5 py-3 flex items-start gap-4 transition-all duration-200 hover:bg-white/[0.03] cursor-default group">
                  <div className="w-7 h-7 rounded-lg flex items-center justify-center text-[11px] font-extrabold shrink-0 bg-gradient-accent bg-opacity-10 text-white transition-transform duration-300 group-hover:scale-110 group-hover:shadow-lg group-hover:shadow-[#FF512F]/20">
                    {i + 1}
                  </div>
                  <div className="flex-1">
                    <p className="text-xs font-bold" style={{ color: 'var(--foreground)' }}>{fl.name}</p>
                    <p className="text-[11px] mt-1 leading-relaxed" style={{ color: 'var(--muted)' }}>
                      {fl.rooms?.map((r: any) => typeof r === 'string' ? r : (r.name || r.type || 'Room')).join(' • ') || 'No rooms'}
                      {fl.has_staircase && <span className="ml-2 opacity-70">• Staircase</span>}
                    </p>
                  </div>
                  <span className="text-[10px] font-bold px-2 py-0.5 rounded-full shrink-0"
                    style={{ background: 'var(--panel-header)', color: 'var(--muted)', border: '1px solid var(--panel-border)' }}>
                    {fl.rooms?.length || 0} rooms
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Key Quantities section removed as requested */}
      </div>
    </div>
  );
}

// ── Main FileViewerPanel ──────────────────────────────────────────
export default function FileViewerPanel({ sessionId, fileType, sessionName, sessionState }: FileViewerPanelProps) {
  return (
    <div className="flex flex-col h-full w-full animate-fade-in">
      {fileType === 'plan' && <PlanViewer sessionId={sessionId} />}
      {fileType === 'excel' && (
        <ResultPanel 
          sessionState={sessionState} 
          sessionId={sessionId} 
          downloadUrl={api.downloadUrl(sessionId)} 
        />
      )}
      {fileType === 'readme' && <ReadmeViewer sessionId={sessionId} />}
    </div>
  );
}
