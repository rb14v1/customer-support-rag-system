import React, { useState, useRef, useEffect } from 'react';
import Message from './Message';
import { sendChatMessage } from '../services/api';

const EXAMPLE_QUESTIONS = [
  "What is the return policy?",
  "How long does shipping take?",
  "What does the warranty cover?",
  "How do I manage my account?"
];

export default function Chat({ _onHealthCheck }) {
  const [messages, setMessages] = useState([]);
  const [inputQuestion, setInputQuestion] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);

  const scrollToBottom = () => {
    console.log('[Chat] Starting scrollToBottom...');
    try {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    } catch (err) {
      console.error('[Chat] Error scrolling to bottom:', err);
    } finally {
      console.log('[Chat] Finished scrollToBottom');
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  const getCurrentTime = () => {
    console.log('[Chat] Starting getCurrentTime...');
    try {
      const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      console.log('[Chat] Finished getCurrentTime');
      return timeStr;
    } catch (err) {
      console.error('[Chat] Error formatting timestamp:', err);
      return '';
    }
  };

  const handleSend = async (textToSend = null) => {
    console.log('[Chat] Starting handleSend...');
    try {
      const questionText = typeof textToSend === 'string' ? textToSend : inputQuestion;
      const trimmedQuestion = questionText.trim();

      if (!trimmedQuestion || isLoading) return;

      console.log('[Chat] Sending question:', trimmedQuestion);
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
      console.error('[Chat] handleSend error:', err);
      setError(err.message || 'An unexpected error occurred while communicating with the backend.');
    } finally {
      setIsLoading(false);
      console.log('[Chat] Finished handleSend');
    }
  };

  const handleKeyDown = (e) => {
    console.log('[Chat] Starting handleKeyDown...');
    try {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    } catch (err) {
      console.error('[Chat] handleKeyDown error:', err);
    } finally {
      console.log('[Chat] Finished handleKeyDown');
    }
  };

  const handleExampleClick = (question) => {
    console.log('[Chat] Starting handleExampleClick...');
    try {
      console.log('[Chat] Example question clicked:', question);
      setInputQuestion(question);
      handleSend(question);
    } catch (err) {
      console.error('[Chat] handleExampleClick error:', err);
    } finally {
      console.log('[Chat] Finished handleExampleClick');
    }
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
              <svg width="40" height="40" viewBox="0 0 100 100" fill="none">
                {/* Background Documents & Magnifying Glass */}
                <rect x="56" y="16" width="22" height="28" rx="4" fill="currentColor" opacity="0.4"/>
                <rect x="48" y="22" width="22" height="28" rx="4" fill="currentColor"/>
                <line x1="53" y1="28" x2="65" y2="28" stroke="var(--bg-card, #ffffff)" strokeWidth="2" strokeLinecap="round"/>
                <line x1="53" y1="34" x2="63" y2="34" stroke="var(--bg-card, #ffffff)" strokeWidth="2" strokeLinecap="round"/>
                <circle cx="65" cy="41" r="7.5" fill="var(--bg-card, #ffffff)" stroke="currentColor" strokeWidth="3"/>
                <line x1="71" y1="46.5" x2="79" y2="54.5" stroke="currentColor" strokeWidth="3.5" strokeLinecap="round"/>
                {/* Foreground Headset & Chat Bubble */}
                <path d="M 20 54 A 23 23 0 0 1 64 54" fill="none" stroke="currentColor" strokeWidth="6" strokeLinecap="round"/>
                <rect x="15" y="45" width="10" height="19" rx="5" fill="currentColor"/>
                <rect x="59" y="45" width="10" height="19" rx="5" fill="currentColor"/>
                <path d="M 42 34 C 53.0457 34 62 42.0589 62 52 C 62 61.9411 53.0457 70 42 70 C 39.2 70 36.5 69.5 34 68.6 L 24 75 L 26.5 64.8 C 23.7 61.8 22 57.1 22 52 C 22 42.0589 30.9543 34 42 34 Z" fill="var(--bg-card, #ffffff)" stroke="currentColor" strokeWidth="5" strokeLinejoin="round"/>
                <circle cx="33" cy="52" r="3" fill="currentColor"/>
                <circle cx="42" cy="52" r="3" fill="currentColor"/>
                <circle cx="51" cy="52" r="3" fill="currentColor"/>
                <path d="M 64 60 C 64 74, 49 76, 44 74" fill="none" stroke="currentColor" strokeWidth="5" strokeLinecap="round"/>
                <circle cx="42" cy="74" r="5" fill="currentColor"/>
              </svg>
            </div>
            <h2>Welcome to SupportGen</h2>
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
            placeholder="Ask SupportGen a question... (Enter to send, Shift+Enter for new line)"
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
          <span>SupportGen AI grounded on enterprise knowledge base</span>
        </div>
      </div>
    </div>
  );
}
