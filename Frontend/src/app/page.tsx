'use client';

import React, { useState, useEffect } from 'react';
import { 
  Building2, 
  Settings, 
  HelpCircle, 
  CircleDot,
  User,
  Key,
  Eye,
  EyeOff,
  Sun,
  Moon,
  Mail,
  ShieldCheck,
  Layers,
  Sparkles
} from 'lucide-react';
import Sidebar from '../components/Sidebar';
import TabEditor from '../components/TabEditor';
import CopilotPanel from '../components/CopilotPanel';
import ThemeToggle from '../components/ThemeToggle';
import FileViewerPanel from '../components/editor/FileViewerPanel';
import { useAuth } from '../hooks/useAuth';
import { useSSE } from '../hooks/useSSE';
import { api } from '../lib/api';
import { GoogleLogin } from '@react-oauth/google';
import { useTheme } from '../components/ThemeProvider';

interface EstimationSession {
  id: string;
  filename: string;
  date: string;
  status: string;
}

export default function Page() {
  const { isLoggedIn, loading: authLoading, user, logout, refresh } = useAuth();
  const { theme } = useTheme();
  
  const handleGoogleSuccess = async (credentialResponse: any) => {
    setAuthError(null);
    setAuthFormLoading(true);
    try {
      const idToken = credentialResponse.credential;
      if (!idToken) throw new Error("No ID Token returned from Google");
      await api.loginWithGoogle(idToken);
      refresh();
    } catch (err: any) {
      setAuthError(err.message || 'Google Sign In failed');
    } finally {
      setAuthFormLoading(false);
    }
  };

  const handleGoogleError = () => {
    setAuthError('Google Sign In failed. Please try again.');
  };
  
  // Auth Form State
  const [authMode, setAuthMode] = useState<'login' | 'signup' | 'otp'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [otp, setOtp] = useState('');
  const [otpArray, setOtpArray] = useState<string[]>(Array(6).fill(''));
  const [showPassword, setShowPassword] = useState(false);
  const [authError, setAuthError] = useState<string | null>(null);
  const [authSuccessMessage, setAuthSuccessMessage] = useState<string | null>(null);
  const [authFormLoading, setAuthFormLoading] = useState(false);

  // Handle OTP digit changes
  const handleOtpChange = (element: HTMLInputElement, index: number) => {
    const val = element.value.replace(/\D/g, '');
    if (!val) {
      const newOtp = [...otpArray];
      newOtp[index] = '';
      setOtpArray(newOtp);
      setOtp(newOtp.join(''));
      return;
    }

    const newOtp = [...otpArray];
    newOtp[index] = val[val.length - 1];
    setOtpArray(newOtp);
    setOtp(newOtp.join(''));

    // Move focus to next input
    if (index < 5 && val) {
      const nextInput = element.parentNode?.children[index + 1] as HTMLInputElement;
      if (nextInput) {
        nextInput.focus();
      }
    }
  };

  const handleOtpKeyDown = (e: React.KeyboardEvent<HTMLInputElement>, index: number) => {
    if (e.key === 'Backspace') {
      if (!otpArray[index] && index > 0) {
        const prevInput = e.currentTarget.parentNode?.children[index - 1] as HTMLInputElement;
        if (prevInput) {
          prevInput.focus();
        }
      }
    }
  };

  const handleOtpPaste = (e: React.ClipboardEvent<HTMLInputElement>) => {
    e.preventDefault();
    const pastedData = e.clipboardData.getData('text').replace(/\D/g, '').substring(0, 6);
    if (pastedData.length === 6) {
      const newOtp = pastedData.split('');
      setOtpArray(newOtp);
      setOtp(pastedData);
      
      const inputs = e.currentTarget.children;
      if (inputs && inputs.length === 6) {
        (inputs[5] as HTMLInputElement).focus();
      }
    }
  };

  // Workspace States
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'drawing' | 'qa' | 'result'>('drawing');
  const [sessionState, setSessionState] = useState<any>(null);
  const [sessionsList, setSessionsList] = useState<EstimationSession[]>([]);
  // File viewer: which file sub-item is active (plan / excel / readme / parameters)
  const [activeFile, setActiveFile] = useState<{ sessionId: string; fileType: 'plan' | 'excel' | 'readme' | 'parameters' } | null>(null);

  const fetchSessions = async () => {
    try {
      const data = await api.listSessions();
      setSessionsList(data);
      
      // Restore last active session if it exists in the history
      const savedActiveId = localStorage.getItem('costmate_active_session_id');
      if (savedActiveId && data.some((s: any) => s.id === savedActiveId)) {
        setActiveSessionId(savedActiveId);
      }
    } catch (err: any) {
      console.warn("Failed to load sessions list from database:", err.message || err);
    }
  };

  // Load history and active session from database on login changes
  useEffect(() => {
    if (isLoggedIn) {
      fetchSessions();
    } else {
      setSessionsList([]);
      setActiveSessionId(null);
      setSessionState(null);
    }
  }, [isLoggedIn]);

  // Keep track of active session ID in localStorage
  useEffect(() => {
    if (isLoggedIn) {
      if (activeSessionId) {
        localStorage.setItem('costmate_active_session_id', activeSessionId);
      } else {
        localStorage.removeItem('costmate_active_session_id');
      }
    } else {
      localStorage.removeItem('costmate_active_session_id');
    }
  }, [activeSessionId, isLoggedIn]);

  // Fetch complete state for selected session
  const loadSessionState = async (sessionId: string) => {
    try {
      const data = await api.getSession(sessionId);
      setSessionState(data);
      
      // Select appropriate tab based on status
      if (data.status === 'completed') {
        setActiveTab('result');
      } else if (data.current_step === 'qa_prefilled' || data.current_step === 'paused_qa') {
        setActiveTab('qa');
      } else {
        setActiveTab('drawing');
      }
      
      // Update session status in sidebar history list
      setSessionsList((prev) => prev.map(s => {
        if (s.id === sessionId) {
          const derivedStatus = (data.current_step === 'qa_prefilled' || data.current_step === 'paused_qa') && data.status !== 'completed' && data.status !== 'failed' 
            ? 'paused_qa' 
            : data.status;
          return { ...s, status: derivedStatus };
        }
        return s;
      }));
    } catch (err: any) {
      console.warn("Failed to load session:", err.message || err);
      if (err.message && err.message.includes("Session not found")) {
        setActiveSessionId(null);
        setSessionState(null);
        setSessionsList((prev) => prev.filter((s) => s.id !== sessionId));
      }
    }
  };

  useEffect(() => {
    if (activeSessionId) {
      loadSessionState(activeSessionId);
    }
  }, [activeSessionId]);

  // SSE Callbacks
  const handleQAWaiting = () => {
    if (sessionState?.current_step !== 'paused_qa' && sessionState?.current_step !== 'qa_prefilled') {
      setActiveTab('qa');
    }
    if (activeSessionId) loadSessionState(activeSessionId);
  };

  const handleCompleted = () => {
    if (sessionState?.status !== 'completed') {
      setActiveTab('result');
    }
    if (activeSessionId) {
      loadSessionState(activeSessionId);
      
      // Update session status in sidebar history list
      setSessionsList((prev) => prev.map(s => s.id === activeSessionId ? { ...s, status: 'completed' } : s));
    }
  };

  const activeSession = sessionsList.find(s => s.id === activeSessionId);
  const currentStatus = sessionState ? sessionState.status : activeSession?.status;
  const isTerminal = currentStatus === 'completed' || currentStatus === 'failed';

  const { progress, status, step } = useSSE(activeSessionId, isTerminal, handleCompleted, handleQAWaiting);

  const handleSelectSession = (sessionId: string | null) => {
    if (activeSessionId !== sessionId) {
      setSessionState(null); // Prevent stale state leak
    }
    setActiveSessionId(sessionId);
    setActiveFile(null); // clear file viewer when switching sessions
  };

  const handleSelectFile = (sessionId: string, fileType: 'plan' | 'excel' | 'readme' | 'parameters', sessionName: string) => {
    setActiveFile({ sessionId, fileType });
    if (fileType === 'parameters') {
      setActiveTab('qa');
    }
    // Also ensure this session is selected
    if (activeSessionId !== sessionId) {
      setSessionState(null); // Prevent stale state leak
      setActiveSessionId(sessionId);
    }
  };

  const handleNewSessionCreated = (sessionId: string, filename: string) => {
    const newSession: EstimationSession = {
      id: sessionId,
      filename,
      date: new Date().toLocaleDateString(),
      status: 'processing'
    };
    
    setSessionsList((prev) => [newSession, ...prev]);
    
    setActiveSessionId(sessionId);
    setActiveTab('drawing');
  };

  // Handle Login / Signup / OTP
  const handleAuthSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthError(null);
    setAuthSuccessMessage(null);
    setAuthFormLoading(true);
    
    try {
      if (authMode === 'login') {
        await api.login(email.trim(), password);
        setEmail('');
        setPassword('');
        refresh();
      } else if (authMode === 'signup') {
        await api.signup(email.trim(), password);
        setAuthSuccessMessage("Verification code sent to email!");
        setAuthMode('otp');
      } else if (authMode === 'otp') {
        await api.verifyOtp(email.trim(), otp.trim());
        setEmail('');
        setPassword('');
        setOtp('');
        refresh();
      }
    } catch (err: any) {
      setAuthError(err.message || 'Authentication failed');
    } finally {
      setAuthFormLoading(false);
    }
  };

  if (authLoading) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center bg-bg text-fg font-sans">
        <CircleDot className="w-8 h-8 text-accent animate-spin mb-2" />
        <div className="text-sm font-medium text-slate-500">Checking credentials...</div>
      </div>
    );
  }

  // Render Login page if not logged in
  if (!isLoggedIn) {
    return (
      <div className="min-h-screen w-screen flex flex-col items-center justify-center bg-bg text-fg p-4 font-sans relative selection:bg-accent/20">
        {/* Floating Top Header for styling */}
        <div className="absolute top-6 right-6">
          <ThemeToggle />
        </div>

        <div className="w-full max-w-md bg-panel border border-border rounded-xl shadow-xl p-8 flex flex-col gap-6 transition-all duration-300">
          <div className="flex flex-col items-center gap-2 text-center">
            <div className="w-12 h-12 bg-accent/10 text-accent rounded-xl flex items-center justify-center border border-accent/20 animate-bounce-subtle">
              <Building2 className="w-6 h-6" />
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-fg">
              Civil Work Estimation
            </h1>
            <p className="text-sm text-slate-500 max-w-[280px]">
              AI-powered quantity takeoff and estimation platform
            </p>
          </div>

          <form onSubmit={handleAuthSubmit} className="flex flex-col gap-4">
            {authMode === 'otp' ? (
              <div className="flex flex-col gap-4">
                <div className="text-center bg-accent/5 border border-accent/10 p-4 rounded-lg flex flex-col items-center gap-1">
                  <ShieldCheck className="w-8 h-8 text-accent animate-pulse mb-1" />
                  <span className="text-xs font-semibold text-accent leading-none">Security Verification</span>
                  <p className="text-[11px] text-slate-500 mt-1 leading-normal max-w-xs">
                    We've emailed a 6-digit confirmation code (OTP) to your email. Please enter it below.
                  </p>
                </div>

                <div className="flex flex-col gap-2">
                  <label className="text-xs font-semibold text-slate-600 dark:text-slate-400 text-center mb-1">Verification Code</label>
                  <div className="flex justify-center gap-3" onPaste={handleOtpPaste}>
                    {otpArray.map((digit, idx) => (
                      <input
                        key={idx}
                        type="text"
                        maxLength={1}
                        value={digit}
                        onChange={(e) => handleOtpChange(e.target, idx)}
                        onKeyDown={(e) => handleOtpKeyDown(e, idx)}
                        className={`w-12 h-14 text-center text-xl font-bold rounded-xl border transition-all duration-150 font-mono shadow-sm focus:outline-none focus:ring-4 focus:ring-accent/15 focus:border-accent hover:scale-105 ${
                          digit 
                            ? 'border-accent bg-accent/5 dark:bg-accent/10 text-accent font-extrabold shadow-inner' 
                            : 'bg-panel border-slate-200 dark:border-border hover:border-slate-400 dark:hover:border-border/80 text-fg'
                        }`}
                        required
                      />
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex flex-col gap-3">
                <div className="flex flex-col gap-1.5">
                  <label className="text-xs font-semibold text-slate-600 dark:text-slate-400">Email Address</label>
                  <div className="relative flex items-center">
                    <Mail className="w-4 h-4 text-slate-500 absolute left-3" />
                    <input
                      type="email"
                      placeholder="you@example.com"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      className="w-full bg-bg/50 border border-border pl-10 pr-4 py-2.5 text-sm text-fg placeholder-slate-500 focus:outline-none focus:border-accent rounded-lg"
                      required
                    />
                  </div>
                </div>

                <div className="flex flex-col gap-1.5">
                  <label className="text-xs font-semibold text-slate-600 dark:text-slate-400">Password</label>
                  <div className="relative flex items-center">
                    <Key className="w-4 h-4 text-slate-500 absolute left-3" />
                    <input
                      type={showPassword ? 'text' : 'password'}
                      placeholder="Enter your password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      className="w-full bg-bg/50 border border-border pl-10 pr-10 py-2.5 text-sm text-fg placeholder-slate-500 focus:outline-none focus:border-accent rounded-lg"
                      required
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-3 p-1 text-slate-500 hover:text-fg transition-colors animate-fade-in"
                    >
                      {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                </div>
              </div>
            )}

            {authError && (
              <div className="text-xs text-red-500 bg-red-500/10 border border-red-500/20 p-3 rounded-lg leading-snug">
                {authError}
              </div>
            )}

            {authSuccessMessage && (
              <div className="text-xs text-emerald-500 bg-emerald-500/10 border border-emerald-500/20 p-3 rounded-lg leading-snug">
                {authSuccessMessage}
              </div>
            )}

            <button
              type="submit"
              disabled={authFormLoading}
              className="w-full bg-accent text-accent-fg font-bold py-2.5 rounded-lg hover:bg-accent-hover transition-all text-sm cursor-pointer disabled:opacity-50 mt-2 shadow-lg shadow-accent/15 active:scale-[0.98]"
            >
              {authFormLoading 
                ? 'Processing...' 
                : authMode === 'login' 
                  ? 'Sign In' 
                  : authMode === 'signup' 
                    ? 'Send Verification Code' 
                    : 'Verify & Register'}
            </button>
          </form>

          {authMode !== 'otp' && (
            <>
              <div className="relative flex py-1 items-center">
                <div className="flex-grow border-t border-border/80"></div>
                <span className="flex-shrink mx-4 text-slate-500 text-xs font-semibold uppercase">Or</span>
                <div className="flex-grow border-t border-border/80"></div>
              </div>

              <div className="flex justify-center w-full min-h-[40px] items-center">
                <GoogleLogin
                  onSuccess={handleGoogleSuccess}
                  onError={handleGoogleError}
                  theme={theme === 'dark' ? 'filled_black' : 'outline'}
                  size="large"
                  text="signin_with"
                  shape="rectangular"
                  width="382px"
                />
              </div>
            </>
          )}

          <div className="border-t border-border pt-4 text-center">
            {authMode === 'otp' ? (
              <button
                type="button"
                onClick={() => {
                  setAuthMode('signup');
                  setOtp('');
                  setOtpArray(Array(6).fill(''));
                  setAuthError(null);
                  setAuthSuccessMessage(null);
                }}
                className="text-xs text-accent hover:underline transition-colors font-medium"
              >
                ← Back to Sign Up
              </button>
            ) : (
              <button
                type="button"
                onClick={() => {
                  setAuthMode(authMode === 'login' ? 'signup' : 'login');
                  setOtp('');
                  setOtpArray(Array(6).fill(''));
                  setAuthError(null);
                  setAuthSuccessMessage(null);
                }}
                className="text-xs text-accent hover:underline transition-colors font-medium"
              >
                {authMode === 'login' ? "Don't have an account? Sign Up" : 'Already have an account? Sign In'}
              </button>
            )}
          </div>
        </div>
      </div>
    );
  }

  // Render Dashboard if logged in
  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-bg text-fg font-sans">
      {/* ── Top Header ── */}
      <header className="h-14 flex items-center justify-between px-6 glass-header shrink-0"
        style={{ boxShadow: '0 1px 0 var(--panel-border)' }}>

        {/* Brand */}
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg flex items-center justify-center border"
            style={{
              background: 'var(--accent-subtle)',
              color: 'var(--accent)',
              borderColor: 'var(--accent-ring)',
            }}>
            <Building2 className="w-4 h-4" />
          </div>
          <span className="font-extrabold text-lg tracking-tight" style={{ color: 'var(--foreground)' }}>
            Civil Work <span className="text-gradient-accent">Estimation</span>
          </span>
        </div>

        {/* Right actions */}
        <div className="flex items-center gap-4">
          <ThemeToggle />
          <div className="h-5 w-px" style={{ background: 'var(--panel-border)' }} />

          <div className="flex items-center gap-3">
            <div className="text-right select-none">
              <div className="text-xs font-semibold leading-none" style={{ color: 'var(--foreground)' }}>
                {user?.email}
              </div>
              <div className="text-[10px] mt-0.5 font-medium text-gradient-accent">
                Civil Engineer
              </div>
            </div>
            <button
              onClick={() => logout()}
              className="text-xs font-bold px-3 py-1.5 rounded-lg cursor-pointer transition-all border"
              style={{
                color: 'var(--muted)',
                borderColor: 'var(--panel-border)',
                background: 'transparent',
              }}
              onMouseOver={e => {
                e.currentTarget.style.color = '#ff453a';
                e.currentTarget.style.borderColor = 'rgba(255,69,58,0.3)';
                e.currentTarget.style.background = 'rgba(255,69,58,0.06)';
              }}
              onMouseOut={e => {
                e.currentTarget.style.color = 'var(--muted)';
                e.currentTarget.style.borderColor = 'var(--panel-border)';
                e.currentTarget.style.background = 'transparent';
              }}
            >
              Sign Out
            </button>
          </div>
        </div>
      </header>

      {/* Main Workspace Frame */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Sidebar */}
        <Sidebar 
          activeSessionId={activeSessionId}
          onSelectSession={handleSelectSession}
          onNewSessionCreated={handleNewSessionCreated}
          sessionsList={sessionsList}
          setSessionsList={setSessionsList}
          onSelectFile={handleSelectFile}
          activeFile={activeFile}
        />

        {/* Right Workspace Panel: Dynamic Dual-Panel Split */}
        <div className="flex-1 flex overflow-hidden bg-bg">
          {activeSessionId ? (
            <>
              {/* Left Column: AI Swarm Copilot & Logs */}
              <CopilotPanel 
                sessionId={activeSessionId}
                sessionState={sessionState}
                refreshSession={() => activeSessionId && loadSessionState(activeSessionId)}
                progress={progress}
                status={status}
                step={step}
              />
              
              {/* Right Column: File Viewer OR TabEditor */}
              <div className="flex-1 flex flex-col overflow-hidden">
                {activeFile && activeFile.sessionId === activeSessionId && activeFile.fileType !== 'parameters' ? (
                  <FileViewerPanel
                    sessionId={activeFile.sessionId}
                    fileType={activeFile.fileType as 'plan' | 'excel' | 'readme'}
                    sessionName={sessionsList.find(s => s.id === activeFile.sessionId)?.filename || ''}
                  />
                ) : (
                  <TabEditor 
                    activeTab={activeTab}
                    setActiveTab={setActiveTab}
                    sessionId={activeSessionId}
                    sessionState={sessionState}
                    refreshSession={() => activeSessionId && loadSessionState(activeSessionId)}
                    displayName={sessionsList.find(s => s.id === activeSessionId)?.filename}
                  />
                )}
              </div>
            </>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center p-8 text-center bg-bg relative overflow-hidden font-sans select-none animate-fade-in">
              
              {/* Background glowing orbs */}
              <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-gradient-accent rounded-full opacity-[0.03] blur-[100px] pointer-events-none" />
              <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[300px] h-[300px] bg-gradient-accent rounded-full opacity-[0.05] blur-[60px] animate-pulse pointer-events-none" />

              {/* Glassmorphism Card */}
              <div className="relative z-10 flex flex-col items-center p-12 rounded-3xl backdrop-blur-xl shadow-2xl transition-all duration-300 hover:shadow-xl hover:shadow-[#8b5cf6]/10 hover:-translate-y-1"
                style={{ background: 'var(--panel)', border: '1px solid var(--panel-border)' }}>
                
                {/* Stunning Icon Composition */}
                <div className="relative mb-8 flex items-center justify-center">
                  <div className="absolute inset-0 bg-gradient-accent opacity-20 blur-2xl rounded-full animate-pulse" />
                  <div className="relative w-24 h-24 rounded-2xl bg-gradient-accent p-[1px] shadow-2xl shadow-[#FF512F]/20">
                    <div className="w-full h-full rounded-2xl flex items-center justify-center" style={{ background: 'var(--background)' }}>
                      <Layers className="w-10 h-10 animate-pulse" style={{ color: 'var(--foreground)' }} />
                    </div>
                  </div>
                  <div className="absolute -top-3 -right-3 w-8 h-8 rounded-full bg-gradient-accent flex items-center justify-center shadow-lg shadow-[#8b5cf6]/30 transition-transform hover:scale-110">
                    <Sparkles className="w-4 h-4 text-white" />
                  </div>
                </div>

                <h1 className="text-3xl font-black mb-3 tracking-tight text-gradient-accent">
                  Ready for AI Estimation
                </h1>
                <p className="max-w-[420px] text-[13px] leading-relaxed mb-8 text-center" style={{ color: 'var(--muted)' }}>
                  Your workspace is clear. Select an existing estimation from the sidebar or start a new project to let the AI Swarm do the heavy lifting.
                </p>
                <button 
                  onClick={() => window.dispatchEvent(new Event('open-new-project'))}
                  className="btn-accent px-8 py-3.5 rounded-2xl font-bold text-sm shadow-xl shadow-[#8b5cf6]/20 transition-all hover:-translate-y-1 hover:shadow-[#8b5cf6]/30 flex items-center gap-2">
                  <Sparkles className="w-4 h-4" />
                  New Project
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
