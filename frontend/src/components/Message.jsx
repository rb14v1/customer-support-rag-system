import React from 'react';

/**
 * Message component rendering user or assistant chat bubbles, timestamps, and retrieved sources.
 */
export default function Message({ message }) {
  const isUser = message.sender === 'user';

  const formatRelevance = (rel) => {
    if (typeof rel === 'number') {
      const pct = rel <= 1 ? Math.round(rel * 100) : Math.round(rel);
      return `${pct}%`;
    }
    return 'N/A';
  };

  return (
    <div className={`message-row ${isUser ? 'user-row' : 'assistant-row'}`}>
      {!isUser && (
        <div className="avatar assistant-avatar" aria-label="AI Assistant Avatar" title="AI Support">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2zm0 18a8 8 0 1 1 8-8 8 8 0 0 1-8 8z"/>
            <path d="M12 6a4 4 0 0 0-4 4c0 2 2 3 4 5 2-2 4-3 4-5a4 4 0 0 0-4-4z"/>
          </svg>
        </div>
      )}

      <div className={`message-bubble ${isUser ? 'user-bubble' : 'assistant-bubble'}`}>
        <div className="message-header">
          <span className="sender-name">{isUser ? 'You' : 'Customer Support Assistant'}</span>
          {message.timestamp && <span className="message-time">{message.timestamp}</span>}
        </div>

        <div className="message-text">
          {message.text.split('\n').map((paragraph, idx) => (
            <p key={idx}>{paragraph}</p>
          ))}
        </div>

        {/* Display Retrieved Context Sources */}
        {!isUser && message.sources && message.sources.length > 0 && (
          <div className="sources-container">
            <div className="sources-header">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                <polyline points="14 2 14 8 20 8"/>
                <line x1="16" y1="13" x2="8" y2="13"/>
                <line x1="16" y1="17" x2="8" y2="17"/>
              </svg>
              <span>Sources</span>
            </div>

            <div className="sources-list">
              {message.sources.map((src, index) => (
                <div key={index} className="source-card">
                  <div className="source-doc-name" title={src.document}>
                    {src.document}
                  </div>
                  <div className="source-meta">
                    <span className="source-page">Page {src.page}</span>
                    <span className="source-relevance">Relevance: {formatRelevance(src.relevance)}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {isUser && (
        <div className="avatar user-avatar" title="You">
          <span>Y</span>
        </div>
      )}
    </div>
  );
}
