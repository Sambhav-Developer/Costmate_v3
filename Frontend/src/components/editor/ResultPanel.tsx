'use client';
import React, { useMemo } from 'react';
import { Download, FileSpreadsheet } from 'lucide-react';
import { Workbook } from '@fortune-sheet/react';
import '@fortune-sheet/react/dist/index.css';

interface ResultPanelProps {
  sessionState: any;
  sessionId: string;
  downloadUrl: string;
}

export default function ResultPanel({ sessionState, sessionId, downloadUrl }: ResultPanelProps) {
  let verified = sessionState?.qa_verified;
  let prefilled = sessionState?.qa_prefilled;
  
  if (typeof verified === 'string') {
    try { verified = JSON.parse(verified.replace(/```json/g, '').replace(/```/g, '').trim()); } catch (e) {}
  }
  if (typeof prefilled === 'string') {
    try { prefilled = JSON.parse(prefilled.replace(/```json/g, '').replace(/```/g, '').trim()); } catch (e) {}
  }
  
  const hasVerified = verified && typeof verified === 'object' && Object.keys(verified).length > 0;
  const hasPreFilled = prefilled && typeof prefilled === 'object' && Object.keys(prefilled).length > 0;
  
  const qa = hasVerified ? verified : (hasPreFilled ? prefilled : {});
  
  const doors = (verified?.doors?.length ? verified.doors : prefilled?.doors) || qa.doors || [];
  const windows = (verified?.windows?.length ? verified.windows : prefilled?.windows) || qa.windows || [];
  const cvLookup = useMemo(() => {
    const detections = sessionState?.cv_results?.detections || [];
    const map: any = {};
    for (const d of detections) {
      if (d.mark) map[String(d.mark).trim().toUpperCase()] = d;
    }
    return map;
  }, [sessionState?.cv_results]);

  const hasScheduleData = doors.length > 0 || windows.length > 0;

  const workbookData = useMemo(() => {
    if (!hasScheduleData) return [];
    
    const items = [...doors, ...windows];

    const generateRawSheet = (sheetItems: any[], sheetName: string, color: string, order: number) => {
      const allKeys = new Set<string>();
      sheetItems.forEach(item => Object.keys(item).forEach(k => allKeys.add(k)));
      const rawHeaders = Array.from(allKeys).filter(k => {
        const kl = k.toLowerCase().trim();
        return kl !== 'count' && kl !== 'qty' && 
               kl !== 'needs_review' && kl !== 'needs review' && 
               kl !== 'need_review' && kl !== 'need review';
      });
      
      const celldata: any[] = [];
      rawHeaders.forEach((h, c) => {
        const displayHeader = (h.toLowerCase() === 'type' || h.toLowerCase() === 'mark') ? 'MARK' : h;
        celldata.push({ r: 0, c, v: { v: displayHeader, m: displayHeader, bl: 1, bg: '#333333', fc: '#ffffff' } });
      });

      sheetItems.forEach((item, rIdx) => {
        rawHeaders.forEach((h, cIdx) => {
          const val = item[h] || '';
          celldata.push({ r: rIdx + 1, c: cIdx, v: { v: val, m: String(val) } });
        });
      });

      celldata.push({ r: 99, c: 25, v: { v: '', m: '' } });

      return {
        name: sheetName,
        color,
        status: order === 0 ? 1 : 0,
        order,
        row: 100,
        column: 26,
        celldata,
        config: { columnlen: Object.fromEntries(rawHeaders.map((_, i) => [i, 130])) }
      };
    };

    const generateEstimationSheet = (order: number) => {
      const allKeys = new Set<string>();
      items.forEach(item => Object.keys(item).forEach(k => allKeys.add(k)));
      const rawHeaders = Array.from(allKeys);
      
      const estimationHeaders = ['QTY', 'MARKS', 'LOCATION', 'ESTIMATOR NOTES', 'FLOOR NO', 'OPENING MODE', 'INT/EXT'];
      const dynamicHeaders = rawHeaders.filter(k => {
        const kl = k.toLowerCase().trim();
        return kl !== 'mark' && kl !== 'type' && 
               kl !== 'count' && kl !== 'qty' &&
               kl !== 'needs_review' && kl !== 'needs review' && 
               kl !== 'need_review' && kl !== 'need review';
      });
      const finalHeaders = [...estimationHeaders, ...dynamicHeaders];
      
      const celldata: any[] = [];
      finalHeaders.forEach((h, c) => {
        celldata.push({ r: 0, c, v: { v: h, m: h, bl: 1, bg: '#333333', fc: '#ffffff' } });
      });

      items.forEach((item, rIdx) => {
        const mark = String(item.type || item.mark || '').trim().toUpperCase();
        const cvInfo = cvLookup[mark] || {};
        
        finalHeaders.forEach((h, cIdx) => {
          let val = '';
          if (h === 'QTY') val = item.count || '1';
          else if (h === 'MARKS') val = mark;
          else if (h === 'LOCATION' || h === 'ESTIMATOR NOTES' || h === 'FLOOR NO') val = '';
          else if (h === 'OPENING MODE') val = cvInfo.opening_mode || '';
          else if (h === 'INT/EXT') val = cvInfo.int_ext || '';
          else val = item[h] || '';
          
          celldata.push({ r: rIdx + 1, c: cIdx, v: { v: val, m: String(val) } });
        });
      });

      celldata.push({ r: 99, c: 29, v: { v: '', m: '' } });

      return {
        name: 'ESTIMATION SCHEDULE',
        color: '#ffaa00',
        status: order === 0 ? 1 : 0,
        order,
        row: 100,
        column: 30,
        celldata,
        config: { columnlen: Object.fromEntries(finalHeaders.map((_, i) => [i, 150])) }
      };
    };

    const sheets = [];
    if (doors.length > 0) sheets.push(generateRawSheet(doors, 'DOOR SCHEDULE', '#4caf50', sheets.length));
    if (windows.length > 0) sheets.push(generateRawSheet(windows, 'WINDOW SCHEDULE', '#2196f3', sheets.length));
    if (items.length > 0) sheets.push(generateEstimationSheet(sheets.length));
    
    return sheets;
  }, [doors, windows, cvLookup, hasScheduleData]);

  const [showWorkbook, setShowWorkbook] = React.useState(false);
  const containerRef = React.useRef<HTMLDivElement>(null);
  
  React.useEffect(() => {
    const timer = setTimeout(() => {
      setShowWorkbook(true);
    }, 100);

    return () => clearTimeout(timer);
  }, []);

  React.useEffect(() => {
    if (!showWorkbook || !containerRef.current) return;

    const observer = new ResizeObserver(() => {
      // Safely dispatch window resize to trigger fortune-sheet auto-resize
      window.dispatchEvent(new Event('resize'));
    });

    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, [showWorkbook]);

  return (
    <div className="flex flex-col gap-5 w-full h-[85vh] animate-fade-in relative overflow-hidden">
      {/* ── Summary Banner ── */}
      <div className="rounded-2xl p-5 flex items-center justify-between gap-4 shrink-0"
        style={{
          background: 'linear-gradient(135deg, rgba(255,81,47,0.08) 0%, rgba(139,92,246,0.06) 100%)',
          border: '1px solid rgba(139,92,246,0.15)',
        }}>
        <div className="flex items-center gap-4">
          <div className="w-11 h-11 rounded-2xl flex items-center justify-center bg-gradient-accent bg-opacity-10 text-white">
            <FileSpreadsheet className="w-5 h-5" />
          </div>
          <div>
            <p className="font-bold text-sm" style={{ color: 'var(--foreground)' }}>Bill of Quantities</p>
            <p className="text-[11px] mt-0.5" style={{ color: 'var(--muted)' }}>
              Preview, edit and export your Excel sheets instantly.
            </p>
          </div>
        </div>
        
        <div className="flex items-center gap-3">
          <a
            href={downloadUrl}
            download
            className="btn-accent flex items-center gap-2 text-sm px-5 py-2.5 rounded-xl no-underline transition-all hover:scale-[1.02]"
          >
            <Download className="w-4 h-4" />
            Download Excel
          </a>
        </div>
      </div>

      {/* ── Content Area ── */}
      {hasScheduleData ? (
        <div 
          ref={containerRef}
          className="w-full flex-1 rounded-2xl overflow-hidden border shadow-xl relative costmate-fortune-wrapper" 
          style={{ borderColor: 'var(--panel-border)' }}
        >
          {showWorkbook && <Workbook data={workbookData} />}
        </div>
      ) : (
        <div className="flex-1 flex flex-col items-center justify-center bg-white rounded-2xl border shadow-sm">
           <FileSpreadsheet className="w-12 h-12 text-slate-300 mb-4" />
           <p className="text-slate-500 font-medium text-sm">No schedule data available to preview.</p>
        </div>
      )}
    </div>
  );
}
