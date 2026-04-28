import { useState, useRef, useEffect, useCallback } from 'react';
import { Send, Scale, MessageSquare, FileSearch, BookOpen, HelpCircle, Menu, Sparkles, Briefcase } from 'lucide-react';
import ChatMessage from './ChatMessage';
import Sidebar from './Sidebar';
import type { Message, ModelInfo, DocumentInfo } from './types';
import './index.css';

type LanguageMode = 'simple' | 'technical';
const LANG_STORAGE_KEY = 'eproc.language_mode';

const API_BASE = import.meta.env.DEV ? 'http://localhost:8080' : '';

function generateId() {
  return Math.random().toString(36).substring(2, 15);
}

const WELCOME_SUGGESTIONS = [
  { icon: <MessageSquare size={20} />, text: 'Como peticionar no eProc?' },
  { icon: <FileSearch size={20} />, text: 'Como consultar um processo pelo número?' },
  { icon: <BookOpen size={20} />, text: 'Como configurar o certificado digital para acessar o eProc?' },
  { icon: <HelpCircle size={20} />, text: 'Quais os prazos para recurso no eProc?' },
];

export default function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [modelInfo, setModelInfo] = useState<ModelInfo | null>(null);
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [languageMode, setLanguageMode] = useState<LanguageMode>(() => {
    const saved = localStorage.getItem(LANG_STORAGE_KEY);
    return saved === 'technical' ? 'technical' : 'simple';
  });
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
  }, []);

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
        body: JSON.stringify({ query: text.trim(), language_mode: languageMode }),
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
  }, [isLoading, languageMode]);

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
        onClearChat={() => setMessages([])}
        onUploadFile={handleUpload}
        isUploading={isUploading}
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        onSuggestionClick={(text) => sendMessage(text)}
        modelInfo={modelInfo}
        documents={documents}
      />

      {/* Main Content */}
      <div className="main-content">
        <div className="chat-area">
          {showWelcome ? (
            <div className="welcome-screen">
              <div className="welcome-icon">
                <Scale size={28} color="white" />
              </div>
              <h1 className="welcome-title">eProc Agent</h1>
              <p className="welcome-subtitle">
                Seu assistente inteligente para o sistema judicial eProc.
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
            <div className="lang-toggle" role="radiogroup" aria-label="Tom da resposta">
              <button
                type="button"
                role="radio"
                aria-checked={languageMode === 'simple'}
                className={`lang-pill ${languageMode === 'simple' ? 'active' : ''}`}
                onClick={() => setLanguageMode('simple')}
                title="Linguagem clara, sem juridiquês"
              >
                <Sparkles size={13} /> Simples
              </button>
              <button
                type="button"
                role="radio"
                aria-checked={languageMode === 'technical'}
                className={`lang-pill ${languageMode === 'technical' ? 'active' : ''}`}
                onClick={() => setLanguageMode('technical')}
                title="Tom formal, terminologia jurídica"
              >
                <Briefcase size={13} /> Técnico
              </button>
            </div>
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
