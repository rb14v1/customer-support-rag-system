import React from 'react';
import ReactMarkdown from 'react-markdown';
import { getDocumentSourceUrl } from '../services/api';

/**
 * Message component rendering user or assistant chat bubbles, timestamps, and retrieved sources.
 */
export default function Message({ message }) {
  const isUser = message.sender === 'user';

  const formatRelevance = (rel) => {
    try {
      if (typeof rel === 'number') {
        const pct = rel <= 1 ? Math.round(rel * 100) : Math.round(rel);
        return `${pct}%`;
      }
      return 'N/A';
    } catch (err) {
      console.error('[Message] Error formatting relevance:', err);
      return 'N/A';
    }
  };

  const truncateExcerpt = (text, maxLength = 140) => {
    try {
      if (!text) return '';
      const cleanText = text.replace(/\s+/g, ' ').trim();
      if (cleanText.length <= maxLength) return cleanText;
      return cleanText.slice(0, maxLength).trim() + '...';
    } catch (err) {
      console.error('[Message] Error truncating excerpt:', err);
      return text || '';
    }
  };

  return (
    <div className={`message-row ${isUser ? 'user-row' : 'assistant-row'}`}>
      {!isUser && (
        <div className="avatar assistant-avatar" aria-label="SupportGen Avatar" title="SupportGen">
          <svg width="22" height="22" viewBox="0 0 100 100" fill="none">
            {/* Background Documents & Magnifying Glass */}
            <rect x="56" y="16" width="22" height="28" rx="4" fill="currentColor" opacity="0.5"/>
            <rect x="48" y="22" width="22" height="28" rx="4" fill="currentColor"/>
            <line x1="53" y1="28" x2="65" y2="28" stroke="#ffffff" strokeWidth="2" strokeLinecap="round"/>
            <line x1="53" y1="34" x2="63" y2="34" stroke="#ffffff" strokeWidth="2" strokeLinecap="round"/>
            <circle cx="65" cy="41" r="7.5" fill="#ffffff" stroke="currentColor" strokeWidth="3"/>
            <line x1="71" y1="46.5" x2="79" y2="54.5" stroke="currentColor" strokeWidth="3.5" strokeLinecap="round"/>
            {/* Foreground Headset & Chat Bubble */}
            <path d="M 20 54 A 23 23 0 0 1 64 54" fill="none" stroke="currentColor" strokeWidth="6" strokeLinecap="round"/>
            <rect x="15" y="45" width="10" height="19" rx="5" fill="currentColor"/>
            <rect x="59" y="45" width="10" height="19" rx="5" fill="currentColor"/>
            <path d="M 42 34 C 53.0457 34 62 42.0589 62 52 C 62 61.9411 53.0457 70 42 70 C 39.2 70 36.5 69.5 34 68.6 L 24 75 L 26.5 64.8 C 23.7 61.8 22 57.1 22 52 C 22 42.0589 30.9543 34 42 34 Z" fill="#ffffff" stroke="currentColor" strokeWidth="5" strokeLinejoin="round"/>
            <circle cx="33" cy="52" r="3" fill="currentColor"/>
            <circle cx="42" cy="52" r="3" fill="currentColor"/>
            <circle cx="51" cy="52" r="3" fill="currentColor"/>
            <path d="M 64 60 C 64 74, 49 76, 44 74" fill="none" stroke="currentColor" strokeWidth="5" strokeLinecap="round"/>
            <circle cx="42" cy="74" r="5" fill="currentColor"/>
          </svg>
        </div>
      )}

      <div className={`message-bubble ${isUser ? 'user-bubble' : 'assistant-bubble'}`}>
        <div className="message-header">
          <span className="sender-name">{isUser ? 'You' : 'SupportGen'}</span>
          {message.timestamp && <span className="message-time">{message.timestamp}</span>}
        </div>

        <div className="message-text">
          <ReactMarkdown
            components={{
              a: ({ _node, ...props }) => (
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
