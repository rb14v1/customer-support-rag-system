import React, { useState, useRef, useEffect } from 'react';
import Message from './Message';
import { sendChatMessage } from '../services/api';

const EXAMPLE_QUESTIONS = [
  "What is the return policy?",
  "How long does shipping take?",
  "What does the warranty cover?",
  "How do I manage my account?"
];

export default function Chat({ onHealthCheck }) {
  const [messages, setMessages] = useState([]);
  const [inputQuestion, setInputQuestion] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  const getCurrentTime = () => {
    return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  const handleSend = async (textToSend = null) => {
    const questionText = typeof textToSend === 'string' ? textToSend : inputQuestion;
    const trimmedQuestion = questionText.trim();

    if (!trimmedQuestion || isLoading) return;

    setError(null);

    // 1. Append user message
    const userMsg = {
      id: Date.now().toString(),
      sender: 'user',
      text: trimmedQuestion,
      timestamp: getCurrentTime(),
    };

    // 2. Build conversation history from existing messages
    const conversationHistory = messages.map((m) => ({
      role: m.sender === 'user' ? 'user' : 'assistant',
      content: m.text,
    }));

    setMessages((prev) => [...prev, userMsg]);
    if (!textToSend) setInputQuestion('');
    setIsLoading(true);

    try {
      // 3. Call Django API POST /api/chat/ with question + conversationHistory
      const data = await sendChatMessage(trimmedQuestion, conversationHistory);

      // 4. Append assistant response
      const assistantMsg = {
        id: (Date.now() + 1).toString(),
        sender: 'assistant',
        text: data.answer || 'No response returned from assistant.',
        sources: data.sources || [],
        timestamp: getCurrentTime(),
      };

      setMessages((prev) => [...prev, assistantMsg]);

    } catch (err) {
      setError(err.message || 'An unexpected error occurred while communicating with the backend.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleExampleClick = (question) => {
    setInputQuestion(question);
    handleSend(question);
  };

  return (
    <div className="chat-container">
      {/* Error Alert Notification */}
      {error && (
        <div className="error-alert" role="alert">
          <div className="error-alert-content">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10"/>
              <line x1="12" y1="8" x2="12" y2="12"/>
              <line x1="12" y1="16" x2="12.01" y2="16"/>
            </svg>
            <span>{error}</span>
          </div>
          <button className="error-dismiss-btn" onClick={() => setError(null)} title="Dismiss">
            &times;
          </button>
        </div>
      )}

      {/* Main Chat Area */}
      <div className="chat-messages-area">
        {messages.length === 0 ? (
          <div className="welcome-container">
            <div className="welcome-badge">
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
              </svg>
            </div>
            <h2>Welcome to Customer Support Assistant</h2>
            <p>Ask any question regarding policies, warranties, shipping, product manuals, or account management.</p>

            <div className="examples-section">
              <span className="examples-label">Try asking an example question:</span>
              <div className="example-chips-grid">
                {EXAMPLE_QUESTIONS.map((q, idx) => (
                  <button
                    key={idx}
                    className="example-chip"
                    onClick={() => handleExampleClick(q)}
                    disabled={isLoading}
                  >
                    <span>{q}</span>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <line x1="5" y1="12" x2="19" y2="12"/>
                      <polyline points="12 5 19 12 12 19"/>
                    </svg>
                  </button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <div className="messages-list">
            {messages.map((msg) => (
              <Message key={msg.id} message={msg} />
            ))}

            {/* Typing / Loading Indicator */}
            {isLoading && (
              <div className="message-row assistant-row">
                <div className="avatar assistant-avatar" title="AI Support">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="12" cy="12" r="10"/>
                  </svg>
                </div>
                <div className="message-bubble assistant-bubble typing-bubble">
                  <div className="typing-indicator">
                    <span></span>
                    <span></span>
                    <span></span>
                  </div>
                  <span className="typing-text">Analyzing knowledge base & generating answer...</span>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Chat Input Bar */}
      <div className="chat-input-area">
        <div className="input-wrapper">
          <textarea
            ref={textareaRef}
            className="chat-textarea"
            rows="1"
            placeholder="Ask a customer support question... (Enter to send, Shift+Enter for new line)"
            value={inputQuestion}
            onChange={(e) => setInputQuestion(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isLoading}
          />
          <button
            className="send-button"
            onClick={() => handleSend()}
            disabled={isLoading || !inputQuestion.trim()}
            title="Send Message"
            aria-label="Send Message"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="22" y1="2" x2="11" y2="13"/>
              <polygon points="22 2 15 22 11 13 2 9 22 2"/>
            </svg>
          </button>
        </div>
        <div className="input-footer">
          <span>AI Support grounded on enterprise knowledge base</span>
        </div>
      </div>
    </div>
  );
}
