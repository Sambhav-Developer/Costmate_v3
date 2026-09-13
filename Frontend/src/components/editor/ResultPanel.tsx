'use client';
import React, { useMemo } from 'react';
import { Download, FileSpreadsheet } from 'lucide-react';
import { Workbook } from '@fortune-sheet/react';
import '@fortune-sheet/react/dist/index.css';
import { api } from '../../lib/api';


interface ResultPanelProps {
  sessionState: any;
  sessionId: string;
  downloadUrl: string;
}

function getItemMark(item: any): string {
  if (!item || typeof item !== 'object') return '';
  for (const k of Object.keys(item)) {
    const kl = k.toLowerCase().trim();
    if (['mark', 'type', 'marks', 'door mark', 'door no', 'door no.', 'window mark', 'window no', 'window no.', 'id', 'mark / type', 'mark/type'].includes(kl)) {
      if (item[k]) return String(item[k]).trim().toUpperCase();
    }
  }
  for (const k of Object.keys(item)) {
    const kl = k.toLowerCase().trim();
    if ((kl.includes('mark') || kl.includes('type')) && !['hardware group no', 'door type', 'frame type', 'opening mode', 'type of door', 'type of frame'].includes(kl)) {
      if (item[k]) return String(item[k]).trim().toUpperCase();
    }
  }
  return '';
}

