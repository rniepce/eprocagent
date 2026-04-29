import { useState, useRef, useEffect, useCallback } from 'react';
import { Send, Scale, BookOpen, HelpCircle, Menu, FileText, Search } from 'lucide-react';
import ChatMessage from './ChatMessage';
import Sidebar from './Sidebar';
import type { Message, ModelInfo, DocumentInfo, SectionInfo, LanguageMode } from './types';
import './index.css';

const LANG_STORAGE_KEY = 'eproc.language_mode';
const SESSION_STORAGE_KEY = 'eproc.session_id';

function uuid(): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID();
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16);
  });
}

interface SessionSummary {
  session_id: string;
  title: string;
  msg_count: number;
  last_at?: string | null;
}

interface PersistedMessage {
  role: 'user' | 'assistant';
  content: string;
  sources?: any[] | null;
  structured?: any | null;
}

const API_BASE = import.meta.env.DEV ? 'http://localhost:8080' : '';

function generateId() {
  return Math.random().toString(36).substring(2, 15);
}

const WELCOME_SUGGESTIONS = [
  { icon: <FileText size={24} />, text: 'Como peticionar no eProc?' },
  { icon: <Search size={24} />, text: 'Como consultar um processo pelo número?' },
  { icon: <BookOpen size={24} />, text: 'Como configurar o certificado digital para acessar o eProc?' },
  { icon: <HelpCircle size={24} />, text: 'Quais os prazos para recurso no eProc?' },
];

