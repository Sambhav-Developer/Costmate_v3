const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

function getHeaders(extraHeaders: Record<string, string> = {}) {
  const headers: Record<string, string> = {
    ...extraHeaders,
  };
  
  if (typeof window !== 'undefined') {
    const token = localStorage.getItem('costmate_token');
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
  }
  
  return headers;
}

import { encryptPayload, generateEncryptionHeaders, decryptPayload } from './crypto';

export async function request(path: string, options: RequestInit = {}) {
  const url = `${BASE_URL}${path}`;
  let finalOptions = { ...options };
  let extraHeaders = (options.headers as Record<string, string>) || {};
  let currentAesKey: string | null = null;

  // Skip encryption for fetching the public key itself!
  const isPublicKeyReq = path === '/api/auth/public-key';

  if (!isPublicKeyReq) {
    if (options.body && typeof options.body === 'string' && extraHeaders['Content-Type'] === 'application/json') {
      try {
        const parsedBody = JSON.parse(options.body);
        const encrypted = await encryptPayload(parsedBody);
        finalOptions.body = JSON.stringify({
          rsa_encrypted_aes_key: encrypted.rsa_encrypted_aes_key,
          aes_encrypted_payload: encrypted.aes_encrypted_payload
        });
        currentAesKey = encrypted.raw_aes_key;
      } catch (e) {
        console.warn("Payload encryption failed or skipped:", e);
      }
    } else if (!options.body || typeof options.body !== 'string') {
      // For GET requests or requests without a JSON body, we send an AES key in the headers
      // so the backend can encrypt the response!
      try {
        const encHeaders = await generateEncryptionHeaders();
        extraHeaders['x-encryption-key'] = encHeaders.rsa_encrypted_aes_key;
        currentAesKey = encHeaders.raw_aes_key;
      } catch (e) {
        console.warn("Failed to generate encryption headers:", e);
      }
    }
  }

  const response = await fetch(url, {
    ...finalOptions,
    headers: getHeaders(extraHeaders),
  });

  if (response.status === 401) {
    if (typeof window !== 'undefined') {
      localStorage.removeItem('costmate_token');
      window.dispatchEvent(new Event('costmate-auth-changed'));
    }
  }

  if (!response.ok) {
    let errorMessage = 'Something went wrong';
    try {
      let errData = await response.json();
      if (errData && typeof errData === 'object' && 'encrypted_response' in errData && currentAesKey) {
        try {
          errData = decryptPayload(errData.encrypted_response, currentAesKey);
        } catch (e) {
          console.error("Failed to decrypt error response payload:", e);
        }
      }
      errorMessage = (typeof errData?.detail === 'string' ? errData.detail : (Array.isArray(errData?.detail) ? JSON.stringify(errData.detail) : errData?.detail)) || errorMessage;
    } catch {
      // Ignored
    }
    throw new Error(errorMessage);
  }

  const originalJson = response.json.bind(response);
  response.json = async () => {
    const rawData = await originalJson();
    
    let processedData = rawData;
    // Decrypt if it's an encrypted response!
    if (rawData && typeof rawData === 'object' && 'encrypted_response' in rawData && currentAesKey) {
      try {
        processedData = decryptPayload(rawData.encrypted_response, currentAesKey);
      } catch (e) {
        console.error("Failed to decrypt response payload:", e);
      }
    }

    if (processedData && typeof processedData === 'object' && 'success' in processedData && 'data' in processedData) {
      return processedData.data;
    }
    return processedData;
  };

  return response;
}

