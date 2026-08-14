import React from 'react';
import ReactMarkdown from 'react-markdown';
import { getDocumentSourceUrl } from '../services/api';

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

  const truncateExcerpt = (text, maxLength = 140) => {
    if (!text) return '';
    const cleanText = text.replace(/\s+/g, ' ').trim();
    if (cleanText.length <= maxLength) return cleanText;
    return cleanText.slice(0, maxLength).trim() + '...';
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
          <ReactMarkdown
            components={{
              a: ({ node, ...props }) => (
                <a target="_blank" rel="noopener noreferrer" {...props} />
              ),
            }}
          >
            {message.text}
          </ReactMarkdown>
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
              {message.sources.map((src, index) => {
                const sourceUrl = src.url ? (src.url.startsWith('http') ? src.url : `${import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'}${src.url}`) : getDocumentSourceUrl(src.document, src.page);
                const excerpt = truncateExcerpt(src.text);
                return (
                  <div key={index} className="source-card">
                    <div className="source-card-header">
                      <span className="source-icon">📄</span>
                      <span className="source-doc-name" title={src.document}>
                        {src.document}
                      </span>
                    </div>
                    <div className="source-meta">
                      <span className="source-page">Page {src.page}</span>
                      <span className="source-relevance">Relevance: {formatRelevance(src.relevance)}</span>
                    </div>
                    {excerpt && (
                      <div className="source-excerpt" title={src.text}>
                        "{excerpt}"
                      </div>
                    )}
                    <a
                      href={sourceUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="view-source-btn"
                      title={`Open ${src.document} at page ${src.page}`}
                    >
                      View source ↗
                    </a>
                  </div>
                );
              })}
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
