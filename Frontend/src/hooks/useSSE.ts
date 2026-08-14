import { useState, useEffect } from 'react';
import { api } from '../lib/api';

export interface TerminalLog {
  timestamp: string;
  message: string;
  type: 'info' | 'success' | 'warn' | 'error' | 'stdout';
}

export function useSSE(
  sessionId: string | null,
  isTerminal: boolean,
  onCompleted?: () => void,
  onQAWaiting?: () => void
) {
  const [progress, setProgress] = useState(0);
  const [targetProgress, setTargetProgress] = useState(0);
  const [status, setStatus] = useState('idle');
  const [step, setStep] = useState('');
  const [logs, setLogs] = useState<TerminalLog[]>([]);

  const addLog = (message: string, type: TerminalLog['type'] = 'stdout') => {
    const timestamp = new Date().toLocaleTimeString();
    setLogs((prev) => [...prev, { timestamp, message, type }]);
  };

  // Smooth progressive progress interpolator to target
  useEffect(() => {
    if (status === 'processing' || status === 'calculating') {
      const interval = setInterval(() => {
        setProgress(prev => {
          if (prev < targetProgress) {
            // Increment by 1% at a time for smooth animation
            return parseFloat(Math.min(prev + 1, targetProgress).toFixed(1));
          }
          return prev;
        });
      }, 100);
      return () => clearInterval(interval);
    }
  }, [status, targetProgress]);

  // Reset state when session ID changes
  useEffect(() => {
    if (!sessionId) {
      setProgress(0);
      setTargetProgress(0);
      setStatus('idle');
      setStep('');
      setLogs([]);
    }
  }, [sessionId]);

  useEffect(() => {
    if (!sessionId || isTerminal) {
      return;
    }

    addLog(`Establishing connection to Agent stream for session ${sessionId.substring(0, 8)}...`, 'info');
    const es = api.statusEventSource(sessionId);

    es.onopen = () => {
      addLog('Secure stream connection established with Civil Work Estimator.', 'success');
      setStatus('processing');
    };

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        if (data.progress !== undefined) {
          setTargetProgress(data.progress);
        }
        if (data.status !== undefined) {
          setStatus(data.status);
        }
        if (data.step !== undefined) {
          setStep(data.step);
        }

        // Map step event to descriptive logs
        switch (data.step) {
          case 'upload_completed':
            addLog('🚀 File uploaded successfully. Initializing Civil Work Estimator pipeline.', 'info');
            break;
          case 'specs_analyzed':
            addLog('◽ Node completed: Specifications analyzed and project context established.', 'info');
            break;
          case 'schedule_parsed':
            addLog('◽ Node completed: Door and Window schedules parsed successfully.', 'info');
            break;
          case 'ocr_completed':
            addLog('◽ Node completed: OCR consensus pass compiled layout characters.', 'info');
            break;
          case 'cv_detector_completed':
            addLog('◽ Swarm completed: Computer Vision element detector located callout tags.', 'info');
            break;
          case 'reconciliation_completed':
            addLog('◽ Node completed: Extracted counts reconciled against schedule registry.', 'info');
            break;
          case 'paused_qa':
            addLog('⏸️ PIPELINE INTERRUPTED: Awaiting engineering review in config parameters...', 'warn');
            if (onQAWaiting) onQAWaiting();
            break;
          case 'completed':
            addLog('✅ ESTIMATE READY: BOQ spreadsheet estimate generated successfully.', 'success');
            if (onCompleted) onCompleted();
            break;
          case 'error':
            addLog(`❌ EXCEPTION DETECTED: ${data.error || 'Unknown failure'}`, 'error');
            break;
          default:
            addLog(`Executing: ${data.step}...`, 'stdout');
            break;
        }
      } catch (err: any) {
        addLog(`Error parsing event data: ${err.message}`, 'error');
      }
    };

    es.onerror = () => {
      addLog('Stream disconnected. Auto-reconnecting...', 'warn');
    };

    return () => {
      es.close();
      addLog('Stream closed by client.', 'info');
    };
  }, [sessionId, isTerminal]);

  return {
    progress,
    status,
    step,
    logs,
    clearLogs: () => setLogs([]),
    addCustomLog: addLog
  };
}
