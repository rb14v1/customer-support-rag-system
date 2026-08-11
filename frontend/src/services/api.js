/**
 * Centralized API service module for communicating with the Django backend.
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

/**
 * Generic fetch wrapper with centralized error handling.
 */
async function request(endpoint, options = {}) {
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
      } catch (e) {
        // Fall back to HTTP status message if JSON parsing fails
      }
      throw new Error(errorMessage);
    }

    return await response.json();
  } catch (error) {
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
  return request('/api/health/');
}

/**
 * Fetch list of ingested documents and chunk statistics.
 * GET /api/documents/
 */
export async function getDocuments() {
  return request('/api/documents/');
}

/**
 * Trigger document ingestion on the backend.
 * POST /api/ingest/
 */
export async function ingestDocuments(dataDir = null) {
  const body = dataDir ? JSON.stringify({ data_dir: dataDir }) : JSON.stringify({});
  return request('/api/ingest/', {
    method: 'POST',
    body,
  });
}

/**
 * Send customer question to primary chat endpoint.
 * POST /api/chat/
 * Payload: { "question": "..." }
 * Response: { "answer": "...", "sources": [...] }
 */
export async function sendChatMessage(question) {
  if (!question || !question.trim()) {
    throw new Error('Please provide a non-empty question.');
  }

  return request('/api/chat/', {
    method: 'POST',
    body: JSON.stringify({ question: question.trim() }),
  });
}

/**
 * Constructs the source document URL for a cited PDF document and page number.
 * GET /api/documents/<document_name>/source/?page=<page>#page=<page>
 */
export function getDocumentSourceUrl(documentName, page = 1) {
  const safeDocName = encodeURIComponent(documentName);
  const pageNum = parseInt(page, 10) || 1;
  return `${API_BASE_URL}/api/documents/${safeDocName}/source/?page=${pageNum}#page=${pageNum}`;
}
