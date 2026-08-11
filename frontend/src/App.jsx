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
    try {
      setBackendStatus('checking');
      const data = await getHealth();
      setHealth(data);
      setBackendStatus('connected');
    } catch (err) {
      setBackendStatus('error');
    }
  };

  const fetchDocuments = async () => {
    try {
      const data = await getDocuments();
      setDocumentsInfo(data);
    } catch (err) {
      // Handled silently
    }
  };

  useEffect(() => {
    checkBackendHealth();
  }, []);

  const handleOpenDocs = async () => {
    setShowDocsModal(true);
    await fetchDocuments();
  };

  const handleTriggerIngest = async () => {
    try {
      setIsIngesting(true);
      await ingestDocuments();
      await fetchDocuments();
      await checkBackendHealth();
    } catch (err) {
      alert('Ingestion error: ' + err.message);
    } finally {
      setIsIngesting(false);
    }
  };

  return (
    <div className="app-layout">
      {/* Microsoft Teams-inspired Header */}
      <header className="app-header">
        <div className="header-left">
          <div className="brand-logo">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
            </svg>
          </div>
          <div className="brand-titles">
            <h1 className="header-title">Customer Support Assistant</h1>
            <div className="status-badge">
              <span className={`status-dot ${backendStatus}`}></span>
              <span className="status-text">
                {backendStatus === 'connected' && 'AI Support Online'}
                {backendStatus === 'checking' && 'Checking Connection...'}
                {backendStatus === 'error' && 'Backend Disconnected'}
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
