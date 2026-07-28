import { useState, useEffect } from 'react';
import { api } from '../lib/api';

export function useAuth() {
  const [user, setUser] = useState<{ id: number; email: string } | null>(null);
  const [loading, setLoading] = useState(true);

  const checkAuth = async () => {
    const token = typeof window !== 'undefined' ? localStorage.getItem('costmate_token') : null;
    if (!token) {
      setUser(null);
      setLoading(false);
      return;
    }
    
    try {
      const userData = await api.me();
      setUser(userData);
    } catch (e) {
      setUser(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    checkAuth();
    
    const handleAuthChange = () => {
      setLoading(true);
      checkAuth();
    };

    if (typeof window !== 'undefined') {
      window.addEventListener('costmate-auth-changed', handleAuthChange);
    }
    
    return () => {
      if (typeof window !== 'undefined') {
        window.removeEventListener('costmate-auth-changed', handleAuthChange);
      }
    };
  }, []);

  return {
    user,
    loading,
    isLoggedIn: !!user,
    logout: () => api.logout(),
    refresh: checkAuth,
  };
}
