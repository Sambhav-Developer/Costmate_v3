"use client";

import React, { useState, useRef, useEffect } from "react";
import { Upload, FileText, CheckCircle, Activity, LayoutTemplate, Play, FileUp, AlertTriangle } from "lucide-react";

export default function DoorsWindowsPipeline() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  
  // Step state: 0=Init, 1=Schedule, 2=Plan, 3=Processing, 4=Completed
  const [currentStep, setCurrentStep] = useState<number>(0);
  
  const [scheduleFiles, setScheduleFiles] = useState<File[]>([]);
  const [planFiles, setPlanFiles] = useState<File[]>([]);
  
  const [isUploading, setIsUploading] = useState(false);
  const [statusData, setStatusData] = useState<any>(null);

  const scheduleInputRef = useRef<HTMLInputElement>(null);
  const planInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    // Create session on mount
    const initSession = async () => {
      try {
        const res = await fetch("http://localhost:8000/api/v2/doors-windows/session", {
          method: "POST",
          headers: {
            "Authorization": `Bearer ${localStorage.getItem("token") || ""}`
          }
        });
        const data = await res.json();
        if (data.session_id) {
          setSessionId(data.session_id);
          setCurrentStep(1);
        }
      } catch (e) {
        console.error("Failed to init session", e);
      }
    };
    initSession();
  }, []);

  // Poll for status when processing
  useEffect(() => {
    if (currentStep !== 3 || !sessionId) return;
    
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`http://localhost:8000/api/v2/doors-windows/${sessionId}/status`, {
          headers: { "Authorization": `Bearer ${localStorage.getItem("token") || ""}` }
        });
        const data = await res.json();
        setStatusData(data);
        
        if (data.status === "completed" || data.status === "error") {
          setCurrentStep(4);
          clearInterval(interval);
        }
      } catch (e) {
        console.error("Polling error", e);
      }
    }, 3000);
    
    return () => clearInterval(interval);
  }, [currentStep, sessionId]);

  const handleFileUpload = async (file: File, type: "schedule" | "plan") => {
    if (!sessionId) return;
    
    setIsUploading(true);
    const formData = new FormData();
    formData.append("file", file);
    
    try {
      await fetch(`http://localhost:8000/api/v2/doors-windows/${sessionId}/${type}`, {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${localStorage.getItem("token") || ""}`
        },
        body: formData
      });
      
      if (type === "schedule") {
        setScheduleFiles(prev => [...prev, file]);
        setCurrentStep(2); // Move to plan upload
      } else {
        setPlanFiles(prev => [...prev, file]);
      }
    } catch (e) {
      console.error(`Upload ${type} failed`, e);
      alert(`Failed to upload ${type}`);
    } finally {
      setIsUploading(false);
    }
  };

  const startProcessing = async () => {
    if (!sessionId || planFiles.length === 0) return;
    
    setIsUploading(true);
    try {
      await fetch(`http://localhost:8000/api/v2/doors-windows/${sessionId}/process`, {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${localStorage.getItem("token") || ""}`
        }
      });
      setCurrentStep(3);
    } catch (e) {
      console.error("Failed to start processing", e);
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="min-h-screen bg-neutral-950 text-white p-8 font-sans selection:bg-indigo-500/30">
      <div className="max-w-4xl mx-auto space-y-8">
        
        {/* Header */}
        <div className="border-b border-white/10 pb-6">
          <h1 className="text-3xl font-light tracking-tight text-white mb-2 flex items-center gap-3">
            <LayoutTemplate className="w-8 h-8 text-indigo-400" />
            Doors & Windows <span className="font-semibold text-indigo-400">Pipeline V2</span>
          </h1>
          <p className="text-neutral-400 text-lg font-light">
            Specialized 2-stage extraction using schedule ingestion and plan reconciliation.
          </p>
        </div>

        {/* Pipeline Steps */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12">
          {/* Step 1: Schedule */}
          <div className={`p-6 rounded-2xl border transition-all duration-500 ${currentStep >= 1 ? 'border-indigo-500/30 bg-indigo-500/5 shadow-[0_0_30px_-5px_rgba(99,102,241,0.1)]' : 'border-white/5 bg-neutral-900/50 opacity-50'}`}>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-medium text-white flex items-center gap-2">
                <span className="flex items-center justify-center w-6 h-6 rounded-full bg-indigo-500/20 text-indigo-400 text-sm">1</span>
                Schedule
              </h2>
              {scheduleFiles.length > 0 && <CheckCircle className="w-5 h-5 text-emerald-400" />}
            </div>
            <p className="text-sm text-neutral-400 mb-6">Upload the door/window schedule tables.</p>
            
            <button 
              onClick={() => scheduleInputRef.current?.click()}
              disabled={isUploading || currentStep === 3}
              className="w-full py-3 px-4 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 flex items-center justify-center gap-2 text-sm font-medium transition-colors disabled:opacity-50"
            >
              <FileUp className="w-4 h-4" />
              {isUploading && currentStep === 1 ? "Uploading..." : "Upload Schedule"}
            </button>
            <input 
              type="file" 
              ref={scheduleInputRef} 
              className="hidden" 
              onChange={(e) => e.target.files && handleFileUpload(e.target.files[0], "schedule")} 
            />
            
            {scheduleFiles.length > 0 && (
              <div className="mt-4 space-y-2">
                {scheduleFiles.map((f, i) => (
                  <div key={i} className="text-xs text-indigo-300 flex items-center gap-1 bg-indigo-500/10 py-1.5 px-3 rounded-lg">
                    <FileText className="w-3 h-3" /> {f.name}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Step 2: Plan */}
          <div className={`p-6 rounded-2xl border transition-all duration-500 ${currentStep >= 2 ? 'border-indigo-500/30 bg-indigo-500/5 shadow-[0_0_30px_-5px_rgba(99,102,241,0.1)]' : 'border-white/5 bg-neutral-900/50 opacity-50'}`}>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-medium text-white flex items-center gap-2">
                <span className="flex items-center justify-center w-6 h-6 rounded-full bg-indigo-500/20 text-indigo-400 text-sm">2</span>
                Floor Plan
              </h2>
              {planFiles.length > 0 && <CheckCircle className="w-5 h-5 text-emerald-400" />}
            </div>
            <p className="text-sm text-neutral-400 mb-6">Upload the architectural layout sheets.</p>
            
            <button 
              onClick={() => planInputRef.current?.click()}
              disabled={isUploading || currentStep < 2 || currentStep === 3}
              className="w-full py-3 px-4 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 flex items-center justify-center gap-2 text-sm font-medium transition-colors disabled:opacity-50"
            >
              <FileUp className="w-4 h-4" />
              Upload Plan
            </button>
            <input 
              type="file" 
              ref={planInputRef} 
              className="hidden" 
              onChange={(e) => e.target.files && handleFileUpload(e.target.files[0], "plan")} 
            />

            {planFiles.length > 0 && (
              <div className="mt-4 space-y-2">
                {planFiles.map((f, i) => (
                  <div key={i} className="text-xs text-indigo-300 flex items-center gap-1 bg-indigo-500/10 py-1.5 px-3 rounded-lg">
                    <FileText className="w-3 h-3" /> {f.name}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Step 3: Process */}
          <div className={`p-6 rounded-2xl border transition-all duration-500 ${planFiles.length > 0 || currentStep >= 3 ? 'border-indigo-500/30 bg-indigo-500/5 shadow-[0_0_30px_-5px_rgba(99,102,241,0.1)]' : 'border-white/5 bg-neutral-900/50 opacity-50'}`}>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-medium text-white flex items-center gap-2">
                <span className="flex items-center justify-center w-6 h-6 rounded-full bg-indigo-500/20 text-indigo-400 text-sm">3</span>
                Extract
              </h2>
              {currentStep === 4 && <CheckCircle className="w-5 h-5 text-emerald-400" />}
            </div>
            <p className="text-sm text-neutral-400 mb-6">Run AI ingestion and reconciliation.</p>
            
            <button 
              onClick={startProcessing}
              disabled={planFiles.length === 0 || currentStep >= 3}
              className="w-full py-3 px-4 rounded-xl bg-indigo-500 hover:bg-indigo-400 text-white flex items-center justify-center gap-2 text-sm font-medium transition-all disabled:opacity-50 disabled:bg-neutral-800 disabled:text-neutral-500"
            >
              {currentStep === 3 ? (
                <><Activity className="w-4 h-4 animate-spin" /> Processing...</>
              ) : (
                <><Play className="w-4 h-4 fill-current" /> Start Processing</>
              )}
            </button>
          </div>
        </div>

        {/* Results Area */}
        {currentStep >= 3 && statusData && (
          <div className="bg-neutral-900/50 border border-white/10 rounded-2xl p-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <h3 className="text-2xl font-light mb-6 flex items-center gap-3">
              {currentStep === 3 ? (
                <><Activity className="w-6 h-6 text-indigo-400 animate-pulse" /> AI Extraction in Progress</>
              ) : (
                <><CheckCircle className="w-6 h-6 text-emerald-400" /> Extraction Complete</>
              )}
            </h3>
            
            {statusData.error && (
              <div className="bg-red-500/10 border border-red-500/20 p-4 rounded-xl flex gap-3 text-red-400 mb-6">
                <AlertTriangle className="w-5 h-5 shrink-0" />
                <p className="text-sm">{statusData.error}</p>
              </div>
            )}

            <div className="space-y-6">
              {/* Schedule Registry Preview */}
              {statusData.schedule_registry && (
                <div className="bg-black/40 rounded-xl p-6 border border-white/5">
                  <h4 className="text-sm font-semibold text-indigo-400 uppercase tracking-wider mb-4">Ingested Schedule Registry</h4>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="bg-white/5 p-4 rounded-lg">
                      <div className="text-3xl font-light text-white mb-1">
                        {statusData.schedule_registry.type_registry?.doors?.length || 0}
                      </div>
                      <div className="text-xs text-neutral-400 uppercase tracking-wider">Door Types</div>
                    </div>
                    <div className="bg-white/5 p-4 rounded-lg">
                      <div className="text-3xl font-light text-white mb-1">
                        {statusData.schedule_registry.type_registry?.windows?.length || 0}
                      </div>
                      <div className="text-xs text-neutral-400 uppercase tracking-wider">Window Types</div>
                    </div>
                  </div>
                </div>
              )}

              {/* Reconciliation Results */}
              {statusData.reconciliation_result && (
                <div className="bg-black/40 rounded-xl p-6 border border-white/5">
                  <h4 className="text-sm font-semibold text-emerald-400 uppercase tracking-wider mb-4">Reconciliation Summary</h4>
                  <p className="text-neutral-300 text-sm leading-relaxed mb-6">
                    {statusData.reconciliation_result.summary}
                  </p>
                  
                  <div className="space-y-3">
                    {Object.entries(statusData.reconciliation_result.category_completeness || {}).map(([cat, data]: [string, any]) => (
                      <div key={cat} className="flex items-center justify-between bg-white/5 p-3 rounded-lg border border-white/5">
                        <span className="capitalize text-sm font-medium">{cat} Completeness</span>
                        <span className={`text-xs px-2 py-1 rounded-full font-medium ${data.status === 'pass' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'}`}>
                          {data.status.toUpperCase()} ({data.extracted_count} extracted)
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
