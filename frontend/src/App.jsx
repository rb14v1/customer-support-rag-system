import React, { useState, useEffect } from 'react';
import Chat from './components/Chat';
import { getHealth, getDocuments, ingestDocuments } from './services/api';

export default function App() {
  const [health, setHealth] = useState(null);
  const [documentsInfo, setDocumentsInfo] = useState(null);
  const [showDocsModal, setShowDocsModal] = useState(false);
  const [isIngesting, setIsIngesting] = useState(false);
  const [backendStatus, setBackendStatus] = useState('checking'); // 'connected', 'error', 'checking'

  const checkBackendHealth = async () => {
    console.log('[App] Starting checkBackendHealth...');
    try {
      setBackendStatus('checking');
      const data = await getHealth();
      setHealth(data);
      setBackendStatus('connected');
    } catch (err) {
      console.warn('[App] Backend health check failed:', err.message);
      setBackendStatus('error');
    } finally {
      console.log('[App] Finished checkBackendHealth');
    }
  };

  const fetchDocuments = async () => {
    console.log('[App] Starting fetchDocuments...');
    try {
      const data = await getDocuments();
      setDocumentsInfo(data);
    } catch (err) {
      console.warn('[App] Fetching documents info failed:', err.message);
    } finally {
      console.log('[App] Finished fetchDocuments');
    }
  };

  useEffect(() => {
    console.log('[App] Starting mount useEffect...');
    checkBackendHealth();
    console.log('[App] Finished mount useEffect');
  }, []);

  const handleOpenDocs = async () => {
    console.log('[App] Starting handleOpenDocs...');
    try {
      setShowDocsModal(true);
      await fetchDocuments();
    } catch (err) {
      console.error('[App] Error opening docs modal:', err.message);
    } finally {
      console.log('[App] Finished handleOpenDocs');
    }
  };

  const handleTriggerIngest = async () => {
    console.log('[App] Starting handleTriggerIngest...');
    try {
      console.log('[App] Triggering re-ingestion from UI');
      setIsIngesting(true);
      await ingestDocuments();
      await fetchDocuments();
      await checkBackendHealth();
    } catch (err) {
      console.error('[App] Ingestion failed:', err.message);
      alert('Ingestion error: ' + err.message);
    } finally {
      setIsIngesting(false);
      console.log('[App] Finished handleTriggerIngest');
    }
  };

  return (
    <div className="app-layout">
      {/* Microsoft Teams-inspired Header */}
      <header className="app-header">
        <div className="header-left">
          <div className="brand-logo" title="SupportGen AI">
            <svg width="34" height="34" viewBox="0 0 100 100" fill="none">
              {/* Background Documents & Magnifying Glass */}
              <rect x="56" y="14" width="24" height="30" rx="5" fill="#60A5FA" opacity="0.7"/>
              <rect x="48" y="20" width="24" height="30" rx="5" fill="#3B82F6"/>
              <line x1="54" y1="27" x2="66" y2="27" stroke="#FFFFFF" strokeWidth="2.5" strokeLinecap="round"/>
              <line x1="54" y1="34" x2="64" y2="34" stroke="#FFFFFF" strokeWidth="2.5" strokeLinecap="round"/>
              <circle cx="66" cy="42" r="7.5" fill="#FFFFFF" stroke="#1E3A8A" strokeWidth="2.5"/>
              <line x1="71.5" y1="47.5" x2="80" y2="56" stroke="#1E3A8A" strokeWidth="3" strokeLinecap="round"/>
              {/* Foreground Headset & Chat Bubble */}
              <path d="M 18 54 A 25 25 0 0 1 66 54" fill="none" stroke="#FFFFFF" strokeWidth="6.5" strokeLinecap="round"/>
              <rect x="13" y="44" width="11" height="20" rx="5.5" fill="#60A5FA"/>
              <rect x="60" y="44" width="11" height="20" rx="5.5" fill="#60A5FA"/>
              <path d="M 42 34 C 53.0457 34 62 42.0589 62 52 C 62 61.9411 53.0457 70 42 70 C 39.2 70 36.5 69.5 34 68.6 L 24 75 L 26.5 64.8 C 23.7 61.8 22 57.1 22 52 C 22 42.0589 30.9543 34 42 34 Z" fill="#FFFFFF" stroke="#1E3A8A" strokeWidth="4.5" strokeLinejoin="round"/>
              <circle cx="33" cy="52" r="3" fill="#1E3A8A"/>
              <circle cx="42" cy="52" r="3" fill="#1E3A8A"/>
              <circle cx="51" cy="52" r="3" fill="#1E3A8A"/>
              <path d="M 65 60 C 65 75, 49 77, 44 75" fill="none" stroke="#FFFFFF" strokeWidth="5.5" strokeLinecap="round"/>
              <circle cx="42" cy="75" r="5" fill="#60A5FA" stroke="#FFFFFF" strokeWidth="1.5"/>
            </svg>
          </div>
          <div className="brand-titles">
            <h1 className="header-title">SupportGen</h1>
            <div className="status-badge">
              <span className={`status-dot ${backendStatus}`}></span>
              <span className="status-text">
                {backendStatus === 'connected' && 'Enterprise Support Online'}
                {backendStatus === 'checking' && 'Connecting to SupportGen...'}
                {backendStatus === 'error' && 'Backend Offline'}
              </span>
            </div>
          </div>
        </div>

        <div className="header-right">
          <button className="header-btn" onClick={handleOpenDocs} title="View Knowledge Base Documents">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/>
              <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>
            </svg>
            <span>Knowledge Base</span>
          </button>
        </div>
      </header>

      {/* Main Container */}
      <main className="app-main">
        <Chat onHealthCheck={checkBackendHealth} />
      </main>

      {/* Knowledge Base Modal */}
      {showDocsModal && (
        <div className="modal-backdrop" onClick={() => setShowDocsModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Knowledge Base Documents</h3>
              <button className="modal-close" onClick={() => setShowDocsModal(false)}>&times;</button>
            </div>
            <div className="modal-body">
              {health && (
                <div className="health-summary-card">
                  <div className="summary-item">
                    <span className="summary-label">Provider</span>
                    <span className="summary-value">{health.vector_store_provider}</span>
                  </div>
                  <div className="summary-item">
                    <span className="summary-label">Total Documents</span>
                    <span className="summary-value">{health.documents_indexed}</span>
                  </div>
                  <div className="summary-item">
                    <span className="summary-label">Total Chunks</span>
                    <span className="summary-value">{health.chunks_indexed}</span>
                  </div>
                </div>
              )}

              <div className="doc-list-section">
                <h4>Ingested PDF Files ({documentsInfo?.documents?.length || 0})</h4>
                {documentsInfo?.documents?.length > 0 ? (
                  <ul className="doc-files-list">
                    {documentsInfo.documents.map((file, idx) => (
                      <li key={idx} className="doc-file-item">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                          <polyline points="14 2 14 8 20 8"/>
                        </svg>
                        <span>{file}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="empty-docs-msg">No documents loaded yet or backend offline.</p>
                )}
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn-secondary" onClick={handleTriggerIngest} disabled={isIngesting}>
                {isIngesting ? 'Ingesting PDFs...' : 'Re-ingest PDF Documents'}
              </button>
              <button className="btn-primary" onClick={() => setShowDocsModal(false)}>Close</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
