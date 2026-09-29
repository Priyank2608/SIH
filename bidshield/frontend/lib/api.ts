const API_URL = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/+$/, '');
export const API_BASE = API_URL.endsWith('/api/v1') ? API_URL : `${API_URL}/api/v1`;

export function getToken(): string | null {
  if (typeof window === 'undefined') return null;
  return sessionStorage.getItem('bidshield_token');
}

export function setToken(token: string) {
  if (typeof window !== 'undefined') {
    sessionStorage.setItem('bidshield_token', token);
  }
}

export function clearToken() {
  if (typeof window !== 'undefined') {
    sessionStorage.removeItem('bidshield_token');
    sessionStorage.removeItem('bidshield_user');
  }
}

export function getCurrentUser() {
  if (typeof window === 'undefined') return null;
  const user = sessionStorage.getItem('bidshield_user');
  if (!user) return null;
  try { return JSON.parse(user); } catch { clearToken(); return null; }
}

export async function api(endpoint: string, options: RequestInit = {}) {
  const token = getToken();
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string> || {}),
  };

  if (!(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
  }

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  });

  if (res.status === 401) {
    clearToken();
    if (typeof window !== 'undefined' && !window.location.pathname.includes('/login')) {
      window.location.replace('/login?expired=1');
    }
  }

  if (!res.ok) {
    let errMessage = 'API request failed';
    try {
      const errData = await res.json();
      errMessage = errData.detail || errMessage;
    } catch {
      errMessage = res.statusText || errMessage;
    }
    throw new Error(errMessage);
  }

  return res.json();
}

export async function downloadFile(url: string, defaultFilename: string) {
  const token = getToken();
  const res = await fetch(url.startsWith('http') ? url : `${API_BASE}${url}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });

  if (!res.ok) throw new Error('File download failed');
  const blob = await res.blob();
  const blobUrl = window.URL.createObjectURL(blob);
  startBlobDownload(blobUrl, defaultFilename);
}

export function startBlobDownload(blobUrl: string, defaultFilename: string) {
  const a = document.createElement('a');
  a.href = blobUrl;
  a.download = defaultFilename;
  a.tabIndex = -1;
  a.setAttribute('aria-hidden', 'true');
  a.style.position = 'fixed';
  a.style.left = '-10000px';
  document.body.appendChild(a);
  a.click();
  // Keep the download anchor and blob alive while the browser streams the file.
  window.setTimeout(() => {
    a.remove();
    window.URL.revokeObjectURL(blobUrl);
  }, 60_000);
}

export async function recordReportDownload(url: string) {
  const token = getToken();
  const res = await fetch(url.startsWith('http') ? url : `${API_BASE}${url}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    cache: 'no-store',
  });
  if (!res.ok) throw new Error('Unable to record report download');
  await res.body?.cancel();
}

export async function fetchFileBlob(url: string): Promise<Blob> {
  const token = getToken();
  const res = await fetch(url.startsWith('http') ? url : `${API_BASE}${url}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    cache: 'no-store',
  });
  if (!res.ok) {
    let message = 'Unable to open this report';
    try { message = (await res.json()).detail || message; } catch { /* Keep a safe message. */ }
    throw new Error(message);
  }
  const blob = await res.blob();
  if (blob.type !== 'application/pdf') throw new Error('The server did not return a PDF report');
  return blob;
}
