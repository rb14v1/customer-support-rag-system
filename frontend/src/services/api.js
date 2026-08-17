/**
 * Centralized API service module for communicating with the Django backend.
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

/**
 * Generic fetch wrapper with centralized error handling.
 */
async function request(endpoint, options = {}) {
  console.log(`[API] Starting request: ${options.method || 'GET'} ${endpoint}`);
  const url = `${API_BASE_URL}${endpoint}`;
  const defaultHeaders = {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
  };

  const config = {
    ...options,
    headers: {
      ...defaultHeaders,
      ...options.headers,
    },
  };

  try {
    const response = await fetch(url, config);

    if (!response.ok) {
      let errorMessage = `HTTP Error ${response.status}`;
      try {
        const errorData = await response.json();
        if (errorData.detail) {
          errorMessage = errorData.detail;
        } else if (errorData.error) {
          errorMessage = errorData.error;
        } else if (errorData.question) {
          errorMessage = Array.isArray(errorData.question) ? errorData.question.join(', ') : errorData.question;
        }
      } catch {
        // Fall back to HTTP status message if JSON parsing fails
      }
      throw new Error(errorMessage);
    }

    const result = await response.json();
    console.log(`[API] Finished request: ${options.method || 'GET'} ${endpoint}`);
    return result;
  } catch (error) {
    console.error(`[API Request Error] ${options.method || 'GET'} ${url}:`, error.message);
    if (error.name === 'TypeError' || error.message.includes('Failed to fetch') || error.message.includes('NetworkError')) {
      throw new Error('Unable to connect to the customer support service. Please ensure the Django backend is running at ' + API_BASE_URL);
    }
    throw error;
  }
}

/**
 * Fetch health status of the RAG system and backend.
 * GET /api/health/
 */
export async function getHealth() {
  console.log('[API] Starting getHealth');
  try {
    const res = await request('/api/health/');
    console.log('[API] Finished getHealth');
    return res;
  } catch (err) {
    console.error('[API] Health check failed:', err.message);
    throw err;
  }
}

/**
 * Fetch list of ingested documents and chunk statistics.
 * GET /api/documents/
 */
export async function getDocuments() {
  console.log('[API] Starting getDocuments');
  try {
    const res = await request('/api/documents/');
    console.log('[API] Finished getDocuments');
    return res;
  } catch (err) {
    console.error('[API] Failed to fetch documents info:', err.message);
    throw err;
  }
}

/**
 * Trigger document ingestion on the backend.
 * POST /api/ingest/
 */
export async function ingestDocuments(dataDir = null) {
  console.log('[API] Starting ingestDocuments');
  try {
    console.log('[API] Triggering document ingestion', dataDir ? `for directory ${dataDir}` : '');
    const body = dataDir ? JSON.stringify({ data_dir: dataDir }) : JSON.stringify({});
    const res = await request('/api/ingest/', {
      method: 'POST',
      body,
    });
    console.log('[API] Finished ingestDocuments');
    return res;
  } catch (err) {
    console.error('[API] Document ingestion request failed:', err.message);
    throw err;
  }
}

export async function sendChatMessage(question, conversationHistory = []) {
  console.log('[API] Starting sendChatMessage');
  try {
    if (!question || !question.trim()) {
      throw new Error('Please provide a non-empty question.');
    }

    const payload = {
      question: question.trim(),
    };

    if (Array.isArray(conversationHistory) && conversationHistory.length > 0) {
      payload.conversation_history = conversationHistory;
    }

    console.log('[API] Sending chat query:', question.substring(0, 50));
    const res = await request('/api/chat/', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    console.log('[API] Finished sendChatMessage');
    return res;
  } catch (err) {
    console.error('[API] sendChatMessage failed:', err.message);
    throw err;
  }
}

/**
 * Constructs the source document URL for a cited PDF document opening to the specified page number.
 * GET /api/documents/<document_name>/source/?page=<page>#page=<page>
 */
export function getDocumentSourceUrl(documentName, page = 1) {
  console.log('[API] Starting getDocumentSourceUrl');
  try {
    const safeDocName = encodeURIComponent(documentName || '');
    const pageNum = parseInt(page, 10) || 1;
    const url = `${API_BASE_URL}/api/documents/${safeDocName}/source/?page=${pageNum}#page=${pageNum}`;
    console.log('[API] Finished getDocumentSourceUrl');
    return url;
  } catch (err) {
    console.error('[API] Failed to construct document source URL:', err.message);
    return '#';
  }
}
