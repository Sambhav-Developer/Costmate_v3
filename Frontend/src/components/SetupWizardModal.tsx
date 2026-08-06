'use client';

import React, { useState, useRef } from 'react';
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
  const [uploadingFloorId, setUploadingFloorId] = useState<number | null>(null);
  const [draftSessionId, setDraftSessionId] = useState<string | null>(null);

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
  const activeFloorIndex = floors.findIndex(f => f.id === activeFloorId);
  const activeFloor = floors[activeFloorIndex];

  const [activeTab, setActiveTab] = useState<'rooms' | 'floorSpecs'>('rooms');
  const [expandedRoomId, setExpandedRoomId] = useState<number | null>(null);
  const [hoveredRoomId, setHoveredRoomId] = useState<number | null>(null);
  const [draggedFloorIdx, setDraggedFloorIdx] = useState<number | null>(null);

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
        
        try {
          setIsScanning(true);
          const scanRes = await api.quickScanDraft(currentSid);
          if (scanRes.data && scanRes.data.rooms) {
            scannedRooms = scanRes.data.rooms.map((r: any, idx: number) => ({
              id: Date.now() + idx,
              name: r.name || 'Room',
              dimensions: r.dimensions || '',
              boundingBox: r.bounding_box || null,
              tiles: 'Vitrified',
              pop: 'No',
              skirting: '4 inch',
              dado: 'None',
              hasBalconyRailing: 'No',
              balconyRailingDim: '',
              balconyRailingMaterial: 'MS (Mild Steel)',
              doors: [],
              windows: []
            }));
          }
        } catch (scanErr) {
          console.warn('Quick scan failed:', scanErr);
        } finally {
          setIsScanning(false);
        }
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
           const res = await api.uploadDraftFile(sid, f.file);
           newFloors[i].fileName = res.filename;
           if (res.page_paths && res.page_paths.length > 0) {
             newFloors[i].pageUrls = res.page_paths;
           }
           newFloors[i].rawUrl = res.raw_url;
        }
      }
      setFloors(newFloors);

      const intakeData = { globalSettings, floors: newFloors };
      const resData = await api.startDraftTakeoff(sid, intakeData);
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
      <label className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider">{label}</label>
      <input 
        value={value} 
        onChange={(e) => onChange(e.target.value)} 
        placeholder={placeholder}
        className="w-full bg-[#18181b] border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder-zinc-600 focus:outline-none focus:border-violet-500 focus:ring-1 focus:ring-violet-500/50 transition-all"
      />
    </div>
  );

  const renderSelect = (label: string, value: string, onChange: (v: string) => void, options: string[]) => (
    <div className="flex flex-col gap-1.5 w-full">
      <label className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider">{label}</label>
      <select 
        value={value} 
        onChange={(e) => onChange(e.target.value)} 
        className="w-full bg-[#18181b] border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-violet-500 transition-all cursor-pointer"
      >
        {options.map(opt => <option key={opt} value={opt}>{opt}</option>)}
      </select>
    </div>
  );

  const renderGridInput = (value: string, onChange: (v: string) => void, placeholder: string = "") => (
    <input 
      value={value} 
      onChange={(e) => onChange(e.target.value)} 
      placeholder={placeholder}
      className="w-full bg-[#111111] border border-white/5 rounded-md px-3 py-2 text-sm text-white placeholder-zinc-600 focus:outline-none focus:border-violet-500 focus:ring-1 focus:ring-violet-500/50 transition-all"
    />
  );

  const renderGridSelect = (value: string, onChange: (v: string) => void, options: string[]) => (
    <select 
      value={value} 
      onChange={(e) => onChange(e.target.value)} 
      className="w-full bg-[#111111] border border-white/5 rounded-md px-3 py-2 text-sm text-white focus:outline-none focus:border-violet-500 transition-all cursor-pointer"
    >
      {options.map(opt => <option key={opt} value={opt}>{opt}</option>)}
    </select>
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/90 backdrop-blur-sm p-6 animate-in fade-in duration-300 font-sans">
      <div className="w-full h-full bg-[#09090b] border border-white/10 rounded-2xl shadow-2xl flex flex-col overflow-hidden ring-1 ring-white/5 relative">
        
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/10 bg-[#09090b] shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-violet-500/20 flex items-center justify-center border border-violet-500/30">
              <Building2 className="w-4 h-4 text-violet-400" />
            </div>
            <h2 className="text-lg font-bold text-white tracking-tight">Project Initialization Wizard</h2>
          </div>
          <button onClick={onClose} className="p-2 bg-white/5 hover:bg-white/10 rounded-lg text-zinc-400 hover:text-white transition-all">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Stepper */}
        <div className="px-8 py-4 border-b border-white/5 flex items-center justify-center gap-16 bg-[#09090b] shrink-0">
          {[
            { num: 1, label: 'Global Setup' },
            { num: 2, label: 'Floor Layouts & Details' }
          ].map((s, i) => (
            <React.Fragment key={s.num}>
              <div className="flex items-center gap-3 cursor-pointer group" onClick={() => setStep(s.num)}>
                <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold transition-all ${step === s.num ? 'bg-violet-500 text-white shadow-[0_0_15px_rgba(139,92,246,0.4)]' : step > s.num ? 'bg-violet-500/20 text-violet-400 border border-violet-500/50' : 'bg-white/5 text-zinc-500 group-hover:bg-white/10'}`}>
                  {step > s.num ? <Check className="w-3.5 h-3.5" /> : s.num}
                </div>
                <span className={`text-sm font-semibold transition-colors ${step === s.num ? 'text-white' : step > s.num ? 'text-zinc-300' : 'text-zinc-600 group-hover:text-zinc-400'}`}>{s.label}</span>
              </div>
              {i < 1 && <div className={`w-16 h-px ${step > s.num ? 'bg-violet-500/50' : 'bg-white/10'}`} />}
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
        <div className="flex-1 flex overflow-hidden bg-[#09090b] relative">
          
          {/* STEP 1: Global Settings */}
          {step === 1 && (
            <div className="flex-1 flex flex-col items-center p-10 overflow-y-auto custom-scrollbar animate-in fade-in slide-in-from-bottom-4">
              <div className="w-full max-w-2xl space-y-6">
                <div className="bg-[#18181b] border border-white/5 rounded-xl p-6">
                  <h3 className="text-sm font-bold text-white mb-5 uppercase tracking-widest text-zinc-400 flex items-center gap-2">
                    <Settings2 className="w-4 h-4 text-violet-400"/> General Information
                  </h3>
                  <div className="space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                      {renderInput("Project Name", globalSettings.projectName, v => setGlobalSettings({...globalSettings, projectName: v}), "e.g. Skyline Towers")}
                    </div>
                    <div className={`grid grid-cols-3 gap-4`}>
                      {renderSelect("Building Type", globalSettings.buildingType, v => setGlobalSettings({...globalSettings, buildingType: v}), ['Residential', 'Commercial', 'Apartment', 'Industrial', 'Other'])}
                      {renderSelect("Basement Present", globalSettings.basementPresent, v => setGlobalSettings({...globalSettings, basementPresent: v}), ['No', 'Yes'])}
                      {globalSettings.basementPresent === 'Yes' && (
                        renderInput("Number of Basements", globalSettings.numBasements.toString(), v => setGlobalSettings({...globalSettings, numBasements: parseInt(v) || 0}), "e.g. 2")
                      )}
                      {renderInput("Number of Floors", globalSettings.numFloors.toString(), v => setGlobalSettings({...globalSettings, numFloors: parseInt(v) || 0}), "e.g. 4")}
                    </div>
                  </div>
                </div>

                {/* GLOBAL SCHEDULES */}
                <div className="bg-[#18181b] border border-white/5 rounded-xl p-6">
                  <h3 className="text-sm font-bold text-white mb-5 uppercase tracking-widest text-zinc-400 flex items-center gap-2">
                    <FileText className="w-4 h-4 text-violet-400"/> Door & Window Schedules (Optional)
                  </h3>
                  
                  <div className="flex flex-col gap-4">
                    {/* Door Schedule */}
                    <div className="flex items-center gap-4">
                      <button 
                        onClick={() => document.getElementById('door-schedule-upload')?.click()}
                        disabled={isUploadingDoor || loading}
                        className="px-4 py-2 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 flex items-center gap-2 text-sm font-medium transition-colors w-52 disabled:opacity-50 disabled:cursor-not-allowed"
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
                          const files = e.target.files;
                          if (!files || files.length === 0) return;
                          setLoading(true);
                          setIsUploadingDoor(true);
                          try {
                            let sid = draftSessionId;
                            if (!sid) {
                              const data = await api.createDraftSession(globalSettings.projectName);
                              sid = data.session_id;
                              setDraftSessionId(sid);
                            }
                            
                            let uploadedNames: string[] = [];
                            if (globalSettings.doorScheduleFileName) {
                               uploadedNames = globalSettings.doorScheduleFileName.split(", ");
                            }
                            
                            for (let i = 0; i < files.length; i++) {
                              const file = files[i];
                              uploadedNames.push(file.name);
                              // 3-minute client timeout — shows error if OpenRouter hangs
                              const timeoutPromise = new Promise<never>((_, reject) =>
                                setTimeout(() => reject(new Error('Schedule parsing timed out. The AI service is busy — please try again in a moment.')), 180_000)
                              );
                              const res = await Promise.race([api.uploadDraftSchedule(sid, file), timeoutPromise]);
                              
                                setGlobalSettings(prev => {
                                  const oldReg = prev.scheduleRegistry || { type_registry: { doors: [], windows: [] }, instance_schedule: [] };
                                  const rawReg = res.schedule_registry;
                                  let newReg: any = { type_registry: { doors: [], windows: [] }, instance_schedule: [] };
                                  if (Array.isArray(rawReg)) {
                                      newReg.instance_schedule = rawReg.map((item: any) => ({ ...item, _schedule_type: 'door' }));
                                  } else if (rawReg && Array.isArray(rawReg.instance_schedule)) {
                                      newReg = rawReg;
                                      newReg.instance_schedule = newReg.instance_schedule.map((item: any) => ({ ...item, _schedule_type: 'door' }));
                                  }
                                  
                                  return {
                                    ...prev, 
                                    doorScheduleFileName: uploadedNames.join(", "),
                                    scheduleRegistry: {
                                      ...oldReg,
                                      ...newReg,
                                      type_registry: {
                                        doors: [...(oldReg.type_registry?.doors || []), ...(newReg.type_registry?.doors || [])],
                                        windows: [...(oldReg.type_registry?.windows || []), ...(newReg.type_registry?.windows || [])]
                                      },
                                      instance_schedule: [...(oldReg.instance_schedule || []), ...(newReg.instance_schedule || [])]
                                    }
                                  };
                                });
                            }
                          } catch (err: any) {
                            setError('⚠️ ' + (err.message || 'Failed to upload door schedule. Please try again.'));
                          } finally {
                            setLoading(false);
                            setIsUploadingDoor(false);
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
                        onClick={() => document.getElementById('window-schedule-upload')?.click()}
                        disabled={isUploadingWindow || loading}
                        className="px-4 py-2 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 flex items-center gap-2 text-sm font-medium transition-colors w-52 disabled:opacity-50 disabled:cursor-not-allowed"
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
                          const files = e.target.files;
                          if (!files || files.length === 0) return;
                          setLoading(true);
                          setIsUploadingWindow(true);
                          try {
                            let sid = draftSessionId;
                            if (!sid) {
                              const data = await api.createDraftSession(globalSettings.projectName);
                              sid = data.session_id;
                              setDraftSessionId(sid);
                            }
                            
                            let uploadedNames: string[] = [];
                            if (globalSettings.windowScheduleFileName) {
                               uploadedNames = globalSettings.windowScheduleFileName.split(", ");
                            }
                            
                            for (let i = 0; i < files.length; i++) {
                              const file = files[i];
                              uploadedNames.push(file.name);
                              // 3-minute client timeout — shows error if OpenRouter hangs
                              const timeoutPromise = new Promise<never>((_, reject) =>
                                setTimeout(() => reject(new Error('Schedule parsing timed out. The AI service is busy — please try again in a moment.')), 180_000)
                              );
                              const res = await Promise.race([api.uploadDraftSchedule(sid, file), timeoutPromise]);
                              
                              setGlobalSettings(prev => {
                                const oldReg = prev.scheduleRegistry || { type_registry: { doors: [], windows: [] }, instance_schedule: [] };
                                const rawReg = res.schedule_registry;
                                let newReg: any = { type_registry: { doors: [], windows: [] }, instance_schedule: [] };
                                if (Array.isArray(rawReg)) {
                                    newReg.instance_schedule = rawReg.map((item: any) => ({ ...item, _schedule_type: 'window' }));
                                } else if (rawReg && Array.isArray(rawReg.instance_schedule)) {
                                    newReg = rawReg;
                                    newReg.instance_schedule = newReg.instance_schedule.map((item: any) => ({ ...item, _schedule_type: 'window' }));
                                }
                                return {
                                  ...prev, 
                                  windowScheduleFileName: uploadedNames.join(", "),
                                  scheduleRegistry: {
                                    ...oldReg,
                                    ...newReg,
                                    type_registry: {
                                      doors: [...(oldReg.type_registry?.doors || []), ...(newReg.type_registry?.doors || [])],
                                      windows: [...(oldReg.type_registry?.windows || []), ...(newReg.type_registry?.windows || [])]
                                    },
                                    instance_schedule: [...(oldReg.instance_schedule || []), ...(newReg.instance_schedule || [])]
                                  }
                                };
                              });
                            }
                          } catch (err: any) {
                            setError('⚠️ ' + (err.message || 'Failed to upload window schedule. Please try again.'));
                          } finally {
                            setLoading(false);
                            setIsUploadingWindow(false);
                          }
                        }} 
                      />
                      {globalSettings.windowScheduleFileName && !isUploadingWindow && (
                        <div className="text-sm text-emerald-400 flex items-center gap-2 bg-emerald-500/10 px-3 py-1.5 rounded-lg border border-emerald-500/20 truncate max-w-xs">
                          <CheckCircle2 className="w-4 h-4 shrink-0" /> <span className="truncate">{globalSettings.windowScheduleFileName}</span>
                        </div>
                      )}
                    </div>
                  </div>
                  <p className="text-xs text-zinc-500 mt-4">
                    Upload your schedules here. We will extract the door/window types and use them when scanning your floor plans.
                  </p>
                  
                  {/* Schedule Preview */}
                  {globalSettings.scheduleRegistry && (
                    <div className="mt-4 p-4 border border-white/10 rounded-lg bg-black overflow-auto max-h-64 custom-scrollbar">
                      <h4 className="text-sm font-bold text-white mb-2 flex items-center gap-2">
                        <CheckCircle2 className="w-4 h-4 text-emerald-400" /> Parsed Schedule Data (Preview)
                      </h4>
                      <pre className="text-xs text-zinc-400 whitespace-pre-wrap select-text" draggable="false" style={{ userSelect: 'text', WebkitUserDrag: 'none' }}>
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
              <div className="w-[260px] border-r border-white/5 bg-[#09090b] flex flex-col shrink-0">
                <div className="p-4 flex justify-between items-center border-b border-white/5">
                  <span className="text-xs font-bold text-zinc-400 uppercase tracking-widest">Levels</span>
                  <button onClick={handleAddFloor} className="p-1.5 rounded-md bg-white/5 border border-white/10 hover:bg-violet-500/20 hover:text-violet-400 transition-all text-zinc-400">
                    <Plus className="w-4 h-4"/>
                  </button>
                </div>
                <div className="flex-1 overflow-y-auto p-3 space-y-2 custom-scrollbar">
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
                      className={`p-3 rounded-lg border cursor-pointer transition-all flex items-center gap-3 group ${activeFloorId === floor.id ? 'bg-[#18181b] border-violet-500/50 shadow-[0_4px_20px_-4px_rgba(139,92,246,0.1)] text-white' : 'bg-transparent border-transparent text-zinc-400 hover:bg-white/5 hover:text-zinc-200'} ${draggedFloorIdx === index ? 'opacity-50 border-dashed border-zinc-600 bg-white/5' : ''}`}
                    >
                      <Layers className={`w-4 h-4 shrink-0 ${activeFloorId === floor.id ? 'text-violet-400' : ''}`} />
                      <div className="flex flex-col overflow-hidden flex-1">
                        <span className="text-sm font-semibold truncate">{floor.name}</span>
                        {floor.fileName && <span className="text-[10px] text-zinc-500 truncate">{floor.fileName}</span>}
                      </div>
                      <button 
                        onClick={(e) => handleDeleteFloor(e, floor.id)} 
                        className={`p-1.5 rounded-md transition-colors ${activeFloorId === floor.id ? 'text-violet-300 hover:text-red-400 hover:bg-red-500/10' : 'text-zinc-500 hover:text-red-400 hover:bg-red-500/10 opacity-0 group-hover:opacity-100'}`}
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ))}
                </div>
              </div>

              {/* Main Floor Editor */}
              <div className="flex-1 flex flex-col bg-[#09090b] h-full overflow-hidden relative">
                {/* Floor Header */}
                <div className="px-8 py-5 border-b border-white/5 flex items-center justify-between bg-[#09090b] shrink-0">
                  <input 
                    value={activeFloor.name} 
                    onChange={e => { const nf = [...floors]; nf[activeFloorIndex].name = e.target.value; setFloors(nf); }} 
                    className="bg-transparent text-2xl font-bold text-white outline-none border-b border-transparent focus:border-violet-500 px-1 w-64 transition-all"
                    placeholder="Floor Name"
                  />
                  <div className="flex items-center gap-3 bg-[#18181b] border border-white/10 rounded-lg p-1.5 px-3">
                    <span className="text-xs text-zinc-500 font-semibold">Copy Specs From:</span>
                    <select 
                      onChange={(e) => handleCopySpecs(e.target.value)}
                      className="bg-transparent text-xs text-white outline-none font-medium cursor-pointer"
                    >
                      <option value="None">None</option>
                      {floors.filter(f => f.id !== activeFloor.id).map(f => <option key={f.id} value={f.id}>{f.name}</option>)}
                    </select>
                  </div>
                </div>

                <div className="flex-1 overflow-y-auto px-8 pb-8 custom-scrollbar relative">
                  <div className="w-full mx-auto flex flex-col xl:flex-row gap-8 pt-8">
                    
                    {/* Left Col: Upload */}
                    <div className="w-full xl:w-[300px] shrink-0 flex flex-col gap-4 xl:sticky xl:top-0 h-fit z-10">
                      <div className="flex items-center justify-between">
                        <h3 className="text-sm font-bold text-zinc-400 uppercase tracking-widest">Floor Plan</h3>
                        {activeFloor.file && activeFloor.fileName && !loading && (
                          <div className="flex items-center gap-4">
                            <button onClick={() => window.open(URL.createObjectURL(activeFloor.file), '_blank')} className="text-xs font-bold text-sky-400 hover:text-sky-300 flex items-center gap-1.5 transition-colors">
                              <Maximize2 className="w-3.5 h-3.5"/> View Full
                            </button>
                            <button onClick={() => fileInputRef.current?.click()} className="text-xs font-bold text-violet-400 hover:text-violet-300 flex items-center gap-1.5 transition-colors">
                              <Upload className="w-3.5 h-3.5"/> Replace
                            </button>
                          </div>
                        )}
                      </div>
                      <div className="h-[280px] bg-[#18181b] border-2 border-dashed border-white/10 rounded-2xl flex flex-col items-center justify-center p-6 text-center relative overflow-hidden">
                        <input type="file" ref={fileInputRef} onChange={handleFileUpload} accept=".pdf,.png,.jpg" className="hidden" />
                        {uploadingFloorId === activeFloor.id ? (
                          <div className="flex flex-col items-center">
                            <Loader2 className="w-8 h-8 animate-spin text-violet-500 mb-3" />
                            <span className="text-sm font-bold text-violet-400">
                              {isScanning ? '✨ AI is detecting rooms...' : 'Uploading...'}
                            </span>
                          </div>
                        ) : activeFloor.file && activeFloor.fileName ? (
                          <div className="absolute inset-0 w-full h-full p-2 flex items-center justify-center group overflow-hidden">
                             <div className="relative max-w-full max-h-full flex items-center justify-center">
                               {activeFloor.pageUrls && activeFloor.pageUrls.length > 0 ? (
                                  <img src={activeFloor.pageUrls[0]} alt="Preview" className="max-w-full max-h-full object-contain rounded-xl relative z-0" style={{ maxHeight: '250px' }} />
                               ) : activeFloor.fileName.toLowerCase().endsWith('.pdf') ? (
                                  <iframe 
                                    src={`${URL.createObjectURL(activeFloor.file)}#toolbar=0&navpanes=0&scrollbar=0`} 
                                    className="w-full h-[250px] rounded-xl bg-white/5 relative z-0" 
                                  />
                               ) : (
                                  <img src={URL.createObjectURL(activeFloor.file)} alt="Preview" className="max-w-full max-h-full object-contain rounded-xl relative z-0" style={{ maxHeight: '250px' }} />
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
                                       className={`absolute border-2 transition-all duration-300 ${isHovered ? 'border-violet-500 bg-violet-500/30 shadow-[0_0_15px_rgba(139,92,246,0.6)] z-20' : 'border-emerald-500/40 bg-emerald-500/10 z-10'}`}
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
                            <div className="w-14 h-14 bg-white/5 rounded-full flex items-center justify-center mb-4 group-hover:bg-violet-500/20 group-hover:scale-110 transition-all duration-300"><Upload className="w-6 h-6 text-zinc-400 group-hover:text-violet-400" /></div>
                            <span className="text-sm font-bold text-white mb-1">Upload Layout</span>
                            <span className="text-xs text-zinc-500">PDF, PNG, JPG</span>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Right Col: Tabs & Content */}
                    <div className="flex-1 flex flex-col gap-4 min-w-0">
                      
                      {/* STICKY HEADER */}
                      <div className="sticky top-[-32px] bg-[#09090b] z-20 pt-8 pb-3 -mt-8 shadow-[0_10px_20px_-10px_#09090b]">
                        {/* Sub-Tabs */}
                        <div className="flex items-center gap-2 border-b border-white/10 pb-px">
                          <button onClick={() => setActiveTab('rooms')} className={`px-4 py-2 text-sm font-bold border-b-2 transition-all flex items-center gap-2 ${activeTab === 'rooms' ? 'border-violet-500 text-violet-400' : 'border-transparent text-zinc-500 hover:text-zinc-300'}`}>
                            <LayoutGrid className="w-4 h-4"/> Room-Wise Details
                          </button>
                          <button onClick={() => setActiveTab('floorSpecs')} className={`px-4 py-2 text-sm font-bold border-b-2 transition-all flex items-center gap-2 ${activeTab === 'floorSpecs' ? 'border-violet-500 text-violet-400' : 'border-transparent text-zinc-500 hover:text-zinc-300'}`}>
                            <Hammer className="w-4 h-4"/> Floor Structural
                          </button>
                        </div>

                        {/* Subheader descriptions based on tab */}
                        <div className="mt-4">
                          {activeTab === 'rooms' ? (
                            <div className="flex justify-between items-center">
                              <p className="text-xs text-zinc-400">Define finishes and individual openings per room.</p>
                              <button onClick={handleAddRoom} className="px-3 py-1.5 bg-violet-500 text-white rounded-lg text-xs font-bold hover:bg-violet-600 transition-all shadow-lg shadow-violet-500/20 flex items-center gap-1.5">
                                <Plus className="w-3.5 h-3.5"/> Add Room
                              </button>
                            </div>
                          ) : (
                            <div className="flex items-center justify-between">
                              <p className="text-xs text-zinc-400">Define global structural settings and schedules for this floor.</p>
                            </div>
                          )}
                        </div>
                      </div>

                      {/* Tab Content: Floor Structural (Schedules) */}
                      {activeTab === 'floorSpecs' && (
                        <div className="flex flex-col gap-6 animate-in fade-in">
                          <div className="bg-[#18181b] border border-white/5 rounded-xl p-6 flex flex-col gap-5">
                            <h4 className="text-sm font-bold text-white uppercase tracking-widest text-zinc-400">Floor Geometry & Staircase</h4>
                            <div className="grid grid-cols-4 gap-4">
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
                            
                            <h4 className="text-sm font-bold text-white uppercase tracking-widest text-zinc-400 mt-4 border-t border-white/5 pt-5">Railings</h4>
                            <div className="grid grid-cols-3 gap-4">
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
                            <div className="bg-[#18181b] border border-white/5 border-dashed rounded-xl p-10 text-center flex flex-col items-center justify-center">
                              <LayoutGrid className="w-10 h-10 text-zinc-600 mb-3" />
                              <p className="text-sm text-zinc-400 font-medium mb-1">No rooms added to this floor</p>
                              <p className="text-xs text-zinc-600">Click "Add Room" to specify details for bedrooms, kitchens, etc.</p>
                            </div>
                          ) : (
                            <div className="flex flex-col gap-3 pb-8">
                              {activeFloor.rooms.map((room: any, rIdx: number) => {
                                const isExpanded = expandedRoomId === room.id;
                                return (
                                  <div 
                                    key={room.id} 
                                    className="bg-[#18181b] border border-white/5 rounded-xl overflow-hidden transition-all duration-300 relative"
                                    onMouseEnter={() => setHoveredRoomId(room.id)}
                                    onMouseLeave={() => setHoveredRoomId(null)}
                                  >
                                    <div 
                                      className="px-5 py-4 flex items-center justify-between cursor-pointer hover:bg-white/[0.02]"
                                      onClick={() => setExpandedRoomId(isExpanded ? null : room.id)}
                                    >
                                      <div className="flex items-center gap-4">
                                        <div className={`p-1.5 rounded-md ${isExpanded ? 'bg-violet-500/20 text-violet-400' : 'bg-white/5 text-zinc-400'}`}>
                                          {isExpanded ? <ChevronUp className="w-4 h-4"/> : <ChevronDown className="w-4 h-4"/>}
                                        </div>
                                        <input 
                                          value={room.name} 
                                          onChange={e => updateRoom(rIdx, 'name', e.target.value)} 
                                          onClick={e => e.stopPropagation()}
                                          className="bg-transparent text-sm font-bold text-white outline-none border-b border-transparent focus:border-violet-500 px-1 placeholder-zinc-600"
                                          placeholder="e.g. Master Bedroom"
                                        />
                                      </div>
                                      <button 
                                        onClick={(e) => { e.stopPropagation(); const nf = [...floors]; nf[activeFloorIndex].rooms.splice(rIdx,1); setFloors(nf); }} 
                                        className="text-zinc-500 hover:text-red-400 transition-colors p-1"
                                      >
                                        <Trash2 className="w-4 h-4"/>
                                      </button>
                                    </div>

                                    {isExpanded && (
                                      <div className="px-5 pb-6 pt-4 border-t border-white/5 bg-black/20 animate-in slide-in-from-top-2 duration-200">
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

                                          <div className="h-px bg-white/5 col-span-3"/>
                                          
                                          {/* Action Buttons for Doors & Windows Modals */}
                                          <div className="col-span-3 flex items-center gap-4">
                                            <button 
                                              onClick={() => setDoorModalRoomIdx(rIdx)}
                                              className="flex-1 py-3 px-4 bg-[#111] hover:bg-[#151515] border border-white/10 rounded-xl flex items-center justify-between group transition-all"
                                            >
                                              <div className="flex items-center gap-3">
                                                <div className="w-8 h-8 rounded-lg bg-pink-500/10 flex items-center justify-center border border-pink-500/20">
                                                  <div className="w-4 h-5 border-2 border-pink-400 rounded-sm relative"><div className="absolute right-1 top-1/2 w-0.5 h-0.5 bg-pink-400 rounded-full"/></div>
                                                </div>
                                                <div className="flex flex-col text-left">
                                                  <span className="text-sm font-bold text-white">Configure Doors</span>
                                                  <span className="text-[10px] text-zinc-500">{room.doors.length} profiles</span>
                                                </div>
                                              </div>
                                              <ChevronRight className="w-4 h-4 text-zinc-600 group-hover:text-white transition-colors" />
                                            </button>

                                            <button 
                                              onClick={() => setWindowModalRoomIdx(rIdx)}
                                              className="flex-1 py-3 px-4 bg-[#111] hover:bg-[#151515] border border-white/10 rounded-xl flex items-center justify-between group transition-all"
                                            >
                                              <div className="flex items-center gap-3">
                                                <div className="w-8 h-8 rounded-lg bg-blue-500/10 flex items-center justify-center border border-blue-500/20">
                                                  <div className="w-5 h-5 border-2 border-blue-400 rounded-sm grid grid-cols-2 grid-rows-2 gap-px p-0.5"><div className="bg-blue-400/50"/><div className="bg-blue-400/50"/><div className="bg-blue-400/50"/><div className="bg-blue-400/50"/></div>
                                                </div>
                                                <div className="flex flex-col text-left">
                                                  <span className="text-sm font-bold text-white">Configure Windows</span>
                                                  <span className="text-[10px] text-zinc-500">{room.windows.length} profiles</span>
                                                </div>
                                              </div>
                                              <ChevronRight className="w-4 h-4 text-zinc-600 group-hover:text-white transition-colors" />
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
                              <div className="bg-[#18181b] border border-white/10 rounded-xl shadow-2xl w-full max-w-3xl flex flex-col overflow-hidden animate-in zoom-in-95 duration-200">
                                <div className="p-5 border-b border-white/5 flex items-center justify-between">
                                  <div className="flex flex-col">
                                    <h4 className="font-bold text-white text-sm flex items-center gap-2">
                                      <div className="w-4 h-5 border-2 border-pink-400 rounded-sm relative"><div className="absolute right-0.5 top-1/2 w-0.5 h-0.5 bg-pink-400 rounded-full"/></div>
                                      Doors <span className="text-zinc-600">—</span> <span className="text-pink-400">{activeFloor.rooms[doorModalRoomIdx].name}</span>
                                    </h4>
                                    <span className="text-[10px] text-zinc-500">{activeFloor.rooms[doorModalRoomIdx].doors.length} door spec(s) configured</span>
                                  </div>
                                  <button onClick={() => setDoorModalRoomIdx(null)} className="p-1.5 text-zinc-500 hover:text-white hover:bg-white/5 rounded-md"><X className="w-4 h-4"/></button>
                                </div>
                                <div className="p-5 flex-1 overflow-y-auto bg-[#09090b]">
                                  <div className="flex items-center justify-between mb-4">
                                    <span className="text-xs font-bold text-white tracking-wide">Door profiles for this room</span>
                                    <button onClick={() => handleAddDoor(doorModalRoomIdx)} className="bg-gradient-to-r from-pink-500 to-purple-500 hover:from-pink-400 hover:to-purple-400 text-white text-xs font-bold px-3 py-1.5 rounded-full flex items-center gap-1.5 shadow-[0_0_15px_rgba(236,72,153,0.3)]"><Plus className="w-3.5 h-3.5"/> Add Door</button>
                                  </div>
                                  <div className="space-y-3">
                                    {activeFloor.rooms[doorModalRoomIdx].doors.map((door: any, dIdx: number) => (
                                      <div key={door.id} className="bg-[#111] border border-white/5 rounded-xl p-4 flex flex-col gap-4 group relative hover:border-pink-500/30 transition-colors">
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
                                      <div className="text-center py-6 text-zinc-500 text-sm italic">No doors added yet.</div>
                                    )}
                                  </div>
                                </div>
                                <div className="p-4 border-t border-white/5 flex justify-end">
                                  <button onClick={() => setDoorModalRoomIdx(null)} className="px-6 py-2 bg-gradient-to-r from-pink-500 to-purple-500 text-white text-sm font-bold rounded-lg shadow-lg">Done</button>
                                </div>
                              </div>
                            </div>
                          )}

                          {windowModalRoomIdx !== null && (
                            <div className="absolute inset-0 bg-black/60 backdrop-blur-sm z-20 flex items-center justify-center p-4">
                              <div className="bg-[#18181b] border border-white/10 rounded-xl shadow-2xl w-full max-w-4xl flex flex-col overflow-hidden animate-in zoom-in-95 duration-200">
                                <div className="p-5 border-b border-white/5 flex items-center justify-between">
                                  <div className="flex flex-col">
                                    <h4 className="font-bold text-white text-sm flex items-center gap-2">
                                      <div className="w-4 h-4 border-2 border-blue-400 rounded-sm grid grid-cols-2 grid-rows-2 gap-px p-px"><div className="bg-blue-400/50"/><div className="bg-blue-400/50"/><div className="bg-blue-400/50"/><div className="bg-blue-400/50"/></div>
                                      Windows <span className="text-zinc-600">—</span> <span className="text-blue-400">{activeFloor.rooms[windowModalRoomIdx].name}</span>
                                    </h4>
                                    <span className="text-[10px] text-zinc-500">{activeFloor.rooms[windowModalRoomIdx].windows.length} window spec(s) configured</span>
                                  </div>
                                  <button onClick={() => setWindowModalRoomIdx(null)} className="p-1.5 text-zinc-500 hover:text-white hover:bg-white/5 rounded-md"><X className="w-4 h-4"/></button>
                                </div>
                                <div className="p-5 flex-1 overflow-y-auto bg-[#09090b]">
                                  <div className="flex items-center justify-between mb-4">
                                    <span className="text-xs font-bold text-white tracking-wide">Window & ventilator profiles</span>
                                    <button onClick={() => handleAddWindow(windowModalRoomIdx)} className="bg-gradient-to-r from-pink-500 to-purple-500 hover:from-pink-400 hover:to-purple-400 text-white text-xs font-bold px-3 py-1.5 rounded-full flex items-center gap-1.5 shadow-[0_0_15px_rgba(236,72,153,0.3)]"><Plus className="w-3.5 h-3.5"/> Add Window</button>
                                  </div>
                                  <div className="space-y-3">
                                    {activeFloor.rooms[windowModalRoomIdx].windows.map((win: any, wIdx: number) => (
                                      <div key={win.id} className="bg-[#111] border border-white/5 rounded-xl p-4 flex flex-col gap-4 group relative hover:border-blue-500/30 transition-colors">
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
                                            <label className="flex items-center gap-2 cursor-pointer text-xs font-bold text-zinc-300 hover:text-white transition-colors">
                                              <input type="checkbox" checked={win.hasSillJamb} onChange={e => updateWindow(windowModalRoomIdx, wIdx, 'hasSillJamb', e.target.checked)} className="rounded border-white/10 bg-[#111] text-violet-500 focus:ring-violet-500 w-4 h-4" />
                                              Sill & Jamb
                                            </label>
                                          </div>
                                        </div>
                                        
                                        {win.hasSillJamb && (
                                          <div className="grid grid-cols-2 gap-4 pt-4 border-t border-white/5 animate-in fade-in slide-in-from-top-2">
                                            <div className="col-span-1">{renderInput("Sill Width (m)", win.sillWidth, v => updateWindow(windowModalRoomIdx, wIdx, 'sillWidth', v))}</div>
                                            <div className="col-span-1">{renderInput("Jamb Width (m)", win.jambWidth, v => updateWindow(windowModalRoomIdx, wIdx, 'jambWidth', v))}</div>
                                          </div>
                                        )}
                                      </div>
                                    ))}
                                    {activeFloor.rooms[windowModalRoomIdx].windows.length === 0 && (
                                      <div className="text-center py-6 text-zinc-500 text-sm italic">No windows added yet.</div>
                                    )}
                                  </div>
                                </div>
                                <div className="p-4 border-t border-white/5 flex justify-end">
                                  <button onClick={() => setWindowModalRoomIdx(null)} className="px-6 py-2 bg-gradient-to-r from-pink-500 to-purple-500 text-white text-sm font-bold rounded-lg shadow-lg">Done</button>
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
        <div className="px-8 py-5 border-t border-white/10 bg-[#09090b] flex justify-between items-center z-10 shrink-0">
          {step === 1 ? <div/> : (
            <button onClick={() => setStep(step-1)} className="px-5 py-2.5 rounded-xl text-sm font-bold text-zinc-400 hover:text-white hover:bg-white/5 transition-all">
              Back
            </button>
          )}

          {step < 2 ? (
            <button onClick={handleNextStep} disabled={loading} className="px-8 py-2.5 bg-white text-black rounded-lg text-sm font-bold shadow-[0_0_20px_rgba(255,255,255,0.1)] hover:shadow-[0_0_25px_rgba(255,255,255,0.2)] hover:scale-[1.02] transition-all flex items-center gap-2">
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <>Next Step <ChevronRight className="w-4 h-4" /></>}
            </button>
          ) : (
            <button onClick={handleFinish} disabled={loading} className="px-8 py-2.5 bg-violet-500 text-white rounded-lg text-sm font-bold shadow-[0_0_20px_rgba(139,92,246,0.3)] hover:bg-violet-400 hover:scale-[1.02] transition-all flex items-center gap-2">
              {loading ? <Loader2 className="w-4 h-4 animate-spin"/> : 'Finalize & Start OCR'} <Check className="w-4 h-4"/>
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