export default function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [modelInfo, setModelInfo] = useState<ModelInfo | null>(null);
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [sections, setSections] = useState<SectionInfo[]>([]);
  const [selectedSections, setSelectedSections] = useState<string[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [languageMode, setLanguageMode] = useState<LanguageMode>(() => {
    const saved = localStorage.getItem(LANG_STORAGE_KEY);
    return saved === 'technical' ? 'technical' : 'simple';
  });
  const [sessionId, setSessionId] = useState<string>(() => {
    let id = localStorage.getItem(SESSION_STORAGE_KEY);
    if (!id) {
      id = uuid();
      localStorage.setItem(SESSION_STORAGE_KEY, id);
    }
    return id;
  });
  const [sessions, setSessions] = useState<SessionSummary[]>([]);

  const refreshSessions = useCallback(() => {
    fetch(`${API_BASE}/api/sessions`).then(r => r.json()).then(setSessions).catch(() => {});
  }, []);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    localStorage.setItem(LANG_STORAGE_KEY, languageMode);
  }, [languageMode]);

  // Scroll to bottom on new messages
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Fetch model info and documents on mount
  useEffect(() => {
    fetch(`${API_BASE}/api/model-info`).then(r => r.json()).then(setModelInfo).catch(() => {});
    fetch(`${API_BASE}/api/documents`).then(r => r.json()).then(setDocuments).catch(() => {});
    fetch(`${API_BASE}/api/sections`).then(r => r.json()).then(setSections).catch(() => {});
    refreshSessions();
  }, [refreshSessions]);

  const toggleSection = useCallback((s: string) => {
    setSelectedSections(prev =>
      prev.includes(s) ? prev.filter(x => x !== s) : [...prev, s]
    );
  }, []);
  const clearSections = useCallback(() => setSelectedSections([]), []);

  const sendMessage = useCallback(async (text: string) => {
    if (!text.trim() || isLoading) return;

    const userMsg: Message = {
      id: generateId(), role: 'user', content: text.trim(), timestamp: new Date(),
    };
    const assistantId = generateId();
    const assistantMsg: Message = {
      id: assistantId,
      role: 'assistant',
      content: '',
      status: 'searching',
      timestamp: new Date(),
    };
    setMessages(prev => [...prev, userMsg, assistantMsg]);
    setInput('');
    setIsLoading(true);

    const updateAssistant = (patch: Partial<Message>) => {
      setMessages(prev =>
        prev.map(m => (m.id === assistantId ? { ...m, ...patch } : m))
      );
    };

    try {
      const res = await fetch(`${API_BASE}/api/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: text.trim(),
          language_mode: languageMode,
          secoes: selectedSections,
          session_id: sessionId,
        }),
      });

      if (!res.ok || !res.body) {
        throw new Error(`HTTP ${res.status}`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        let idx;
        while ((idx = buffer.indexOf('\n\n')) >= 0) {
          const block = buffer.slice(0, idx);
          buffer = buffer.slice(idx + 2);

          let eventName = 'message';
          let dataLine = '';
          for (const line of block.split('\n')) {
            if (line.startsWith('event: ')) eventName = line.slice(7).trim();
            else if (line.startsWith('data: ')) dataLine += line.slice(6);
          }
          if (!dataLine) continue;
          let payload: any;
          try { payload = JSON.parse(dataLine); } catch { continue; }

          if (eventName === 'status') {
            updateAssistant({ status: payload.state });
          } else if (eventName === 'sources') {
            updateAssistant({ sources: payload.sources });
          } else if (eventName === 'answer') {
            updateAssistant({
              content: payload.answer,
              structured: payload.structured ?? undefined,
              status: undefined,
            });
          } else if (eventName === 'error') {
            updateAssistant({
              content: `⚠️ ${payload.detail ?? 'Erro interno.'}`,
              status: 'error',
            });
          }
        }
      }
    } catch (err) {
      updateAssistant({
        content: '⚠️ Erro de conexão com o servidor.',
        status: 'error',
      });
    } finally {
      setIsLoading(false);
      inputRef.current?.focus();
    }
    refreshSessions();
  }, [isLoading, languageMode, selectedSections, sessionId, refreshSessions]);

  const startNewConversation = useCallback(() => {
    const newId = uuid();
    localStorage.setItem(SESSION_STORAGE_KEY, newId);
    setSessionId(newId);
    setMessages([]);
    refreshSessions();
  }, [refreshSessions]);

  const deleteSession = useCallback(async (id: string) => {
    try {
      await fetch(`${API_BASE}/api/sessions/${encodeURIComponent(id)}`, {
        method: 'DELETE',
      });
      if (id === sessionId) {
        const newId = uuid();
        localStorage.setItem(SESSION_STORAGE_KEY, newId);
        setSessionId(newId);
        setMessages([]);
      }
      refreshSessions();
    } catch {
      /* silent */
    }
  }, [sessionId, refreshSessions]);

  const loadSession = useCallback(async (id: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/sessions/${encodeURIComponent(id)}`);
      const rows: PersistedMessage[] = await res.json();
      const restored: Message[] = rows.map((m, i) => ({
        id: `${id}-${i}`,
        role: m.role,
        content: m.content,
        structured: m.structured ?? undefined,
        sources: m.sources ?? undefined,
        timestamp: new Date(),
      }));
      localStorage.setItem(SESSION_STORAGE_KEY, id);
      setSessionId(id);
      setMessages(restored);
    } catch {
      /* silent */
    }
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    sendMessage(input);
  };

  const handleUpload = async (file: File) => {
    setIsUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);

      const res = await fetch(`${API_BASE}/api/upload`, { method: 'POST', body: formData });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const data = await res.json();
      const sysMsg: Message = {
        id: generateId(), role: 'assistant',
        content: `✅ **Documento "${data.filename}" processado com sucesso!**\n\n` +
                 `- **Tipo:** ${data.metadata?.tipo || 'Manual'}\n` +
                 `- **Chunks criados:** ${data.chunks_created}\n` +
                 `- **Resumo:** ${data.metadata?.assunto_resumo || 'N/A'}\n\n` +
                 `O documento já está disponível para consulta.`,
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, sysMsg]);

      // Refresh documents list
      fetch(`${API_BASE}/api/documents`).then(r => r.json()).then(setDocuments).catch(() => {});
    } catch {
      const errMsg: Message = {
        id: generateId(), role: 'assistant',
        content: '⚠️ Erro ao processar o documento. Verifique o formato e tente novamente.',
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, errMsg]);
    } finally {
      setIsUploading(false);
    }
  };

  const showWelcome = messages.length === 0;

  return (
    <>
      {/* Mobile hamburger */}
      <button className="hamburger-btn" onClick={() => setSidebarOpen(!sidebarOpen)}>
        <Menu size={20} />
      </button>

      {/* Mobile overlay */}
      <div
        className={`sidebar-overlay ${sidebarOpen ? 'visible' : ''}`}
        onClick={() => setSidebarOpen(false)}
      />

      {/* Sidebar */}
      <Sidebar
        onClearChat={startNewConversation}
        onUploadFile={handleUpload}
        isUploading={isUploading}
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        onSuggestionClick={(text) => sendMessage(text)}
        modelInfo={modelInfo}
        documents={documents}
        sections={sections}
        selectedSections={selectedSections}
        onToggleSection={toggleSection}
        onClearSections={clearSections}
        sessions={sessions}
        currentSessionId={sessionId}
        onSelectSession={loadSession}
        onDeleteSession={deleteSession}
        languageMode={languageMode}
        setLanguageMode={setLanguageMode}
      />

      {/* Main Content */}
      <div className="main-content">
        <div className="chat-area">
          {showWelcome ? (
            <div className="welcome-screen">
              <div className="welcome-watermark">
                <svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">
                  <circle cx="100" cy="100" r="90" fill="currentColor" opacity="0.3"/>
                  <circle cx="130" cy="60" r="40" fill="currentColor" opacity="0.5"/>
                  <circle cx="70" cy="140" r="30" fill="currentColor" opacity="0.4"/>
                  <text x="100" y="115" fontSize="48" fontWeight="bold" textAnchor="middle" fill="white" style={{ opacity: 1, textShadow: '0 2px 10px rgba(0,0,0,0.1)' }}>eproc</text>
                </svg>
              </div>
              <h1 className="welcome-title">eProc Agent</h1>
              <p className="welcome-subtitle">
                Seu assistente inteligente para o sistema judicial eProc.<br/>
                Faça perguntas sobre procedimentos, funcionalidades e dúvidas do sistema.
              </p>
              <div className="welcome-suggestions">
                {WELCOME_SUGGESTIONS.map((s, i) => (
                  <div key={i} className="welcome-suggestion" onClick={() => sendMessage(s.text)}>
                    <span className="welcome-suggestion-icon">{s.icon}</span>
                    {s.text}
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="chat-container">
              {messages.map((msg) => (
                <ChatMessage
                  key={msg.id}
                  message={msg}
                  onFollowup={sendMessage}
                  userQuery={
                    msg.role === 'assistant'
                      ? messages[messages.indexOf(msg) - 1]?.content
                      : undefined
                  }
                  languageMode={languageMode}
                />
              ))}

              {isLoading && (
                <div className="chat-message assistant">
                  <div className="chat-avatar assistant">
                    <Scale size={16} />
                  </div>
                  <div className="chat-content">
                    <div className="typing-indicator">
                      <div className="typing-dot" />
                      <div className="typing-dot" />
                      <div className="typing-dot" />
                    </div>
                  </div>
                </div>
              )}

              <div ref={chatEndRef} />
            </div>
          )}
        </div>

        {/* Input */}
        <div className="chat-input-container">
          <div className="chat-input-wrapper">
            <form onSubmit={handleSubmit}>
              <input
                ref={inputRef}
                className="chat-input"
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Pergunte algo sobre o eProc..."
                disabled={isLoading}
                autoFocus
              />
              <button
                className="chat-submit-btn"
                type="submit"
                disabled={!input.trim() || isLoading}
              >
                <Send size={16} />
              </button>
            </form>
          </div>
        </div>
      </div>
    </>
  );
}