export default function ResultPanel({ sessionState, sessionId, downloadUrl }: ResultPanelProps) {
  let verified = sessionState?.qa_verified;
  let prefilled = sessionState?.qa_prefilled;

  if (typeof verified === 'string') {
    try { verified = JSON.parse(verified.replace(/```json/g, '').replace(/```/g, '').trim()); } catch (e) { }
  }
  if (typeof prefilled === 'string') {
    try { prefilled = JSON.parse(prefilled.replace(/```json/g, '').replace(/```/g, '').trim()); } catch (e) { }
  }

  const hasVerified = verified && typeof verified === 'object' && Object.keys(verified).length > 0;

  const doors = hasVerified && Array.isArray(verified.doors) 
    ? verified.doors 
    : (prefilled?.doors || []);

  const windows = hasVerified && Array.isArray(verified.windows) 
    ? verified.windows 
    : (prefilled?.windows || []);
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

    const getDictVal = (d: any, targetKey: string): string => {
      if (!d || typeof d !== 'object' || !targetKey) return '';
      if (d[targetKey] !== undefined && d[targetKey] !== null && String(d[targetKey]).trim() !== '') {
        return String(d[targetKey]);
      }
      const tkLower = targetKey.toLowerCase().trim();
      for (const k of Object.keys(d)) {
        if (k.toLowerCase().trim() === tkLower && d[k] !== undefined && d[k] !== null && String(d[k]).trim() !== '') {
          return String(d[k]);
        }
      }
      if (['mark', 'marks', 'door mark', 'door no', 'number', 'type'].includes(tkLower)) {
        for (const k of ['mark', 'MARK', 'type', 'TYPE', 'door_mark', 'number', '_original_mark']) {
          if (d[k] && String(d[k]).trim() !== '') return String(d[k]);
        }
      }
      return '';
    };

    const getItemLocation = (d: any): string => {
      if (!d || typeof d !== 'object') return '';
      const locKeys = ['location', 'location name', 'room', 'room name', 'room no', 'room number', 'room/location', 'room / location', 'room_name', 'room_no'];
      for (const k of Object.keys(d)) {
        if (locKeys.includes(k.toLowerCase().trim()) && d[k] && String(d[k]).trim() !== '') {
          return String(d[k]);
        }
      }
      return '';
    };

    const generateRawSheet = (sheetItems: any[], sheetName: string, color: string, order: number) => {
      const excludedKeys = new Set([
        'count', 'qty', 'needs_review', 'needs review', 'need_review', 'need review',
        'is_borderline', 'is borderline', 'review_reason', 'review reason',
        'section', 'reason', 'reconciled', 'excluded', 'opening_mode', 'opening mode',
        'int/ext', 'int_ext'
      ]);
      const rawHeadersInput = prefilled?.raw_schedule_headers || (sheetItems.length > 0 ? Object.keys(sheetItems[0]) : []);
      const rawSchedCols = rawHeadersInput.filter((k: string) => !String(k).startsWith('_') && !excludedKeys.has(String(k).toLowerCase().trim()));

      const celldata: any[] = [];

      // Metadata Block (Rows 0 to 3)
      const metaItems = [
        ["PROJECT NAME:", sessionState?.project_name || "Costmate Project Takeoff"],
        ["TAKEOFF DONE BY:", "Costmate AI Takeoff"],
        ["PLANS DATE:", "07.09.2026"],
        ["TAKEOFF DATE:", new Date().toLocaleDateString('en-GB')]
      ];
      metaItems.forEach(([label, val], rIdx) => {
        celldata.push({ r: rIdx, c: 0, v: { v: label, m: label, bl: 1 } });
        celldata.push({ r: rIdx, c: 1, v: { v: val, m: String(val), bg: '#FFFF00' } });
      });

      // Header Row (Row 4 = Excel Row 5)
      rawSchedCols.forEach((h: string, c: number) => {
        celldata.push({ r: 4, c, v: { v: h, m: h, bl: 1, bg: '#2F5496', fc: '#ffffff', ht: 1, vt: 1 } });
      });

      // Data Rows (Row 5+ = Excel Row 6+)
      sheetItems.forEach((item, rIdx) => {
        const r = rIdx + 5;
        rawSchedCols.forEach((h: string, c: number) => {
          const val = getDictVal(item, h);
          celldata.push({ r, c, v: { v: val, m: String(val), ht: 1, vt: 1 } });
        });
      });

      return {
        name: sheetName,
        color,
        status: order === 0 ? 1 : 0,
        order,
        row: Math.max(100, sheetItems.length + 10),
        column: Math.max(26, rawSchedCols.length + 2),
        celldata,
        config: { columnlen: Object.fromEntries(rawSchedCols.map((_: any, i: number) => [i, 140])) }
      };
    };

    const generateEstimationSheet = (order: number) => {
      const excludedKeys = new Set([
        'count', 'qty', 'needs_review', 'needs review', 'need_review', 'need review',
        'is_borderline', 'is borderline', 'review_reason', 'review reason',
        'section', 'reason', 'reconciled', 'excluded', 'opening_mode', 'opening mode',
        'int/ext', 'int_ext'
      ]);
      const rawHeadersInput = prefilled?.raw_schedule_headers || (items.length > 0 ? Object.keys(items[0]) : []);
      const rawSchedCols = rawHeadersInput.filter((k: string) => !String(k).startsWith('_') && !excludedKeys.has(String(k).toLowerCase().trim()));

      const hasFloor = rawSchedCols.some((c: string) => String(c).toLowerCase().includes('floor') || String(c).toLowerCase().includes('level'));
      const hasLoc = rawSchedCols.some((c: string) => String(c).toLowerCase().includes('location') || String(c).toLowerCase().includes('room'));

      const estCols: string[] = ['Qty'];
      if (!hasFloor) estCols.push('FLOOR / LEVEL');
      if (!hasLoc) estCols.push('LOCATION');
      estCols.push('Opening mode', 'Int/Ext');

      rawSchedCols.forEach((col: string) => {
        if (!estCols.some(c => c.toLowerCase().trim() === String(col).toLowerCase().trim())) {
          estCols.push(col);
        }
      });
      if (!estCols.some(c => c.toLowerCase().includes('takeoff notes') || c.toLowerCase().includes('estimator notes'))) {
        estCols.push('Takeoff Notes');
      }

      const celldata: any[] = [];

      // Metadata Block (Rows 0 to 3)
      const metaItems = [
        ["PROJECT NAME:", sessionState?.project_name || "Costmate Project Takeoff"],
        ["TAKEOFF DONE BY:", "Costmate AI Takeoff"],
        ["PLANS DATE:", "07.09.2026"],
        ["TAKEOFF DATE:", new Date().toLocaleDateString('en-GB')]
      ];
      metaItems.forEach(([label, val], rIdx) => {
        celldata.push({ r: rIdx, c: 0, v: { v: label, m: label, bl: 1 } });
        celldata.push({ r: rIdx, c: 1, v: { v: val, m: String(val), bg: '#FFFF00' } });
      });

      // Section Title (Row 7 = Excel Row 8)
      celldata.push({ r: 7, c: 0, v: { v: "Door & Window Takeoff Estimation", m: "Door & Window Takeoff Estimation", bl: 1, fs: 12 } });

      // Header Row (Row 8 = Excel Row 9)
      estCols.forEach((h: string, c: number) => {
        celldata.push({ r: 8, c, v: { v: h, m: h, bl: 1, bg: '#2F5496', fc: '#ffffff', ht: 1, vt: 1 } });
      });

      // Group items by floor
      const floorsDict: Record<string, any[]> = {};
      items.forEach(item => {
        const fl = String(item["FLOOR / LEVEL"] || item.floor || item.level || "1ST FLOOR").trim().toUpperCase();
        if (!floorsDict[fl]) floorsDict[fl] = [];
        floorsDict[fl].push(item);
      });

      let currRow = 9;
      Object.entries(floorsDict).forEach(([flName, flItems]) => {
        // Floor Banner Row
        celldata.push({ r: currRow, c: 0, v: { v: flName, m: flName, bl: 1, bg: '#2F5496', fc: '#ffffff', ht: 0, vt: 1 } });
        currRow++;

        const flStartRow = currRow;
        flItems.forEach(item => {
          const doorMat = String(item["DOOR MATERIAL"] || item.door_material || "").trim();
          const frameMat = String(item["FRAME MATERIAL"] || item.frame_material || "").trim();
          const ieStatus = String(item["INT/EXT"] || item._reconciled_int_ext || item.int_ext || "Interior");
          const opMode = String(item["Opening Mode"] || item._reconciled_opening_mode || item.opening_mode || "Single");

          const isStorefront = (doorMat === "-" || frameMat === "-" || opMode === "STOREFRONT" || ieStatus === "Not in Scope");
          let markFill = '#FFFF00'; // Default interior yellow
          if (isStorefront) markFill = '#FF00FF'; // Pink
          else if (ieStatus === 'Exterior') markFill = '#007FFF'; // Blue
          else if (ieStatus === 'Soft Exterior') markFill = '#92D050'; // Green
          else if (ieStatus === 'Window') markFill = '#FFC000'; // Orange

          estCols.forEach((colName, cIdx) => {
            const cnLower = colName.toLowerCase().trim();
            let val: any = '';
            if (cnLower === 'qty') {
              val = item.qty ?? item.QTY ?? item.count ?? 1;
            } else if (['floor / level', 'floor', 'level'].includes(cnLower)) {
              val = flName;
            } else if (['location', 'room name'].includes(cnLower)) {
              val = getItemLocation(item);
            } else if (['opening mode', 'opening_mode'].includes(cnLower)) {
              val = isStorefront ? 'STOREFRONT' : opMode;
            } else if (['int/ext', 'int_ext'].includes(cnLower)) {
              val = isStorefront ? 'Not in Scope' : ieStatus;
            } else if (['takeoff notes', 'takeoff_notes', 'estimator notes'].includes(cnLower)) {
              val = item["Takeoff Notes"] || item["COMMENTS"] || (isStorefront ? "SEE STOREFRONT SCHEDULE." : "");
            } else {
              val = getDictVal(item, colName);
            }

            const cellObj: any = { v: val, m: String(val), ht: 1, vt: 1 };
            if (['mark', 'type', 'number', 'door mark', 'door no'].includes(cnLower)) {
              cellObj.bg = markFill;
            }
            celldata.push({ r: currRow, c: cIdx, v: cellObj });
          });
          currRow++;
        });

        // Floor Subtotal Row
        celldata.push({ r: currRow, c: 0, v: { v: `=SUM(A${flStartRow + 1}:A${currRow})`, m: "", bl: 1 } });
        celldata.push({ r: currRow, c: 1, v: { v: `${flName} TOTAL`, m: `${flName} TOTAL`, bl: 1 } });
        currRow += 2;
      });

      return {
        name: 'Estimation',
        color: '#ffaa00',
        status: order === 0 ? 1 : 0,
        order,
        row: Math.max(100, currRow + 10),
        column: Math.max(30, estCols.length + 2),
        celldata,
        config: { columnlen: Object.fromEntries(estCols.map((_: any, i: number) => [i, 140])) }
      };
    };

    const sheets = [];
    if (items.length > 0) sheets.push(generateRawSheet(items, 'Schedule', '#4caf50', sheets.length));
    if (items.length > 0) sheets.push(generateEstimationSheet(sheets.length));

    return sheets;
  }, [doors, windows, cvLookup, hasScheduleData, sessionState?.specifications_insights]);

  const workbookKey = useMemo(() => {
    return `${sessionId}_${doors.length}_${windows.length}_${JSON.stringify(doors.map((d: any) => d.mark || d.type))}_${JSON.stringify(windows.map((w: any) => w.mark || w.type))}_${sessionState?.updated_at || ''}`;
  }, [sessionId, doors, windows, sessionState?.updated_at]);

  const [showWorkbook, setShowWorkbook] = React.useState(false);
  const [editedWorkbookData, setEditedWorkbookData] = React.useState<any[]>([]);
  const [isDownloading, setIsDownloading] = React.useState(false);
  const containerRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    if (workbookData && workbookData.length > 0) {
      setEditedWorkbookData(workbookData);
    }
  }, [workbookData]);

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

  const handleDownloadExcel = async (e: React.MouseEvent) => {
    e.preventDefault();
    setIsDownloading(true);
    try {
      const token = typeof window !== 'undefined' ? localStorage.getItem('costmate_token') : null;
      const sheetsToExport = (editedWorkbookData && editedWorkbookData.length > 0) ? editedWorkbookData : workbookData;

      const res = await fetch(`${api.baseUrl}/api/download/${sessionId}/custom-excel`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {})
        },
        body: JSON.stringify({ sheets: sheetsToExport })
      });

      if (!res.ok) {
        throw new Error('Failed to generate custom Excel file.');
      }

      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `Costmate_Estimate_${sessionId}.xlsx`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error("Excel custom download error, falling back:", err);
      window.location.href = downloadUrl;
    } finally {
      setIsDownloading(false);
    }
  };

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
            href={api.downloadPlanUrl(sessionId)}
            download
            className="flex items-center gap-2 text-sm px-5 py-2.5 rounded-xl no-underline transition-all hover:scale-[1.02] border"
            style={{ borderColor: 'var(--panel-border)', background: 'var(--panel-header)', color: 'var(--foreground)' }}
          >
            <Download className="w-4 h-4" />
            Download Highlighted Plan
          </a>
          <button
            type="button"
            onClick={handleDownloadExcel}
            disabled={isDownloading}
            className="btn-accent flex items-center gap-2 text-sm px-5 py-2.5 rounded-xl no-underline transition-all hover:scale-[1.02] cursor-pointer disabled:opacity-50"
          >
            <Download className="w-4 h-4" />
            {isDownloading ? 'Exporting Excel...' : 'Download Excel'}
          </button>
        </div>
      </div>

      {/* ── Content Area ── */}
      {hasScheduleData ? (
        <div
          ref={containerRef}
          className="w-full flex-1 rounded-2xl overflow-hidden border shadow-xl relative costmate-fortune-wrapper"
          style={{ borderColor: 'var(--panel-border)' }}
        >
          {showWorkbook && (
            <Workbook
              key={workbookKey}
              data={workbookData}
              onChange={(data) => setEditedWorkbookData(data)}
            />
          )}
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
