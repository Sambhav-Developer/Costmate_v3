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
  const [status, setStatus] = useState('idle');
  const [step, setStep] = useState('');
  const [logs, setLogs] = useState<TerminalLog[]>([]);

  const addLog = (message: string, type: TerminalLog['type'] = 'stdout') => {
    const timestamp = new Date().toLocaleTimeString();
    setLogs((prev) => [...prev, { timestamp, message, type }]);
  };

  // Smooth fake-progress interpolator
  useEffect(() => {
    if (status === 'processing' || status === 'calculating') {
      const interval = setInterval(() => {
        setProgress(prev => {
          // If we are below 14%, crawl to 14%
          if (prev < 14) return parseFloat((prev + 0.3).toFixed(1));
          // After QA (14%), crawl towards 90% while calculating
          if (prev >= 14 && prev < 90) {
            // Asymptotic slowdown towards 90
            const step = (90 - prev) * 0.02;
            return parseFloat((prev + Math.max(step, 0.1)).toFixed(1));
          }
          return prev;
        });
      }, 500);
      return () => clearInterval(interval);
    }
  }, [status]);

  // Reset state when session ID changes
  useEffect(() => {
    if (!sessionId) {
      setProgress(0);
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
          setProgress(data.progress);
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
          case 'ocr_completed':
            addLog('◽ Node completed: OCR scanner parsed floor plan annotations and symbols.', 'info');
            break;
          case 'vision_agents_completed':
            addLog('◽ Swarm completed: Vision sub-agents extracted room dimensions and elements.', 'info');
            break;
          case 'qa_prefilled':
            addLog('◽ Prefill completed: 18-question config parameters populated from layout model.', 'info');
            break;
          case 'paused_qa':
            addLog('⏸️ PIPELINE INTERRUPTED: Awaiting engineering review in qa_config.json...', 'warn');
            if (onQAWaiting) onQAWaiting();
            break;
          case 'quantities_calculated':
            addLog('◽ Swarm completed: Civil volumes and reinforcement steel tonnages calculated.', 'info');
            break;
          case 'validation_completed':
            addLog('◽ Node completed: CHOPS validation checklist verification passed.', 'info');
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
