'use client';

import React, { useState, useRef, useEffect } from 'react';
import { 
  X, Upload, Check, Loader2, Plus, Building2, 
  ChevronRight, Layers, LayoutGrid, Hammer, 
  Trash2, CheckCircle2, ChevronDown, ChevronUp, FileText, Settings2, Pickaxe, Maximize2
} from 'lucide-react';
import { api } from '../lib/api';

interface SetupWizardModalProps {
  isOpen: boolean;
  onClose: () => void;
  onTakeoffStarted: (sessionId: string, filename: string) => void;
}

export default function SetupWizardModal({ isOpen, onClose, onTakeoffStarted }: SetupWizardModalProps) {
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [isScanning, setIsScanning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isUploadingDoor, setIsUploadingDoor] = useState(false);
  const [isUploadingWindow, setIsUploadingWindow] = useState(false);
  const [isUploadingSpec, setIsUploadingSpec] = useState(false);
  const [uploadingFloorId, setUploadingFloorId] = useState<number | null>(null);
  const [draftSessionId, setDraftSessionId] = useState<string | null>(null);
  
  // --- Interactive Crop States ---
  const [isCropModalOpen, setIsCropModalOpen] = useState(false);
  const [cropFile, setCropFile] = useState<File | null>(null);
  const [cropType, setCropType] = useState<'door' | 'window'>('door');
  const [cropRect, setCropRect] = useState<{ startX: number; startY: number; currentX: number; currentY: number } | null>(null);
  const [isDrawing, setIsDrawing] = useState(false);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [cropPdf, setCropPdf] = useState<any>(null);
  const [cropPageNum, setCropPageNum] = useState(1);
  const [cropTotalPages, setCropTotalPages] = useState(0);
  const [pdfLoading, setPdfLoading] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const [pdfScale, setPdfScale] = useState(1.0);
  const [zoomText, setZoomText] = useState("100");
  const renderTaskRef = useRef<any>(null);
  const [pageWidth, setPageWidth] = useState(0);
  const [pageHeight, setPageHeight] = useState(0);
  const [scaleInitialized, setScaleInitialized] = useState(false);

  const [cropStage, setCropStage] = useState<'crop' | 'map'>('crop');
  const [extractedItems, setExtractedItems] = useState<any[]>([]);
  const [headerMappings, setHeaderMappings] = useState<Record<string, string>>({});
  const [editingRowIndex, setEditingRowIndex] = useState<number | null>(null);
  const [editRowData, setEditRowData] = useState<any | null>(null);

  // --- Global Settings ---
  const [globalSettings, setGlobalSettings] = useState({
    projectName: 'New Project',
    buildingType: 'Residential',
    basementPresent: 'No',
    numBasements: 1,
    numFloors: 1,
    plotDimensions: '',

    footings: [] as any[],
    columns: [] as any[],
    beams: [] as any[],
    
    doorScheduleFileName: '' as string,
    windowScheduleFileName: '' as string,
    specificationFileName: '' as string,
    specificationsText: '' as string,
    scheduleRegistry: null as any
  });

  // --- Floors Data ---
  const [floors, setFloors] = useState<any[]>([
    {
      id: 1,
      name: 'Ground Floor',
      fileName: null,
      file: null,
      floorSpecs: { 
        floorHeight: '3.0m', 
        staircaseStepsCount: '',
        staircaseTreadDim: '',
        staircaseTreadMaterial: 'Granite',
        staircaseRiserDim: '',
        staircaseRiserMaterial: 'Granite',
        staircaseWidth: '',
        midlandingDim: '',
        midlandingMaterial: 'Granite',
        hasStaircaseRailing: 'No',
        staircaseRailingDim: '',
        staircaseRailingMaterial: 'MS (Mild Steel)'
      },
      rooms: []
    }
  ]);
  
  const [activeFloorId, setActiveFloorId] = useState(1);
  const activeFloorIndex = Math.max(0, floors.findIndex(f => f.id === activeFloorId));
  const activeFloor = floors[activeFloorIndex] || floors[0] || {
    id: 1,
    name: 'Ground Floor',
    fileName: null,
    file: null,
    floorSpecs: { floorHeight: '3.0m', footings: [], columns: [], beams: [] },
    rooms: []
  };

  const [activeTab, setActiveTab] = useState<'rooms' | 'floorSpecs'>('rooms');
  const [expandedRoomId, setExpandedRoomId] = useState<number | null>(null);
  const [hoveredRoomId, setHoveredRoomId] = useState<number | null>(null);
  const [draggedFloorIdx, setDraggedFloorIdx] = useState<number | null>(null);

  // --- Load pdf.js via CDN ---
  const loadPdfJs = () => {
    return new Promise<any>((resolve) => {
      const win = window as any;
      if (win.pdfjsLib) {
        resolve(win.pdfjsLib);
        return;
      }
      const script = document.createElement('script');
      script.src = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.4.120/pdf.min.js';
      script.onload = () => {
        win.pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.4.120/pdf.worker.min.js';
        resolve(win.pdfjsLib);
      };
      document.body.appendChild(script);
    });
  };

  // Sync zoom input text with scale changes
  useEffect(() => {
    setZoomText(Math.round(pdfScale * 100).toString());
  }, [pdfScale]);

  // Initialize PDF document
  useEffect(() => {
    if (!isCropModalOpen || !cropFile) {
      setCropPdf(null);
      setCropTotalPages(0);
      setCropPageNum(1);
      setScaleInitialized(false);
      return;
    }

    let active = true;
    const initPdf = async () => {
      setPdfLoading(true);
      try {
        const pdfjs = await loadPdfJs();
        const reader = new FileReader();
        reader.onload = async () => {
          if (!active) return;
          try {
            const loadingTask = pdfjs.getDocument({ data: new Uint8Array(reader.result as ArrayBuffer) });
            const pdfDoc = await loadingTask.promise;
            if (!active) return;
            setCropPdf(pdfDoc);
            setCropTotalPages(pdfDoc.numPages);
            setCropPageNum(1);
          } catch (err) {
            console.error("Failed to load PDF doc:", err);
            setError("⚠️ Failed to load PDF file.");
            setIsCropModalOpen(false);
          }
        };
        reader.readAsArrayBuffer(cropFile);
      } catch (err) {
        console.error("Failed to initialize pdf.js:", err);
        setError("⚠️ Failed to initialize PDF renderer library.");
        setIsCropModalOpen(false);
      } finally {
        if (active) setPdfLoading(false);
      }
    };

    initPdf();

    return () => {
      active = false;
    };
  }, [isCropModalOpen, cropFile]);

  // Render PDF Page (with cancellation support)
  useEffect(() => {
    if (!cropPdf) return;

    let active = true;
    const render = async () => {
      // Cancel any ongoing rendering task
      if (renderTaskRef.current) {
        try {
          renderTaskRef.current.cancel();
        } catch (e) {
          // ignore cancel error
        }
      }

      setPdfLoading(true);
      try {
        const page = await cropPdf.getPage(cropPageNum);
        if (!active) return;

        const originalViewport = page.getViewport({ scale: 1.0 });
        if (active) {
          setPageWidth(originalViewport.width);
          setPageHeight(originalViewport.height);
        }

        // Render matching physical device pixels 1-to-1 for pixel-perfect sharpness
        const dpr = window.devicePixelRatio || 1;
        const renderViewport = page.getViewport({ scale: pdfScale * dpr });
        const canvas = canvasRef.current;
        if (!canvas || !active) return;
        const context = canvas.getContext('2d');
        if (!context || !active) return;

        canvas.width = renderViewport.width;
        canvas.height = renderViewport.height;

        const renderTask = page.render({ canvasContext: context, viewport: renderViewport });
        renderTaskRef.current = renderTask;

        await renderTask.promise;
        if (active) {
          setCropRect(null); // Reset selection on page render completion
        }
      } catch (err: any) {
        if (err.name === 'RenderingCancelledException') {
          // Normal cancellation, ignore error
          return;
        }
        console.error("Failed to render page:", err);
      } finally {
        if (active) setPdfLoading(false);
      }
    };

    render();

    return () => {
      active = false;
      if (renderTaskRef.current) {
        try {
          renderTaskRef.current.cancel();
        } catch (e) {}
      }
    };
  }, [cropPageNum, cropPdf, pdfScale]);

  // Global window mouseup listener to handle releases outside the canvas
  useEffect(() => {
    if (!isDrawing) return;
    const handleGlobalMouseUp = () => {
      setIsDrawing(false);
    };
    window.addEventListener('mouseup', handleGlobalMouseUp);
    return () => {
      window.removeEventListener('mouseup', handleGlobalMouseUp);
    };
  }, [isDrawing]);

  const handleCanvasMouseDown = (e: React.MouseEvent<HTMLDivElement>) => {
    if (pdfLoading || extracting) return;
    e.preventDefault(); // Prevent browser default drag/select behaviors
    const rect = e.currentTarget.getBoundingClientRect();
    const startX = e.clientX - rect.left;
    const startY = e.clientY - rect.top;
    
    setCropRect({
      startX,
      startY,
      currentX: startX,
      currentY: startY
    });
    setIsDrawing(true);
  };

  const handleCanvasMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!isDrawing || !cropRect) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const currentX = Math.max(0, Math.min(rect.width, e.clientX - rect.left));
    const currentY = Math.max(0, Math.min(rect.height, e.clientY - rect.top));

    setCropRect({
      ...cropRect,
      currentX,
      currentY
    });
  };

  const handleCanvasMouseUp = () => {
    setIsDrawing(false);
  };

  const handleExtractCrop = async () => {
    if (!cropRect || !cropFile || !draftSessionId) return;

    setError(null);
    setExtracting(true);
    try {
      const x0 = Math.min(cropRect.startX, cropRect.currentX) / pdfScale;
      const y0 = Math.min(cropRect.startY, cropRect.currentY) / pdfScale;
      const x1 = Math.max(cropRect.startX, cropRect.currentX) / pdfScale;
      const y1 = Math.max(cropRect.startY, cropRect.currentY) / pdfScale;

      const pageIdx = cropPageNum - 1;

      const res = await api.cropDraftSchedule(
        draftSessionId,
        cropFile,
        x0,
        y0,
        x1,
        y1,
        pageIdx
      );

      if (res && res.schedule_registry) {
        const rawReg = res.schedule_registry;
        const items = Array.isArray(rawReg) ? rawReg : (rawReg.instance_schedule || []);
        if (Array.isArray(items) && items.length > 0) {
          const keys = Array.from(new Set(items.flatMap(item => Object.keys(item))));
          const filteredKeys = keys.filter(k => k !== 'needs_review' && k !== '_schedule_type');
          const initialMappings: Record<string, string> = {};
          filteredKeys.forEach(k => {
            initialMappings[k] = k;
          });
          setHeaderMappings(initialMappings);
          setExtractedItems(items);
          setCropStage('map');
        } else {
          setError("⚠️ Extraction completed, but no rows were found. Please adjust your crop selection.");
        }
      }
    } catch (err: any) {
      console.error("Crop extraction failed:", err);
      setError("⚠️ Failed to parse table from selection: " + (err.message || err));
    } finally {
      setExtracting(false);
    }
  };

  const handleConfirmSchema = () => {
    if (extractedItems.length === 0) return;

    const mapped = extractedItems.map((item) => {
      const newItem: any = { _schedule_type: cropType, needs_review: false };
      let userMarkValue = "";

      Object.keys(item).forEach((oldKey) => {
        if (oldKey === '_schedule_type' || oldKey === 'needs_review') return;
        const newKey = headerMappings[oldKey]?.trim() || oldKey;
        const val = item[oldKey];
        newItem[newKey] = val;

        // Track user edited mark value from mapped columns
        const nkLower = newKey.toLowerCase();
        if (oldKey === 'mark' || nkLower === 'mark' || nkLower === 'door number' || nkLower === 'door no' || nkLower === 'door mark') {
          if (val && String(val).trim()) {
            userMarkValue = String(val).trim().upper ? String(val).trim().toUpperCase() : String(val).trim();
          }
        }
      });

      // Synchronize primary mark key with user's edited cell value
      if (userMarkValue) {
        newItem["mark"] = userMarkValue;
      }
      return newItem;
    });


    setGlobalSettings(prev => {
      const oldReg = prev.scheduleRegistry || { type_registry: { doors: [], windows: [] }, instance_schedule: [] };
      const scheduleNameField = cropType === 'door' ? ('doorScheduleFileName' as const) : ('windowScheduleFileName' as const);
      
      let prevNames: string[] = [];
      if (prev[scheduleNameField]) {
        prevNames = prev[scheduleNameField].split(", ");
      }
      if (!prevNames.includes(cropFile!.name)) {
        prevNames.push(cropFile!.name);
      }

      return {
        ...prev,
        [scheduleNameField]: prevNames.join(", "),
        scheduleRegistry: {
          ...oldReg,
          type_registry: {
            doors: [...(oldReg.type_registry?.doors || [])],
            windows: [...(oldReg.type_registry?.windows || [])]
          },
          instance_schedule: [...(oldReg.instance_schedule || []), ...mapped]
        }
      };
    });

    // Reset native input values to allow uploading the same file again
    const doorEl = document.getElementById('door-schedule-upload') as HTMLInputElement;
    if (doorEl) doorEl.value = '';
    const winEl = document.getElementById('window-schedule-upload') as HTMLInputElement;
    if (winEl) winEl.value = '';

    // Reset crop modal states
    setIsCropModalOpen(false);
    setCropFile(null);
    setCropPdf(null);
    setExtractedItems([]);
    setHeaderMappings({});
    setCropStage('crop');
  };

  // Structural Temp States
  const [newFooting, setNewFooting] = useState({ code: 'F1', width: '', length: '', depth: '', excavDepth: '', count: '1' });
  const [newColumn, setNewColumn] = useState({ code: 'C1', width: '', depth: '', shape: 'Rectangle', termFloor: '3', count: '1' });
  const [newBeam, setNewBeam] = useState({ code: 'B1', width: '', depth: '', avgSpan: '', count: '1' });

  // Modal States for Rooms
  const [doorModalRoomIdx, setDoorModalRoomIdx] = useState<number | null>(null);
  const [windowModalRoomIdx, setWindowModalRoomIdx] = useState<number | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  if (!isOpen) return null;

  // --- Handlers ---
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setError(null);
    setLoading(true);
    setUploadingFloorId(activeFloorId);
    try {
      let filename = file.name;
      let scannedRooms: any[] = [];
      let pageUrls: string[] = [];
      
      let currentSid = draftSessionId;
      if (!currentSid) {
        const data = await api.createDraftSession(globalSettings.projectName);
        currentSid = data.session_id;
        setDraftSessionId(currentSid);
      }
      

      let rawUrl = '';
      if (currentSid) {
        const res = await api.uploadDraftFile(currentSid, file);
        filename = res.filename;
        if (res.page_paths && res.page_paths.length > 0) {
          pageUrls = res.page_paths;
        }
        rawUrl = res.raw_url;
        
        // Skip AI room detection scanning at upload stage to save API cost and latency
        scannedRooms = [];
      }
      
      const newFloors = [...floors];
      newFloors[activeFloorIndex].fileName = filename;
      newFloors[activeFloorIndex].file = file;
      newFloors[activeFloorIndex].pageUrls = pageUrls;
      newFloors[activeFloorIndex].rawUrl = rawUrl;
      
      if (scannedRooms.length > 0) {
        newFloors[activeFloorIndex].rooms = scannedRooms;
        setActiveTab('rooms');
      }
      setFloors(newFloors);
    } catch (err: any) {
      setError('Upload failed: ' + err.message);
    } finally {
      setLoading(false);
      setUploadingFloorId(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleAddFloor = () => {
    const newId = Date.now();
    const nextFloorNumber = floors.length + 1;
    const newFloor = {
      id: newId,
      name: `Floor ${nextFloorNumber}`,
      fileName: null,
      file: null,
      floorSpecs: { floorHeight: '3.0m', staircase: '', footings: [], columns: [], beams: [] },
      rooms: []
    };
    setFloors([...floors, newFloor]);
    setActiveFloorId(newId);
  };

  const handleAddRoom = () => {
    const newFloors = [...floors];
    const newRoomId = Date.now();
    newFloors[activeFloorIndex].rooms.push({
      id: newRoomId, name: 'New Room', dimensions: '', tiles: 'Vitrified', pop: 'No', 
      skirting: '4 inch', dado: 'None', 
      hasBalconyRailing: 'No', balconyRailingDim: '', balconyRailingMaterial: 'MS (Mild Steel)',
      doors: [], windows: []
    });
    setFloors(newFloors);
    setExpandedRoomId(newRoomId);
    setActiveTab('rooms');
  };

  const updateRoom = (rIdx: number, field: string, value: string) => {
    const newFloors = [...floors];
    newFloors[activeFloorIndex].rooms[rIdx][field] = value;
    setFloors(newFloors);
  };

  const handleAddDoor = (rIdx: number) => {
    const newFloors = [...floors];
    const room = newFloors[activeFloorIndex].rooms[rIdx];
    room.doors.push({
      id: Date.now(), code: `D${room.doors.length + 1}`, width: '0.9', height: '2.1', 
      shutterMaterial: 'Flush Door', frameType: 'Teak Wood', count: '1'
    });
    setFloors(newFloors);
  };

  const updateDoor = (rIdx: number, dIdx: number, field: string, value: string) => {
    const newFloors = [...floors];
    newFloors[activeFloorIndex].rooms[rIdx].doors[dIdx][field] = value;
    setFloors(newFloors);
  };

  const removeDoor = (rIdx: number, dIdx: number) => {
    const newFloors = [...floors];
    newFloors[activeFloorIndex].rooms[rIdx].doors.splice(dIdx, 1);
    setFloors(newFloors);
  };

  const handleAddWindow = (rIdx: number) => {
    const newFloors = [...floors];
    const room = newFloors[activeFloorIndex].rooms[rIdx];
    room.windows.push({
      id: Date.now(), code: `W${room.windows.length + 1}`, width: '1.5', height: '1.5', material: 'UPVC', 
      grills: 'Grill', hasSillJamb: true, sillWidth: '0.15', jambWidth: '0.15', qty: '1'
    });
    setFloors(newFloors);
  };

  const updateWindow = (rIdx: number, wIdx: number, field: string, value: any) => {
    const newFloors = [...floors];
    newFloors[activeFloorIndex].rooms[rIdx].windows[wIdx][field] = value;
    setFloors(newFloors);
  };

  const removeWindow = (rIdx: number, wIdx: number) => {
    const newFloors = [...floors];
    newFloors[activeFloorIndex].rooms[rIdx].windows.splice(wIdx, 1);
    setFloors(newFloors);
  };

  const updateFloorSpec = (field: string, value: string) => {
    const newFloors = [...floors];
    newFloors[activeFloorIndex].floorSpecs[field] = value;
    setFloors(newFloors);
  };

  const updateStructuralItem = (type: 'footings' | 'columns' | 'beams', idx: number, field: string, value: string) => {
    const newSettings: any = { ...globalSettings };
    newSettings[type][idx][field] = value;
    setGlobalSettings(newSettings);
  };

  const addStructuralItem = (type: 'footings' | 'columns' | 'beams', item: any, resetState: any) => {
    const newSettings: any = { ...globalSettings };
    newSettings[type].push({ ...item, id: Date.now() });
    setGlobalSettings(newSettings);
    resetState();
  };

  const removeStructuralItem = (type: 'footings' | 'columns' | 'beams', idx: number) => {
    const newSettings: any = { ...globalSettings };
    newSettings[type].splice(idx, 1);
    setGlobalSettings(newSettings);
  };

  const handleCopySpecs = (sourceFloorIdStr: string) => {
    if (sourceFloorIdStr === 'None') return;
    const sourceFloor = floors.find(f => f.id.toString() === sourceFloorIdStr);
    if (!sourceFloor) return;
    const newFloors = [...floors];
    newFloors[activeFloorIndex].floorSpecs = JSON.parse(JSON.stringify(sourceFloor.floorSpecs));
    newFloors[activeFloorIndex].rooms = JSON.parse(JSON.stringify(sourceFloor.rooms));
    setFloors(newFloors);
  };

  const handleDeleteFloor = (e: React.MouseEvent, id: number) => {
    e.stopPropagation();
    if (floors.length <= 1) {
      const resetFloor = [{
        id: Date.now(),
        name: 'Ground Floor',
        file: null,
        fileName: '',
        pageUrls: [],
        rooms: [],
        floorSpecs: {
          floorHeight: '3.0m',
          staircaseStepsCount: '',
          staircaseTreadDim: '',
          staircaseTreadMaterial: 'Granite',
          staircaseRiserDim: '',
          staircaseRiserMaterial: 'Granite',
          staircaseWidth: '',
          midlandingDim: '',
          midlandingMaterial: 'Granite',
          hasStaircaseRailing: 'No',
          staircaseRailingDim: '',
          staircaseRailingMaterial: 'MS (Mild Steel)'
        }
      }];
      setFloors(resetFloor);
      setActiveFloorId(resetFloor[0].id);
      return;
    }
    const newFloors = floors.filter(f => f.id !== id);
    setFloors(newFloors);
    if (activeFloorId === id) {
      setActiveFloorId(newFloors[0].id);
    }
  };

  const handleDropFloor = (dropIdx: number) => {
    if (draggedFloorIdx === null || draggedFloorIdx === dropIdx) return;
    const newFloors = [...floors];
    const draggedItem = newFloors.splice(draggedFloorIdx, 1)[0];
    newFloors.splice(dropIdx, 0, draggedItem);
    setFloors(newFloors);
    setDraggedFloorIdx(null);
  };

  const handleNextStep = async () => {
    if (step === 1 && !draftSessionId) {
      setLoading(true);
      try {
        const data = await api.createDraftSession(globalSettings.projectName);
        setDraftSessionId(data.session_id);
      } catch (err: any) {
        setError(err.message);
        setLoading(false);
        return;
      }
      setLoading(false);
    }
    setStep(step + 1);
  };

  const handleFinish = async () => {
    setLoading(true);
    try {
      let sid = draftSessionId;
      if (!sid) {
        const data = await api.createDraftSession(globalSettings.projectName);
        sid = data.session_id;
        setDraftSessionId(sid);
      }
      
      // Ensure all files are uploaded
      const newFloors = [...floors];
      for (let i = 0; i < newFloors.length; i++) {
        const f = newFloors[i];
        if (f.file && (!f.pageUrls || f.pageUrls.length === 0)) {
           const res = await api.uploadDraftFile(sid!, f.file);
           newFloors[i].fileName = res.filename;
           if (res.page_paths && res.page_paths.length > 0) {
             newFloors[i].pageUrls = res.page_paths;
           }
           newFloors[i].rawUrl = res.raw_url;
        }
      }
      setFloors(newFloors);

      const intakeData = { globalSettings, floors: newFloors };
      const resData = await api.startDraftTakeoff(sid!, intakeData);
      onTakeoffStarted(resData.session_id, resData.project_name);
      onClose();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const renderInput = (label: string, value: string, onChange: (v: string) => void, placeholder: string = "") => (
    <div className="flex flex-col gap-1.5 w-full">
      <label className="text-[10px] font-bold text-fg/60 uppercase tracking-[0.15em] font-mono pl-0.5">{label}</label>
      <input 
        value={value} 
        onChange={(e) => onChange(e.target.value)} 
        placeholder={placeholder}
        className="w-full bg-transparent border-b-2 border-border/50 hover:border-border focus:border-accent px-1 py-2 text-sm text-fg font-mono placeholder:text-muted focus:outline-none transition-all shadow-none rounded-none"
      />
    </div>
  );

  const renderSelect = (label: string, value: string, onChange: (v: string) => void, options: string[]) => (
    <div className="flex flex-col gap-1.5 w-full">
      <label className="text-[10px] font-bold text-fg/60 uppercase tracking-[0.15em] font-mono pl-0.5">{label}</label>
      <select 
        value={value} 
        onChange={(e) => onChange(e.target.value)} 
        className="w-full bg-transparent border-b-2 border-border/50 hover:border-border focus:border-accent px-1 py-2 text-sm text-fg font-mono focus:outline-none transition-all cursor-pointer shadow-none rounded-none appearance-none"
      >
        {options.map(opt => <option key={opt} value={opt} className="font-sans bg-bg">{opt}</option>)}
      </select>
    </div>
  );

  const renderGridInput = (value: string, onChange: (v: string) => void, placeholder: string = "") => (
    <input 
      value={value} 
      onChange={(e) => onChange(e.target.value)} 
      placeholder={placeholder}
      className="w-full bg-bg border border-border rounded-md px-3 py-2 text-sm text-fg placeholder:text-muted focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent/50 transition-all"
    />
  );

  const renderGridSelect = (value: string, onChange: (v: string) => void, options: string[]) => (
    <select 
      value={value} 
      onChange={(e) => onChange(e.target.value)} 
      className="w-full bg-bg border border-border rounded-md px-3 py-2 text-sm text-fg focus:outline-none focus:border-accent transition-all cursor-pointer"
    >
      {options.map(opt => <option key={opt} value={opt}>{opt}</option>)}
    </select>
  );

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-6 sm:p-10 bg-black/60 backdrop-blur-sm animate-in fade-in duration-300 font-sans">
      <div className="flex w-full h-full max-w-[1400px] max-h-[90vh] bg-bg rounded-xl shadow-[0_20px_50px_rgba(0,0,0,0.5)] overflow-hidden border border-white/10 relative">
        {/* Left Side: Technical Blueprint Visuals */}
        <div 
          className="hidden lg:block w-1/3 relative border-r border-border overflow-hidden shrink-0 bg-[#0f172a]"
          style={{ backgroundImage: 'radial-gradient(rgba(255,255,255,0.15) 1px, transparent 1px)', backgroundSize: '20px 20px' }}
        >
          {/* Faded construction image */}
          <img src="/construction-bg.png" alt="Blueprint" className="absolute inset-0 w-full h-full object-cover opacity-10 grayscale mix-blend-overlay pointer-events-none" />
          
          {/* CAD Registration Marks */}
          <div className="absolute top-6 left-6 text-white/30 font-mono text-sm leading-none">+</div>
          <div className="absolute top-6 right-6 text-white/30 font-mono text-sm leading-none">+</div>
          <div className="absolute bottom-6 left-6 text-white/30 font-mono text-sm leading-none">+</div>
          <div className="absolute bottom-6 right-6 text-white/30 font-mono text-sm leading-none">+</div>

          <div className="absolute bottom-16 left-12 pr-12 z-10">
             <div className="w-12 h-12 bg-transparent flex items-center justify-center border border-white/20 mb-8 rounded-none">
                <Building2 className="w-5 h-5 text-white/70" />
             </div>
             <h2 className="text-2xl font-black text-white mb-4 tracking-[0.2em] uppercase font-mono leading-tight">Project<br/>Initialization</h2>
             <p className="text-white/50 text-xs leading-relaxed font-mono tracking-widest uppercase mt-6 border-l border-white/20 pl-4">
               Configure global parameters<br/>and upload schedules to begin<br/>AI-assisted civil estimation.
             </p>
          </div>
        </div>
        
        {/* Right Side: Interactive Form */}
        <div 
          className="flex-1 flex flex-col h-full bg-bg overflow-hidden relative"
          style={{ backgroundImage: 'radial-gradient(rgba(128,128,128,0.15) 1px, transparent 1px)', backgroundSize: '20px 20px' }}
        >
        
        {/* Header */}
        <div className="flex items-center justify-between px-10 py-6 shrink-0 z-10 bg-bg/80 backdrop-blur-sm border-b border-border/50">
          <div className="flex items-center gap-3">
            <h2 className="text-xl font-black uppercase tracking-widest text-fg">Project Config</h2>
          </div>
          <button onClick={onClose} className="p-2.5 bg-panel hover:bg-panel rounded-xl border border-border text-muted hover:text-fg transition-all">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Stepper */}
        <div className="px-10 pb-6 border-b border-border/50 flex items-center gap-12 shrink-0 z-10">
          {[
            { num: 1, label: 'Global Setup' },
            { num: 2, label: 'Floor Layouts & Details' }
          ].map((s, i) => (
            <React.Fragment key={s.num}>
              <div className="flex items-center gap-4 cursor-pointer group" onClick={() => setStep(s.num)}>
                <div className={`w-9 h-9 rounded-full flex items-center justify-center text-sm font-bold transition-all ${step === s.num ? 'bg-accent text-accent-fg shadow-[0_0_15px_var(--accent)]' : step > s.num ? 'bg-accent/20 text-accent border border-accent/50' : 'bg-panel border border-border text-muted group-hover:bg-panel'}`}>
                  {step > s.num ? <Check className="w-4 h-4" /> : s.num}
                </div>
                <span className={`text-sm font-bold transition-colors tracking-wide ${step === s.num ? 'text-fg' : step > s.num ? 'text-fg opacity-80' : 'text-muted group-hover:text-fg opacity-60'}`}>{s.label}</span>
              </div>
              {i < 1 && <div className={`w-12 h-[2px] rounded-full ${step > s.num ? 'bg-accent/50' : 'bg-border'}`} />}
            </React.Fragment>
          ))}
        </div>

        {/* Error Banner */}
        {error && (
          <div className="mx-8 mt-4 bg-red-500/10 border border-red-500/50 rounded-lg p-3 flex items-center justify-between shrink-0">
            <span className="text-sm text-red-400 font-medium">{error}</span>
            <button onClick={() => setError(null)} className="p-1 rounded-md hover:bg-red-500/20 text-red-400 hover:text-red-300 transition-colors">
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* Content Area */}
        <div className="flex-1 flex overflow-hidden relative font-sans">
          
          {/* STEP 1: Global Settings */}
          {step === 1 && (
            <div className="flex-1 flex flex-col items-center p-10 overflow-y-auto custom-scrollbar animate-in fade-in slide-in-from-bottom-4">
              <div className="w-full max-w-2xl space-y-10">
                <div className="bg-panel border border-border shadow-sm rounded-lg p-8">
                  <h3 className="text-xs font-black text-fg mb-6 uppercase tracking-[0.2em] flex items-center gap-2">
                    <Settings2 className="w-4 h-4 text-accent"/> General Information
                  </h3>
                  <div className="space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                      {renderInput("Project Name", globalSettings.projectName, v => setGlobalSettings({...globalSettings, projectName: v}), "e.g. Skyline Towers")}
                      {renderSelect("Building Type", globalSettings.buildingType, v => setGlobalSettings({...globalSettings, buildingType: v}), ['Residential', 'Commercial', 'Apartment', 'Industrial', 'Other'])}
                    </div>
                  </div>
                </div>

                {/* GLOBAL SCHEDULES */}
                <div className="bg-panel border border-border shadow-sm rounded-lg p-8">
                  <h3 className="text-xs font-black text-fg mb-6 uppercase tracking-[0.2em] flex items-center gap-2">
                    <FileText className="w-4 h-4 text-accent"/> Schedules & Specifications (Optional)
                  </h3>
                  
                  <div className="flex flex-col gap-4">
                    {/* Door Schedule */}
                    <div className="flex items-center gap-4">
                      <button 
                        type="button"
                        onClick={() => document.getElementById('door-schedule-upload')?.click()}
                        disabled={isUploadingDoor || loading}
                        className="px-4 py-2 rounded-lg bg-panel hover:bg-panel border border-border flex items-center gap-2 text-sm font-medium transition-colors w-52 disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {isUploadingDoor ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
                        {isUploadingDoor ? "Processing..." : "Upload Door Schedule"}
                      </button>
                      <input 
                        id="door-schedule-upload"
                        type="file" 
                        multiple
                        className="hidden" 
                        onChange={async (e) => {
                          setError(null);
                          const files = e.target.files;
                          if (!files || files.length === 0) return;
                          
                          const file = files[0];
                          if (!file.name.toLowerCase().endsWith(".pdf")) {
                            setError("⚠️ Only PDF files are supported for table crop selection.");
                            return;
                          }
                          
                          setLoading(true);
                          try {
                            let sid = draftSessionId;
                            if (!sid) {
                              const data = await api.createDraftSession(globalSettings.projectName);
                              sid = data.session_id;
                              setDraftSessionId(sid);
                            }
                            setCropFile(file);
                            setCropType('door');
                            setIsCropModalOpen(true);
                          } catch (err: any) {
                            setError('⚠️ Failed to initialize session: ' + (err.message || err));
                          } finally {
                            setLoading(false);
                          }
                        }} 
                      />
                      {globalSettings.doorScheduleFileName && !isUploadingDoor && (
                        <div className="text-sm text-emerald-400 flex items-center gap-2 bg-emerald-500/10 px-3 py-1.5 rounded-lg border border-emerald-500/20 truncate max-w-xs">
                          <CheckCircle2 className="w-4 h-4 shrink-0" /> <span className="truncate">{globalSettings.doorScheduleFileName}</span>
                        </div>
                      )}
                    </div>

                    {/* Window Schedule */}
                    <div className="flex items-center gap-4">
                      <button 
                        type="button"
                        onClick={() => document.getElementById('window-schedule-upload')?.click()}
                        disabled={isUploadingWindow || loading}
                        className="px-4 py-2 rounded-lg bg-panel hover:bg-panel border border-border flex items-center gap-2 text-sm font-medium transition-colors w-52 disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {isUploadingWindow ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
                        {isUploadingWindow ? "Processing..." : "Upload Window Schedule"}
                      </button>
                      <input 
                        id="window-schedule-upload"
                        type="file" 
                        multiple
                        className="hidden" 
                        onChange={async (e) => {
                          setError(null);
                          const files = e.target.files;
                          if (!files || files.length === 0) return;
                          
                          const file = files[0];
                          if (!file.name.toLowerCase().endsWith(".pdf")) {
                            setError("⚠️ Only PDF files are supported for table crop selection.");
                            return;
                          }
                          
                          setLoading(true);
                          try {
                            let sid = draftSessionId;
                            if (!sid) {
                              const data = await api.createDraftSession(globalSettings.projectName);
                              sid = data.session_id;
                              setDraftSessionId(sid);
                            }
                            setCropFile(file);
                            setCropType('window');
                            setIsCropModalOpen(true);
                          } catch (err: any) {
                            setError('⚠️ Failed to initialize session: ' + (err.message || err));
                          } finally {
                            setLoading(false);
                          }
                        }} 
                      />
                      {globalSettings.windowScheduleFileName && !isUploadingWindow && (
                        <div className="text-sm text-emerald-400 flex items-center gap-2 bg-emerald-500/10 px-3 py-1.5 rounded-lg border border-emerald-500/20 truncate max-w-xs">
                          <CheckCircle2 className="w-4 h-4 shrink-0" /> <span className="truncate">{globalSettings.windowScheduleFileName}</span>
                        </div>
                      )}
                    </div>

                    {/* Specifications Document */}
                    <div className="flex items-center gap-4 border-t border-border pt-4">
                      <button 
                        type="button"
                        onClick={() => document.getElementById('specification-upload')?.click()}
                        disabled={isUploadingSpec || loading}
                        className="px-4 py-2 rounded-lg bg-panel hover:bg-panel border border-border flex items-center gap-2 text-sm font-medium transition-colors w-52 disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {isUploadingSpec ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
                        {isUploadingSpec ? "Processing..." : "Upload Specifications"}
                      </button>
                      <input 
                        id="specification-upload"
                        type="file" 
                        accept=".docx,.doc,.dotx,.dot,.txt,.pdf"
                        className="hidden" 
                        onChange={async (e) => {
                          setError(null);
                          const file = e.target.files?.[0];
                          if (!file) return;
                          setLoading(true);
                          setIsUploadingSpec(true);
                          try {
                            let sid = draftSessionId;
                            if (!sid) {
                              const data = await api.createDraftSession(globalSettings.projectName);
                              sid = data.session_id;
                              setDraftSessionId(sid);
                            }
                            const res = await api.uploadDraftSpecification(sid!, file);
                            setGlobalSettings(prev => ({
                              ...prev,
                              specificationFileName: file.name,
                              specificationsText: res.specifications_text
                            }));
                          } catch (err: any) {
                            setError('⚠️ ' + (err.message || 'Failed to upload specifications.'));
                          } finally {
                            setLoading(false);
                            setIsUploadingSpec(false);
                          }
                        }} 
                      />
                      {globalSettings.specificationFileName && !isUploadingSpec && (
                        <div className="text-sm text-emerald-400 flex items-center gap-2 bg-emerald-500/10 px-3 py-1.5 rounded-lg border border-emerald-500/20 truncate max-w-xs">
                          <CheckCircle2 className="w-4 h-4 shrink-0" /> <span className="truncate">{globalSettings.specificationFileName}</span>
                        </div>
                      )}
                    </div>
                  </div>
                  <p className="text-xs text-muted mt-4">
                    Upload schedules and specifications here. The system will ingest schedules and align estimations with your project specifications.
                  </p>
                  
                  {/* Schedule Preview */}
                  {globalSettings.scheduleRegistry && (
                    <div className="mt-4 p-4 border border-border rounded-lg bg-black overflow-auto max-h-64 custom-scrollbar">
                      <h4 className="text-sm font-bold text-fg mb-2 flex items-center gap-2">
                        <CheckCircle2 className="w-4 h-4 text-emerald-400" /> Parsed Schedule Data (Preview)
                      </h4>
                      <pre className="text-xs text-muted whitespace-pre-wrap select-text" draggable="false" style={{ userSelect: 'text', WebkitUserDrag: 'none' } as any}>
                        {JSON.stringify(globalSettings.scheduleRegistry, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* STEP 2: Floor Layouts & Details */}
          {step === 2 && (
            <div className="flex-1 flex h-full overflow-hidden animate-in fade-in">
              
              {/* Sidebar: Floors */}
              <div className="w-[260px] border-r border-border bg-bg/90 flex flex-col shrink-0 relative z-10 backdrop-blur-md">
                <div className="p-4 flex justify-between items-center border-b border-border z-10 bg-panel">
                  <span className="text-[10px] font-black text-fg uppercase tracking-[0.15em]">Levels</span>
                  <button onClick={handleAddFloor} className="p-1 rounded bg-bg border border-border hover:border-accent hover:text-accent transition-all text-muted">
                    <Plus className="w-4 h-4"/>
                  </button>
                </div>
                <div className="flex-1 overflow-y-auto p-3 space-y-2 custom-scrollbar z-10">
                  {floors.map((floor, index) => (
                    <div 
                      key={floor.id} 
                      onClick={() => setActiveFloorId(floor.id)}
                      draggable
                      onDragStart={(e) => {
                        setDraggedFloorIdx(index);
                        e.dataTransfer.effectAllowed = "move";
                      }}
                      onDragOver={(e) => e.preventDefault()}
                      onDrop={(e) => handleDropFloor(index)}
                      onDragEnter={(e) => e.preventDefault()}
                      onDragEnd={() => setDraggedFloorIdx(null)}
                      className={`p-3 rounded-xl border cursor-pointer transition-all flex items-center gap-3 group ${activeFloorId === floor.id ? 'bg-white/80 dark:bg-black/80 border-accent/50 shadow-[0_4px_20px_-4px_rgba(139,92,246,0.3)] text-fg' : 'bg-transparent border-transparent text-muted hover:bg-white/50 dark:hover:bg-black/50 hover:text-fg'} ${draggedFloorIdx === index ? 'opacity-50 border-dashed border-border bg-white/50' : ''}`}
                    >
                      <Layers className={`w-4 h-4 shrink-0 ${activeFloorId === floor.id ? 'text-accent' : ''}`} />
                      <div className="flex flex-col overflow-hidden flex-1">
                        <span className="text-sm font-semibold truncate">{floor.name}</span>
                        {floor.fileName && <span className="text-[10px] text-muted truncate">{floor.fileName}</span>}
                      </div>
                      <button 
                        onClick={(e) => handleDeleteFloor(e, floor.id)} 
                        className={`p-1.5 rounded-md transition-colors ${activeFloorId === floor.id ? 'text-accent hover:text-red-400 hover:bg-red-500/10' : 'text-muted hover:text-red-400 hover:bg-red-500/10 opacity-0 group-hover:opacity-100'}`}
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ))}
                </div>
              </div>

              {/* Main Floor Editor */}
              <div className="flex-1 flex flex-col h-full overflow-hidden relative">
                {/* Floor Header */}
                <div className="px-8 py-5 border-b border-white/20 dark:border-white/10 flex items-center justify-between shrink-0 glass-header">
                  <input 
                    value={activeFloor.name} 
                    onChange={e => { const nf = [...floors]; nf[activeFloorIndex].name = e.target.value; setFloors(nf); }} 
                    className="bg-transparent text-2xl font-bold text-fg outline-none border-b border-transparent focus:border-accent px-1 w-64 transition-all"
                    placeholder="Floor Name"
                  />
                  <div className="flex items-center gap-3 bg-white/40 dark:bg-black/40 border border-white/30 dark:border-white/10 rounded-lg p-1.5 px-3 shadow-sm">
                    <span className="text-xs text-muted font-bold">Copy Specs From:</span>
                    <select 
                      onChange={(e) => handleCopySpecs(e.target.value)}
                      className="bg-transparent text-xs text-fg outline-none font-bold cursor-pointer"
                    >
                      <option value="None">None</option>
                      {floors.filter(f => f.id !== activeFloor.id).map(f => <option key={f.id} value={f.id}>{f.name}</option>)}
                    </select>
                  </div>
                </div>

                <div className="flex-1 overflow-y-auto px-8 pb-8 custom-scrollbar relative">
                  <div className="w-full mx-auto flex flex-col gap-8 pt-8 max-w-5xl">
                    
                    {/* Top Col: Upload */}
                    <div className="w-full shrink-0 flex flex-col gap-3">
                      <div className="flex items-center justify-between">
                        <h3 className="text-sm font-bold text-muted uppercase tracking-widest">Floor Plan</h3>
                        {activeFloor.file && activeFloor.fileName && !loading && (
                          <div className="flex items-center gap-4">
                            <button onClick={() => window.open(URL.createObjectURL(activeFloor.file), '_blank')} className="text-xs font-bold text-sky-400 hover:text-sky-300 flex items-center gap-1.5 transition-colors">
                              <Maximize2 className="w-3.5 h-3.5"/> View Full
                            </button>
                            <button onClick={() => fileInputRef.current?.click()} className="text-xs font-bold text-accent hover:text-accent flex items-center gap-1.5 transition-colors">
                              <Upload className="w-3.5 h-3.5"/> Replace
                            </button>
                          </div>
                        )}
                      </div>
                      <div className="h-[140px] bg-sky-900/5 dark:bg-sky-500/5 border-2 border-dashed border-sky-600/30 dark:border-sky-400/20 rounded flex flex-col items-center justify-center p-4 text-center relative overflow-hidden">
                        <input type="file" ref={fileInputRef} onChange={handleFileUpload} accept=".pdf,.png,.jpg" className="hidden" />
                        {uploadingFloorId === activeFloor.id ? (
                          <div className="flex flex-col items-center">
                            <Loader2 className="w-8 h-8 animate-spin text-accent mb-3" />
                            <span className="text-sm font-bold text-accent">
                              {isScanning ? '✨ AI is detecting rooms...' : 'Uploading...'}
                            </span>
                          </div>
                        ) : activeFloor.file && activeFloor.fileName ? (
                          <div className="absolute inset-0 w-full h-full p-2 flex items-center justify-center group overflow-hidden">
                             <div className="relative max-w-full max-h-full flex items-center justify-center">
                               {activeFloor.pageUrls && activeFloor.pageUrls.length > 0 ? (
                                  <img src={activeFloor.pageUrls[0]} alt="Preview" className="max-w-full max-h-full object-contain rounded-xl relative z-0" style={{ maxHeight: '120px' }} />
                               ) : activeFloor.fileName.toLowerCase().endsWith('.pdf') ? (
                                  <iframe 
                                    src={`${URL.createObjectURL(activeFloor.file)}#toolbar=0&navpanes=0&scrollbar=0`} 
                                    className="w-full h-[120px] rounded-xl bg-panel relative z-0" 
                                  />
                               ) : (
                                  <img src={URL.createObjectURL(activeFloor.file)} alt="Preview" className="max-w-full max-h-full object-contain rounded-xl relative z-0" style={{ maxHeight: '120px' }} />
                               )}
                               
                               {/* Bounding Box Overlay */}
                               <div className="absolute top-0 left-0 w-full h-full pointer-events-none z-10 rounded-xl overflow-hidden">
                                 {activeFloor.rooms.map((r: any) => {
                                   if (!r.boundingBox || r.boundingBox.length !== 4) return null;
                                   const [ymin, xmin, ymax, xmax] = r.boundingBox;
                                   const isHovered = hoveredRoomId === r.id;
                                   return (
                                     <div 
                                       key={`bbox-${r.id}`}
                                       style={{
                                         top: `${ymin * 100}%`,
                                         left: `${xmin * 100}%`,
                                         height: `${(ymax - ymin) * 100}%`,
                                         width: `${(xmax - xmin) * 100}%`,
                                       }}
                                       className={`absolute border-2 transition-all duration-300 ${isHovered ? 'border-accent bg-accent text-accent-fg/30 shadow-[0_0_15px_rgba(139,92,246,0.6)] z-20' : 'border-emerald-500/40 bg-emerald-500/10 z-10'}`}
                                     />
                                   );
                                 })}
                               </div>
                             </div>
                          </div>
                        ) : (
                          <div 
                            onClick={() => fileInputRef.current?.click()}
                            className="flex flex-col items-center justify-center w-full h-full cursor-pointer group"
                          >
                            <div className="w-10 h-10 bg-white/50 dark:bg-black/50 rounded-full flex items-center justify-center mb-2 group-hover:bg-accent/20 group-hover:scale-110 transition-all duration-300"><Upload className="w-5 h-5 text-muted group-hover:text-accent" /></div>
                            <span className="text-sm font-bold text-fg mb-0.5">Upload Layout</span>
                            <span className="text-xs text-muted">PDF, PNG, JPG</span>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Bottom Col: Tabs & Content */}
                    <div className="w-full flex flex-col gap-4 min-w-0">
                      
                      {/* HEADER */}
                      <div className="z-20 pb-3">
                        {/* Sub-Tabs */}
                        <div className="flex items-center gap-2 border-b border-border pb-px">
                          <button onClick={() => setActiveTab('rooms')} className={`px-4 py-2 text-sm font-bold border-b-2 transition-all flex items-center gap-2 ${activeTab === 'rooms' ? 'border-accent text-accent' : 'border-transparent text-muted hover:text-fg'}`}>
                            <LayoutGrid className="w-4 h-4"/> Room-Wise Details
                          </button>
                          <button onClick={() => setActiveTab('floorSpecs')} className={`px-4 py-2 text-sm font-bold border-b-2 transition-all flex items-center gap-2 ${activeTab === 'floorSpecs' ? 'border-accent text-accent' : 'border-transparent text-muted hover:text-fg'}`}>
                            <Hammer className="w-4 h-4"/> Floor Structural
                          </button>
                        </div>

                        {/* Subheader descriptions based on tab */}
                        <div className="mt-4">
                          {activeTab === 'rooms' ? (
                            <div className="flex justify-between items-center gap-4">
                              <p className="text-xs text-muted">Define finishes and individual openings per room.</p>
                              <button onClick={handleAddRoom} className="px-3 py-1.5 bg-accent text-accent-fg text-white shrink-0 rounded-lg text-xs font-bold hover:bg-accent hover:bg-accent-hover transition-all shadow-lg shadow-violet-500/20 flex items-center gap-1.5">
                                <Plus className="w-3.5 h-3.5"/> Add Room
                              </button>
                            </div>
                          ) : (
                            <div className="flex items-center justify-between">
                              <p className="text-xs text-muted">Define global structural settings and schedules for this floor.</p>
                            </div>
                          )}
                        </div>
                      </div>

                      {/* Tab Content: Floor Structural (Schedules) */}
                      {activeTab === 'floorSpecs' && (
                        <div className="flex flex-col gap-6 animate-in fade-in">
                          <div className="bg-panel border border-border rounded p-8 flex flex-col gap-6 shadow-sm">
                            <h4 className="text-[10px] font-black text-fg uppercase tracking-[0.2em] mb-2">Floor Geometry & Staircase</h4>
                            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-x-8 gap-y-6">
                              {renderInput("Floor Height", activeFloor.floorSpecs.floorHeight, v => updateFloorSpec('floorHeight', v), "e.g. 3.0m")}
                              {renderInput("Staircase Steps", activeFloor.floorSpecs.staircaseStepsCount || '', v => updateFloorSpec('staircaseStepsCount', v), "e.g. 20")}
                              {renderInput("Tread Dimension", activeFloor.floorSpecs.staircaseTreadDim || '', v => updateFloorSpec('staircaseTreadDim', v), "e.g. 300mm")}
                              {renderSelect("Tread Material", activeFloor.floorSpecs.staircaseTreadMaterial || 'Granite', v => updateFloorSpec('staircaseTreadMaterial', v), ['Granite', 'Vitrified', 'Ceramic', 'Marble'])}
                              {renderInput("Riser Dimension", activeFloor.floorSpecs.staircaseRiserDim || '', v => updateFloorSpec('staircaseRiserDim', v), "e.g. 150mm")}
                              {renderSelect("Riser Material", activeFloor.floorSpecs.staircaseRiserMaterial || 'Granite', v => updateFloorSpec('staircaseRiserMaterial', v), ['Granite', 'Vitrified', 'Ceramic', 'Marble'])}
                              {renderInput("Staircase Width", activeFloor.floorSpecs.staircaseWidth || '', v => updateFloorSpec('staircaseWidth', v), "e.g. 1.2m")}
                              {renderInput("Midlanding Dimension", activeFloor.floorSpecs.midlandingDim || '', v => updateFloorSpec('midlandingDim', v), "e.g. 1.2x2.4m")}
                              <div className="col-span-2">
                                {renderSelect("Midlanding Material", activeFloor.floorSpecs.midlandingMaterial || 'Granite', v => updateFloorSpec('midlandingMaterial', v), ['Granite', 'Vitrified', 'Ceramic', 'Marble'])}
                              </div>
                            </div>
                            
                            <h4 className="text-[10px] font-black text-fg uppercase tracking-[0.2em] mt-4 border-t border-border pt-6 mb-2">Railings</h4>
                            <div className="grid grid-cols-2 md:grid-cols-3 gap-x-8 gap-y-6">
                              {renderSelect("Staircase Railing?", activeFloor.floorSpecs.hasStaircaseRailing || 'No', v => updateFloorSpec('hasStaircaseRailing', v), ['No', 'Yes'])}
                              {activeFloor.floorSpecs.hasStaircaseRailing === 'Yes' && (
                                <>
                                  {renderInput("Length (m)", activeFloor.floorSpecs.staircaseRailingDim || '', v => updateFloorSpec('staircaseRailingDim', v))}
                                  {renderSelect("Material", activeFloor.floorSpecs.staircaseRailingMaterial || 'MS (Mild Steel)', v => updateFloorSpec('staircaseRailingMaterial', v), ['MS (Mild Steel)', 'SS (Stainless Steel)', 'Glass', 'Wood'])}
                                </>
                              )}
                            </div>
                          </div>

                        </div>
                      )}

                      {/* Tab Content: Rooms */}
                      {activeTab === 'rooms' && (
                        <div className="flex flex-col gap-4 animate-in fade-in relative">
                          {activeFloor.rooms.length === 0 ? (
                            <div className="bg-panel border border-border border-dashed rounded-xl p-10 text-center flex flex-col items-center justify-center">
                              <LayoutGrid className="w-10 h-10 text-muted mb-3" />
                              <p className="text-sm text-muted font-medium mb-1">No rooms added to this floor</p>
                              <p className="text-xs text-muted">Click "Add Room" to specify details for bedrooms, kitchens, etc.</p>
                            </div>
                          ) : (
                            <div className="flex flex-col gap-3 pb-8">
                              {activeFloor.rooms.map((room: any, rIdx: number) => {
                                const isExpanded = expandedRoomId === room.id;
                                return (
                                  <div 
                                    key={room.id} 
                                    className="bg-panel border border-border rounded-xl overflow-hidden transition-all duration-300 relative"
                                    onMouseEnter={() => setHoveredRoomId(room.id)}
                                    onMouseLeave={() => setHoveredRoomId(null)}
                                  >
                                    <div 
                                      className="px-5 py-4 flex items-center justify-between cursor-pointer hover:bg-white/[0.02]"
                                      onClick={() => setExpandedRoomId(isExpanded ? null : room.id)}
                                    >
                                      <div className="flex items-center gap-4">
                                        <div className={`p-1.5 rounded-md ${isExpanded ? 'bg-accent/10 text-accent' : 'bg-panel text-muted'}`}>
                                          {isExpanded ? <ChevronUp className="w-4 h-4"/> : <ChevronDown className="w-4 h-4"/>}
                                        </div>
                                        <input 
                                          value={room.name} 
                                          onChange={e => updateRoom(rIdx, 'name', e.target.value)} 
                                          onClick={e => e.stopPropagation()}
                                          className="bg-transparent text-sm font-bold text-white outline-none border-b border-transparent focus:border-accent px-1 placeholder-muted"
                                          placeholder="e.g. Master Bedroom"
                                        />
                                      </div>
                                      <button 
                                        onClick={(e) => { e.stopPropagation(); const nf = [...floors]; nf[activeFloorIndex].rooms.splice(rIdx,1); setFloors(nf); }} 
                                        className="text-muted hover:text-red-400 transition-colors p-1"
                                      >
                                        <Trash2 className="w-4 h-4"/>
                                      </button>
                                    </div>

                                    {isExpanded && (
                                      <div className="px-5 pb-6 pt-4 border-t border-border bg-black/20 animate-in slide-in-from-top-2 duration-200">
                                        <div className="grid grid-cols-3 gap-x-6 gap-y-5">
                                          {renderInput("Dimensions", room.dimensions, v => updateRoom(rIdx, 'dimensions', v), "e.g. 10x12 ft")}
                                          {renderSelect("Tiles", room.tiles, v => updateRoom(rIdx, 'tiles', v), ['Vitrified', 'Ceramic', 'Granite', 'Marble', 'Wooden', 'None'])}
                                          {renderSelect("False Ceiling (POP)", room.pop, v => updateRoom(rIdx, 'pop', v), ['Yes', 'No'])}
                                          {renderInput("Skirting Height", room.skirting, v => updateRoom(rIdx, 'skirting', v), "e.g. 4 inch")}
                                          {renderInput("Dado Height", room.dado, v => updateRoom(rIdx, 'dado', v), "e.g. 7 ft")}
                                          
                                          {renderSelect("Balcony Railing?", room.hasBalconyRailing || 'No', v => updateRoom(rIdx, 'hasBalconyRailing', v), ['No', 'Yes'])}
                                          {room.hasBalconyRailing === 'Yes' && (
                                            <>
                                              {renderInput("Balcony Railing Length (m)", room.balconyRailingDim || '', v => updateRoom(rIdx, 'balconyRailingDim', v))}
                                              {renderSelect("Balcony Railing Material", room.balconyRailingMaterial || 'MS (Mild Steel)', v => updateRoom(rIdx, 'balconyRailingMaterial', v), ['MS (Mild Steel)', 'SS (Stainless Steel)', 'Glass', 'Wood'])}
                                            </>
                                          )}

                                          <div className="h-px bg-panel col-span-3"/>
                                          
                                          {/* Action Buttons for Doors & Windows Modals */}
                                          <div className="col-span-3 flex items-center gap-4">
                                            <button 
                                              onClick={() => setDoorModalRoomIdx(rIdx)}
                                              className="flex-1 py-3 px-4 bg-bg hover:bg-[#151515] border border-border rounded-xl flex items-center justify-between group transition-all"
                                            >
                                              <div className="flex items-center gap-3">
                                                <div className="w-8 h-8 rounded-lg bg-pink-500/10 flex items-center justify-center border border-pink-500/20">
                                                  <div className="w-4 h-5 border-2 border-pink-400 rounded-sm relative"><div className="absolute right-1 top-1/2 w-0.5 h-0.5 bg-pink-400 rounded-full"/></div>
                                                </div>
                                                <div className="flex flex-col text-left">
                                                  <span className="text-sm font-bold text-fg">Configure Doors</span>
                                                  <span className="text-[10px] text-muted">{room.doors.length} profiles</span>
                                                </div>
                                              </div>
                                              <ChevronRight className="w-4 h-4 text-muted group-hover:text-fg transition-colors" />
                                            </button>

                                            <button 
                                              onClick={() => setWindowModalRoomIdx(rIdx)}
                                              className="flex-1 py-3 px-4 bg-bg hover:bg-[#151515] border border-border rounded-xl flex items-center justify-between group transition-all"
                                            >
                                              <div className="flex items-center gap-3">
                                                <div className="w-8 h-8 rounded-lg bg-blue-500/10 flex items-center justify-center border border-blue-500/20">
                                                  <div className="w-5 h-5 border-2 border-blue-400 rounded-sm grid grid-cols-2 grid-rows-2 gap-px p-0.5"><div className="bg-blue-400/50"/><div className="bg-blue-400/50"/><div className="bg-blue-400/50"/><div className="bg-blue-400/50"/></div>
                                                </div>
                                                <div className="flex flex-col text-left">
                                                  <span className="text-sm font-bold text-fg">Configure Windows</span>
                                                  <span className="text-[10px] text-muted">{room.windows.length} profiles</span>
                                                </div>
                                              </div>
                                              <ChevronRight className="w-4 h-4 text-muted group-hover:text-fg transition-colors" />
                                            </button>
                                          </div>
                                        </div>
                                      </div>
                                    )}
                                  </div>
                                );
                              })}
                            </div>
                          )}
                          
                          {/* INNER MODALS FOR DOORS/WINDOWS */}
                          {doorModalRoomIdx !== null && (
                            <div className="absolute inset-0 bg-black/60 backdrop-blur-sm z-20 flex items-center justify-center p-4">
                              <div className="bg-panel border border-border rounded-xl shadow-2xl w-full max-w-3xl flex flex-col overflow-hidden animate-in zoom-in-95 duration-200">
                                <div className="p-5 border-b border-border flex items-center justify-between">
                                  <div className="flex flex-col">
                                    <h4 className="font-bold text-fg text-sm flex items-center gap-2">
                                      <div className="w-4 h-5 border-2 border-pink-400 rounded-sm relative"><div className="absolute right-0.5 top-1/2 w-0.5 h-0.5 bg-pink-400 rounded-full"/></div>
                                      Doors <span className="text-muted">—</span> <span className="text-pink-400">{activeFloor.rooms[doorModalRoomIdx].name}</span>
                                    </h4>
                                    <span className="text-[10px] text-muted">{activeFloor.rooms[doorModalRoomIdx].doors.length} door spec(s) configured</span>
                                  </div>
                                  <button onClick={() => setDoorModalRoomIdx(null)} className="p-1.5 text-muted hover:text-fg hover:bg-panel rounded-md"><X className="w-4 h-4"/></button>
                                </div>
                                <div className="p-5 flex-1 overflow-y-auto bg-bg">
                                  <div className="flex items-center justify-between mb-4">
                                    <span className="text-xs font-bold text-fg tracking-wide">Door profiles for this room</span>
                                    <button onClick={() => handleAddDoor(doorModalRoomIdx)} className="bg-accent hover:bg-accent-hover text-accent-fg border border-accent/20 hover:from-pink-400 hover:to-purple-400 text-white text-xs font-bold px-3 py-1.5 rounded-full flex items-center gap-1.5 shadow-[0_0_15px_rgba(236,72,153,0.3)]"><Plus className="w-3.5 h-3.5"/> Add Door</button>
                                  </div>
                                  <div className="space-y-3">
                                    {activeFloor.rooms[doorModalRoomIdx].doors.map((door: any, dIdx: number) => (
                                      <div key={door.id} className="bg-bg border border-border rounded-xl p-4 flex flex-col gap-4 group relative hover:border-pink-500/30 transition-colors">
                                        <div className="flex items-center justify-between">
                                          <div className="w-8 h-8 rounded bg-pink-500/20 text-pink-400 flex items-center justify-center font-black text-xs border border-pink-500/30 shadow-[0_0_10px_rgba(236,72,153,0.1)]">{door.code}</div>
                                          <button onClick={() => removeDoor(doorModalRoomIdx, dIdx)} className="p-1.5 text-red-500/40 hover:text-red-400 hover:bg-red-500/10 rounded-md transition-colors"><Trash2 className="w-4 h-4"/></button>
                                        </div>
                                        <div className="grid grid-cols-12 gap-4">
                                          <div className="col-span-2">{renderInput("Width (m)", door.width, v => updateDoor(doorModalRoomIdx, dIdx, 'width', v))}</div>
                                          <div className="col-span-2">{renderInput("Height (m)", door.height, v => updateDoor(doorModalRoomIdx, dIdx, 'height', v))}</div>
                                          <div className="col-span-2">{renderInput("Count", door.count, v => updateDoor(doorModalRoomIdx, dIdx, 'count', v))}</div>
                                          <div className="col-span-3">{renderSelect("Shutter Material", door.shutterMaterial, v => updateDoor(doorModalRoomIdx, dIdx, 'shutterMaterial', v), ['Flush Door', 'Teak Wood', 'FRP', 'Glass'])}</div>
                                          <div className="col-span-3">{renderSelect("Frame Type", door.frameType, v => updateDoor(doorModalRoomIdx, dIdx, 'frameType', v), ['Teak Wood', 'RCC', 'Metal', 'Other'])}</div>
                                        </div>
                                      </div>
                                    ))}
                                    {activeFloor.rooms[doorModalRoomIdx].doors.length === 0 && (
                                      <div className="text-center py-6 text-muted text-sm italic">No doors added yet.</div>
                                    )}
                                  </div>
                                </div>
                                <div className="p-4 border-t border-border flex justify-end">
                                  <button onClick={() => setDoorModalRoomIdx(null)} className="px-6 py-2 bg-accent hover:bg-accent-hover text-accent-fg border border-accent/20 text-white text-sm font-bold rounded-lg shadow-lg">Done</button>
                                </div>
                              </div>
                            </div>
                          )}

                          {windowModalRoomIdx !== null && (
                            <div className="absolute inset-0 bg-black/60 backdrop-blur-sm z-20 flex items-center justify-center p-4">
                              <div className="bg-panel border border-border rounded-xl shadow-2xl w-full max-w-4xl flex flex-col overflow-hidden animate-in zoom-in-95 duration-200">
                                <div className="p-5 border-b border-border flex items-center justify-between">
                                  <div className="flex flex-col">
                                    <h4 className="font-bold text-fg text-sm flex items-center gap-2">
                                      <div className="w-4 h-4 border-2 border-blue-400 rounded-sm grid grid-cols-2 grid-rows-2 gap-px p-px"><div className="bg-blue-400/50"/><div className="bg-blue-400/50"/><div className="bg-blue-400/50"/><div className="bg-blue-400/50"/></div>
                                      Windows <span className="text-muted">—</span> <span className="text-blue-400">{activeFloor.rooms[windowModalRoomIdx].name}</span>
                                    </h4>
                                    <span className="text-[10px] text-muted">{activeFloor.rooms[windowModalRoomIdx].windows.length} window spec(s) configured</span>
                                  </div>
                                  <button onClick={() => setWindowModalRoomIdx(null)} className="p-1.5 text-muted hover:text-fg hover:bg-panel rounded-md"><X className="w-4 h-4"/></button>
                                </div>
                                <div className="p-5 flex-1 overflow-y-auto bg-bg">
                                  <div className="flex items-center justify-between mb-4">
                                    <span className="text-xs font-bold text-fg tracking-wide">Window & ventilator profiles</span>
                                    <button onClick={() => handleAddWindow(windowModalRoomIdx)} className="bg-accent hover:bg-accent-hover text-accent-fg border border-accent/20 hover:from-pink-400 hover:to-purple-400 text-white text-xs font-bold px-3 py-1.5 rounded-full flex items-center gap-1.5 shadow-[0_0_15px_rgba(236,72,153,0.3)]"><Plus className="w-3.5 h-3.5"/> Add Window</button>
                                  </div>
                                  <div className="space-y-3">
                                    {activeFloor.rooms[windowModalRoomIdx].windows.map((win: any, wIdx: number) => (
                                      <div key={win.id} className="bg-bg border border-border rounded-xl p-4 flex flex-col gap-4 group relative hover:border-blue-500/30 transition-colors">
                                        <div className="flex items-center justify-between">
                                          <div className="w-8 h-8 rounded bg-blue-500/20 text-blue-400 flex items-center justify-center font-black text-xs border border-blue-500/30 shadow-[0_0_10px_rgba(59,130,246,0.1)]">{win.code}</div>
                                          <button onClick={() => removeWindow(windowModalRoomIdx, wIdx)} className="p-1.5 text-red-500/40 hover:text-red-400 hover:bg-red-500/10 rounded-md transition-colors"><Trash2 className="w-4 h-4"/></button>
                                        </div>
                                        
                                        <div className="grid grid-cols-12 gap-4">
                                          <div className="col-span-2">{renderInput("Width (m)", win.width, v => updateWindow(windowModalRoomIdx, wIdx, 'width', v))}</div>
                                          <div className="col-span-2">{renderInput("Height (m)", win.height, v => updateWindow(windowModalRoomIdx, wIdx, 'height', v))}</div>
                                          <div className="col-span-2">{renderInput("Count", win.qty || '1', v => updateWindow(windowModalRoomIdx, wIdx, 'qty', v))}</div>
                                          <div className="col-span-2">{renderSelect("Material", win.material, v => updateWindow(windowModalRoomIdx, wIdx, 'material', v), ['UPVC', 'Aluminum', 'Wood'])}</div>
                                          <div className="col-span-2">{renderSelect("Grills / Gate", win.grills, v => updateWindow(windowModalRoomIdx, wIdx, 'grills', v), ['Grill', 'None'])}</div>
                                          
                                          <div className="col-span-2 flex flex-col items-start justify-end pb-2">
                                            <label className="flex items-center gap-2 cursor-pointer text-xs font-bold text-fg hover:text-fg transition-colors">
                                              <input type="checkbox" checked={win.hasSillJamb} onChange={e => updateWindow(windowModalRoomIdx, wIdx, 'hasSillJamb', e.target.checked)} className="rounded border-border bg-bg text-accent focus:ring-accent w-4 h-4" />
                                              Sill & Jamb
                                            </label>
                                          </div>
                                        </div>
                                        
                                        {win.hasSillJamb && (
                                          <div className="grid grid-cols-2 gap-4 pt-4 border-t border-border animate-in fade-in slide-in-from-top-2">
                                            <div className="col-span-1">{renderInput("Sill Width (m)", win.sillWidth, v => updateWindow(windowModalRoomIdx, wIdx, 'sillWidth', v))}</div>
                                            <div className="col-span-1">{renderInput("Jamb Width (m)", win.jambWidth, v => updateWindow(windowModalRoomIdx, wIdx, 'jambWidth', v))}</div>
                                          </div>
                                        )}
                                      </div>
                                    ))}
                                    {activeFloor.rooms[windowModalRoomIdx].windows.length === 0 && (
                                      <div className="text-center py-6 text-muted text-sm italic">No windows added yet.</div>
                                    )}
                                  </div>
                                </div>
                                <div className="p-4 border-t border-border flex justify-end">
                                  <button onClick={() => setWindowModalRoomIdx(null)} className="px-6 py-2 bg-accent hover:bg-accent-hover text-accent-fg border border-accent/20 text-white text-sm font-bold rounded-lg shadow-lg">Done</button>
                                </div>
                              </div>
                            </div>
                          )}

                        </div>
                      )}

                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

        </div>

        {/* Footer Actions */}
        <div className="px-8 py-5 border-t border-border bg-panel flex justify-between items-center z-10 shrink-0">
          {step === 1 ? <div/> : (
            <button onClick={() => setStep(step-1)} className="px-5 py-2 rounded text-[11px] font-black uppercase tracking-widest text-muted hover:text-fg hover:bg-bg border border-transparent hover:border-border transition-all">
              Back
            </button>
          )}

          {step < 2 ? (
            <button onClick={handleNextStep} disabled={loading} className="px-8 py-2.5 bg-fg text-bg rounded text-[11px] font-black uppercase tracking-[0.1em] shadow hover:bg-accent transition-all flex items-center gap-2">
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <>Next Phase <ChevronRight className="w-4 h-4" /></>}
            </button>
          ) : (
            <button onClick={handleFinish} disabled={loading} className="px-8 py-2.5 bg-accent text-accent-fg text-white rounded text-[11px] font-black uppercase tracking-[0.1em] shadow hover:bg-accent-hover transition-all flex items-center gap-2">
              {loading ? <Loader2 className="w-4 h-4 animate-spin"/> : 'Finalize Config'} <Check className="w-4 h-4"/>
            </button>
          )}
        </div>
      </div>
      </div>

      {/* PDF Interactive Crop Modal */}
      {isCropModalOpen && cropFile && (
        <div className="fixed inset-0 z-50 flex flex-col bg-bg text-fg animate-in fade-in duration-200">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-2 border-b border-border bg-panel shrink-0">
            <div className="flex items-center gap-3">
              <h2 className="text-base font-bold text-fg">Crop Table Selection: {cropFile.name}</h2>
              <span className="px-2.5 py-0.5 text-[10px] rounded bg-accent/10 text-accent border border-accent/30 font-semibold uppercase tracking-wider">
                {cropType} schedule
              </span>
            </div>
            <button 
              onClick={() => {
                setIsCropModalOpen(false);
                setCropFile(null);
                setCropPdf(null);
                setCropStage('crop');
                setExtractedItems([]);
                setHeaderMappings({});
                setScaleInitialized(false);
              }}
              className="p-1.5 rounded-lg hover:bg-panel text-muted hover:text-fg transition-colors cursor-pointer"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Top Toolbar */}
          <div className="flex items-center justify-between px-3 py-1 bg-panel border-b border-border shrink-0 gap-4">
            {cropStage === 'crop' ? (
              <>
                {/* Page Controls */}
                <div className="flex items-center gap-1.5">
                  <span className="text-[10px] font-bold text-muted uppercase tracking-wider mr-1">Page:</span>
                  <button
                    type="button"
                    disabled={cropPageNum <= 1 || pdfLoading}
                    onClick={() => setCropPageNum(prev => Math.max(1, prev - 1))}
                    className="px-2 py-1 rounded-md bg-panel hover:bg-panel border border-border text-[10px] font-semibold transition-colors disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer"
                  >
                    Previous
                  </button>
                  <span className="text-[10px] font-bold bg-panel border border-border px-2 py-1 rounded-md text-fg min-w-[70px] text-center">
                    {cropPageNum} / {cropTotalPages || '?'}
                  </span>
                  <button
                    type="button"
                    disabled={cropPageNum >= (cropTotalPages || 1) || pdfLoading}
                    onClick={() => setCropPageNum(prev => Math.min(cropTotalPages || 1, prev + 1))}
                    className="px-2 py-1 rounded-md bg-panel hover:bg-panel border border-border text-[10px] font-semibold transition-colors disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer"
                  >
                    Next
                  </button>
                </div>

                {/* Zoom Controls */}
                <div className="flex items-center gap-1.5">
                  <span className="text-[10px] font-bold text-muted uppercase tracking-wider mr-1">Zoom:</span>
                  <button
                    type="button"
                    disabled={pdfScale <= 0.25 || pdfLoading}
                    onClick={() => setPdfScale(prev => Math.max(0.25, prev - 0.25))}
                    className="px-2 py-1 rounded-md bg-panel hover:bg-panel border border-border text-[10px] font-semibold transition-colors disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer"
                  >
                    Zoom Out
                  </button>
                  <div className="flex items-center gap-0.5 bg-panel border border-border rounded-md px-1.5 py-1 w-14 shrink-0 justify-center">
                    <input 
                      type="text"
                      value={zoomText}
                      onChange={(e) => {
                        const valStr = e.target.value;
                        if (valStr === "" || /^\d+$/.test(valStr)) {
                          setZoomText(valStr);
                          const val = parseInt(valStr);
                          if (!isNaN(val) && val >= 25 && val <= 500) {
                            setPdfScale(val / 100);
                          }
                        }
                      }}
                      onBlur={() => {
                        let val = parseInt(zoomText);
                        if (isNaN(val) || val < 25) val = 25;
                        if (val > 500) val = 500;
                        setPdfScale(val / 100);
                        setZoomText(val.toString());
                      }}
                      className="w-full bg-transparent text-[10px] font-bold text-center focus:outline-none text-fg font-mono"
                    />
                    <span className="text-[10px] text-muted font-bold">%</span>
                  </div>
                  <button
                    type="button"
                    disabled={pdfScale >= 5.0 || pdfLoading}
                    onClick={() => setPdfScale(prev => Math.min(5.0, prev + 0.25))}
                    className="px-2 py-1 rounded-md bg-panel hover:bg-panel border border-border text-[10px] font-semibold transition-colors disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer"
                  >
                    Zoom In
                  </button>
                </div>

                {/* Status and Action */}
                <div className="flex items-center gap-4">
                  {pdfLoading && (
                    <div className="flex items-center gap-2 text-accent text-xs font-medium animate-pulse">
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      <span>Loading Page...</span>
                    </div>
                  )}
                  {extracting && (
                    <div className="flex items-center gap-2 text-amber-400 text-xs font-medium animate-pulse">
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      <span>Extracting...</span>
                    </div>
                  )}
                  <button
                    type="button"
                    disabled={!cropRect || extracting || pdfLoading}
                    onClick={handleExtractCrop}
                    className="px-3.5 py-1.5 rounded-md bg-accent hover:bg-accent-hover text-accent-fg hover:bg-accent text-accent-fg disabled:bg-panel disabled:text-muted text-[10px] font-bold transition-all shadow-md flex items-center gap-1.5 disabled:cursor-not-allowed cursor-pointer"
                  >
                    {extracting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
                    Extract Schedule
                  </button>
                </div>
              </>
            ) : (
              <>
                {/* Left side info */}
                <div className="flex items-center gap-3">
                  <span className="text-xs text-muted font-medium">
                    Successfully extracted <strong className="text-white">{extractedItems.length}</strong> rows across <strong className="text-white">{Object.keys(headerMappings).length}</strong> columns.
                  </span>
                </div>

                {/* Right side actions */}
                <div className="flex items-center gap-3">
                  <button
                    type="button"
                    onClick={() => {
                      setCropStage('crop');
                      setExtractedItems([]);
                      setHeaderMappings({});
                    }}
                    className="px-4 py-2 rounded-lg bg-panel hover:bg-panel border border-border text-xs font-bold transition-colors cursor-pointer"
                  >
                    Back to Crop
                  </button>
                  <button
                    type="button"
                    onClick={handleConfirmSchema}
                    className="px-5 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold transition-all shadow-md flex items-center gap-1.5 cursor-pointer animate-pulse"
                  >
                    <Check className="w-3.5 h-3.5" />
                    Confirm & Save Schema
                  </button>
                </div>
              </>
            )}
          </div>

          {/* Main Body */}
          <div className="flex-1 flex overflow-hidden">
            {cropStage === 'crop' ? (
              /* Right PDF Canvas Workspace */
              <div className="flex-1 overflow-auto bg-bg p-8 flex items-start justify-start relative">
                <div 
                  className="relative select-none border border-border shadow-2xl bg-white shrink-0"
                  style={{ 
                    cursor: 'crosshair',
                    width: pageWidth ? pageWidth * pdfScale : 'auto',
                    height: pageHeight ? pageHeight * pdfScale : 'auto'
                  }}
                  onMouseDown={handleCanvasMouseDown}
                  onMouseMove={handleCanvasMouseMove}
                  onMouseUp={handleCanvasMouseUp}
                >
                  <canvas 
                    ref={canvasRef} 
                    style={{
                      width: '100%',
                      height: '100%',
                      display: 'block'
                    }}
                  />
                  {/* Crop Overlay Selection Box */}
                  {cropRect && (
                    <div 
                      className="absolute border-2 border-accent bg-accent/10"
                      style={{
                        left: Math.min(cropRect.startX, cropRect.currentX),
                        top: Math.min(cropRect.startY, cropRect.currentY),
                        width: Math.abs(cropRect.startX - cropRect.currentX),
                        height: Math.abs(cropRect.startY - cropRect.currentY),
                        pointerEvents: 'none'
                      }}
                    />
                  )}
                </div>
              </div>
            ) : (
              /* Header Mapping Dashboard */
              <div className="flex-1 flex overflow-hidden animate-in fade-in zoom-in-95 duration-200">
                {/* Left Form: Mappings Editor */}
                <div className="w-[380px] shrink-0 border-r border-border bg-panel flex flex-col overflow-hidden">
                  <div className="p-5 border-b border-border shrink-0">
                    <h3 className="text-sm font-bold text-fg mb-1">Column Schema Editor</h3>
                    <p className="text-xs text-muted">Provide clean, descriptive names for the detected columns.</p>
                  </div>
                  <div className="flex-1 overflow-y-auto p-5 space-y-4 custom-scrollbar">
                    {Object.keys(headerMappings).map((oldKey, idx) => {
                      const sampleVal = extractedItems.find(item => item[oldKey])?.[oldKey] || '';
                      const colors = [
                        'bg-white border-emerald-100 dark:bg-panel dark:border-emerald-900/40 text-emerald-800 dark:text-emerald-300',
                        'bg-emerald-50 border-emerald-200 dark:bg-emerald-950/40 dark:border-emerald-800 text-emerald-900 dark:text-emerald-200'
                      ];
                      const cClass = colors[idx % colors.length];
                      return (
                        <div key={oldKey} className={`flex flex-col gap-1.5 p-3 rounded-xl border transition-all shadow-sm hover:border-emerald-500/50 ${cClass}`}>
                          <div className="flex justify-between items-center text-[9px] font-black uppercase tracking-widest opacity-90">
                            <span>Detected Label</span>
                            <span className="text-muted max-w-[150px] truncate bg-bg px-1.5 py-0.5 rounded font-medium shadow-sm">Sample: "{sampleVal}"</span>
                          </div>
                          <div className="text-xs text-fg font-bold truncate bg-panel px-2.5 py-1.5 rounded border border-border select-all font-mono shadow-inner">
                            {oldKey}
                          </div>
                            <input
                              type="text"
                              value={headerMappings[oldKey]}
                              onChange={(e) => setHeaderMappings(prev => ({ ...prev, [oldKey]: e.target.value }))}
                              className="w-full bg-bg border border-border rounded-lg px-3 py-2 text-xs text-fg focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent/50 transition-all font-semibold shadow-sm"
                              placeholder="Clean name (e.g. Width 1)"
                            />
                          </div>
                      );
                    })}
                  </div>
                </div>

                {/* Right Interactive Table Preview */}
                <div className="flex-1 flex flex-col bg-bg overflow-hidden">
                  <div className="p-5 border-b border-border shrink-0 flex items-center justify-between">
                    <div>
                      <h3 className="text-sm font-bold text-fg mb-1">Data Schema Live Preview</h3>
                      <p className="text-xs text-muted">Table rows updated instantly with your renamed column keys.</p>
                    </div>
                  </div>
                  <div className="flex-1 overflow-auto p-6 custom-scrollbar">
                    <div className="min-w-full inline-block align-middle">
                      <div className="overflow-hidden border border-border rounded-xl bg-panel shadow-sm">
                        <table className="min-w-full divide-y divide-border">
                          <thead className="bg-muted/10 border-b border-border">
                            <tr>
                              {Object.keys(headerMappings).map((oldKey, idx) => {
                                const newKey = headerMappings[oldKey] || oldKey;
                                const colors = [
                                  'bg-white text-emerald-900 dark:bg-panel dark:text-emerald-200',
                                  'bg-emerald-50 text-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-200'
                                ];
                                const cClass = colors[idx % colors.length];
                                return (
                                  <th key={oldKey} className={`px-4 py-3.5 text-left text-xs font-bold uppercase tracking-wider whitespace-nowrap border-r border-border last:border-r-0 ${cClass}`}>
                                    {newKey}
                                  </th>
                                );
                              })}
                              <th className="px-4 py-3.5 text-left text-xs font-bold text-fg uppercase tracking-wider whitespace-nowrap">
                                Actions
                              </th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-border bg-transparent">
                            {extractedItems.slice(0, 10).map((item, idx) => {
                              const isEditing = editingRowIndex === idx;
                              return (
                                <tr 
                                  key={idx} 
                                  className="hover:bg-muted/10 even:bg-muted/5 transition-colors cursor-pointer group"
                                  onDoubleClick={() => {
                                    setEditingRowIndex(idx);
                                    setEditRowData({ ...item });
                                  }}
                                  title="Double-click to edit row"
                                >
                                  {isEditing ? (
                                    <>
                                      {Object.keys(headerMappings).map((oldKey) => (
                                        <td key={oldKey} className="px-2 py-2 text-xs text-muted border-r border-border last:border-r-0 max-w-[200px]">
                                          <input
                                            type="text"
                                            value={editRowData?.[oldKey] || ''}
                                            onChange={(e) => setEditRowData((prev: any) => ({ ...prev, [oldKey]: e.target.value }))}
                                            className="w-full bg-bg border border-accent/50 rounded px-2 py-1 text-xs text-fg focus:outline-none focus:ring-1 focus:ring-accent/30 font-semibold shadow-inner"
                                            autoFocus={Object.keys(headerMappings)[0] === oldKey}
                                            onKeyDown={(e) => {
                                              if (e.key === 'Enter') {
                                                const updated = [...extractedItems];
                                                updated[idx] = editRowData;
                                                setExtractedItems(updated);
                                                setEditingRowIndex(null);
                                                setEditRowData(null);
                                              } else if (e.key === 'Escape') {
                                                setEditingRowIndex(null);
                                                setEditRowData(null);
                                              }
                                            }}
                                          />
                                        </td>
                                      ))}
                                      <td className="px-4 py-2 text-xs text-muted whitespace-nowrap flex items-center gap-1.5 h-full">
                                        <button
                                          type="button"
                                          onClick={() => {
                                            const updated = [...extractedItems];
                                            updated[idx] = editRowData;
                                            setExtractedItems(updated);
                                            setEditingRowIndex(null);
                                            setEditRowData(null);
                                          }}
                                          className="p-1 rounded bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 transition-colors"
                                          title="Save Row"
                                        >
                                          <Check className="w-3.5 h-3.5" />
                                        </button>
                                        <button
                                          type="button"
                                          onClick={() => {
                                            const updated = extractedItems.filter((_, i) => i !== idx);
                                            setExtractedItems(updated);
                                            setEditingRowIndex(null);
                                            setEditRowData(null);
                                          }}
                                          className="p-1 rounded bg-red-500/10 hover:bg-red-500/20 text-red-400 transition-colors"
                                          title="Delete Row"
                                        >
                                          <Trash2 className="w-3.5 h-3.5" />
                                        </button>
                                        <button
                                          type="button"
                                          onClick={() => {
                                            setEditingRowIndex(null);
                                            setEditRowData(null);
                                          }}
                                          className="p-1 rounded bg-panel hover:bg-panel text-muted transition-colors"
                                          title="Cancel"
                                        >
                                          <X className="w-3.5 h-3.5" />
                                        </button>
                                      </td>
                                    </>
                                  ) : (
                                    <>
                                      {Object.keys(headerMappings).map((oldKey) => (
                                        <td key={oldKey} className="px-4 py-3 text-xs text-muted whitespace-nowrap border-r border-border last:border-r-0 max-w-[200px] truncate">
                                          {item[oldKey]}
                                        </td>
                                      ))}
                                      <td className="px-4 py-3 text-xs text-muted whitespace-nowrap">
                                        <button
                                          type="button"
                                          onClick={() => {
                                            const updated = extractedItems.filter((_, i) => i !== idx);
                                            setExtractedItems(updated);
                                          }}
                                          className="p-1 rounded hover:bg-red-500/10 text-muted hover:text-red-400 opacity-0 group-hover:opacity-100 transition-all duration-150"
                                          title="Delete Row"
                                        >
                                          <Trash2 className="w-3.5 h-3.5" />
                                        </button>
                                      </td>
                                    </>
                                  )}
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                      {extractedItems.length > 10 && (
                        <div className="text-center text-muted text-[10px] font-semibold mt-3 uppercase tracking-wider">
                          Showing first 10 of {extractedItems.length} rows
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