export const api = {
  baseUrl: BASE_URL,
  
  async signup(email: string, password: string) {
    const res = await request('/api/auth/signup', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    return res.json();
  },

  async verifyOtp(email: string, otp: string) {
    const res = await request('/api/auth/verify-otp', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, otp }),
    });
    const data = await res.json();
    if (typeof window !== 'undefined') {
      localStorage.setItem('costmate_token', data.access_token);
      window.dispatchEvent(new Event('costmate-auth-changed'));
    }
    return data;
  },

  async login(email: string, password: string) {
    const res = await request('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    const data = await res.json();
    if (typeof window !== 'undefined') {
      localStorage.setItem('costmate_token', data.access_token);
      window.dispatchEvent(new Event('costmate-auth-changed'));
    }
    return data;
  },

  async loginWithGoogle(idToken: string) {
    const res = await request('/api/auth/google', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id_token: idToken }),
    });
    const data = await res.json();
    if (typeof window !== 'undefined') {
      localStorage.setItem('costmate_token', data.access_token);
      window.dispatchEvent(new Event('costmate-auth-changed'));
    }
    return data;
  },

  logout() {
    if (typeof window !== 'undefined') {
      // Best effort notify backend
      request('/api/auth/logout', { method: 'POST' }).catch(() => {});
      localStorage.removeItem('costmate_token');
      window.dispatchEvent(new Event('costmate-auth-changed'));
    }
  },

  async me() {
    const res = await request('/api/auth/me');
    return res.json();
  },

  async upload(file: File) {
    const formData = new FormData();
    formData.append('file', file);
    const res = await request('/api/upload', {
      method: 'POST',
      body: formData,
    });
    return res.json();
  },

  async createDraftSession(projectName: string) {
    const res = await request('/api/session/draft', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_name: projectName }),
    });
    return res.json();
  },

  async uploadDraftFile(draftId: string, file: File) {
    const formData = new FormData();
    formData.append('file', file);
    const res = await request(`/api/session/draft/${draftId}/upload`, {
      method: 'POST',
      body: formData,
    });
    return res.json();
  },

  async uploadDraftSchedule(draftId: string, file: File) {
    const formData = new FormData();
    formData.append('file', file);
    const res = await request(`/api/session/draft/${draftId}/schedule`, {
      method: 'POST',
      body: formData,
    });
    return res.json();
  },

  async cropDraftSchedule(draftId: string, file: File, x0: number, y0: number, x1: number, y1: number, pageNum: number) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('x0', x0.toString());
    formData.append('y0', y0.toString());
    formData.append('x1', x1.toString());
    formData.append('y1', y1.toString());
    formData.append('page_num', pageNum.toString());
    const res = await request(`/api/session/draft/${draftId}/crop-schedule`, {
      method: 'POST',
      body: formData,
    });
    return res.json();
  },

  async uploadDraftSpecification(draftId: string, file: File) {
    const formData = new FormData();
    formData.append('file', file);
    const res = await request(`/api/session/draft/${draftId}/specification`, {
      method: 'POST',
      body: formData,
    });
    return res.json();
  },

  async quickScanDraft(draftId: string) {
    const res = await request(`/api/session/draft/${draftId}/quick-scan`, {
      method: 'POST'
    });
    return res.json();
  },

  async startDraftTakeoff(draftId: string, intakeData?: any) {
    const res = await request(`/api/session/draft/${draftId}/complete`, {
      method: 'POST',
      headers: intakeData ? { 'Content-Type': 'application/json' } : undefined,
      body: intakeData ? JSON.stringify({ intake_data: intakeData }) : undefined,
    });
    return res.json();
  },

  async sendChatMessage(sessionId: string, message: string) {
    const res = await request(`/api/chat/${sessionId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message }),
    });
    return res.json();
  },

  async getSession(sessionId: string) {
    const res = await request(`/api/session/${sessionId}`);
    return res.json();
  },

  async listSessions() {
    const res = await request('/api/session');
    return res.json();
  },

  async deleteSession(sessionId: string) {
    const res = await request(`/api/session/${sessionId}`, {
      method: 'DELETE',
    });
    return res.json();
  },

  async submitQA(sessionId: string, verifiedQA: any) {
    const res = await request(`/api/qa/${sessionId}/submit`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(verifiedQA),
    });
    return res.json();
  },

  downloadUrl(sessionId: string) {
    const token = typeof window !== 'undefined' ? localStorage.getItem('costmate_token') : '';
    return `${BASE_URL}/api/download/${sessionId}?token=${token || ''}&t=${Date.now()}`;
  },

  downloadPlanUrl(sessionId: string) {
    const token = typeof window !== 'undefined' ? localStorage.getItem('costmate_token') : '';
    return `${BASE_URL}/api/download/${sessionId}/plan?token=${token || ''}&t=${Date.now()}`;
  },


  planImageUrl(sessionId: string) {
    const token = typeof window !== 'undefined' ? localStorage.getItem('costmate_token') : '';
    return `${BASE_URL}/api/files/${sessionId}/plan?token=${token || ''}`;
  },

  planPageUrl(sessionId: string, pageIndex: number) {
    const token = typeof window !== 'undefined' ? localStorage.getItem('costmate_token') : '';
    return `${BASE_URL}/api/files/${sessionId}/plan/${pageIndex}?token=${token || ''}`;
  },

  async getPlanPageCount(sessionId: string): Promise<number> {
    const res = await request(`/api/files/${sessionId}/plan/pages`);
    const data = await res.json();
    return data.page_count || 1;
  },

  async getSessionReadme(sessionId: string) {
    const res = await request(`/api/files/${sessionId}/readme`);
    return res.json();
  },

  statusEventSource(sessionId: string) {
    const token = typeof window !== 'undefined' ? localStorage.getItem('costmate_token') : '';
    return new EventSource(`${BASE_URL}/api/status/${sessionId}/stream?token=${token || ''}`);
  }
};
