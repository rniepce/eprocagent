import React, { useRef, type ChangeEvent } from 'react';
import { Plus, Upload, Database, Filter, X, Trash2, FileText, Settings, Search, Clock, Paperclip, LogOut, Sparkles, Briefcase } from 'lucide-react';
import type { SidebarProps } from './types';
import { EprocLogo } from './EprocLogo';

const SUGGESTIONS = [
  { text: 'Como peticionar no eProc?', icon: <FileText size={16} /> },
  { text: 'Como configurar o certificado digital?', icon: <Settings size={16} /> },
  { text: 'Como consultar um processo?', icon: <Search size={16} /> },
  { text: 'Como funcionam os prazos processuais?', icon: <Clock size={16} /> },
  { text: 'Como anexar documentos?', icon: <Paperclip size={16} /> },
];

const Sidebar: React.FC<SidebarProps> = ({
  onClearChat, onUploadFile, isUploading,
  isOpen, onClose, onSuggestionClick,
  modelInfo, documents,
  sections, selectedSections, onToggleSection, onClearSections,
  sessions, currentSessionId, onSelectSession, onDeleteSession,
  languageMode, setLanguageMode
}) => {
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      await onUploadFile(file);
      e.target.value = '';
    }
  };

  return (
    <div className={`sidebar ${isOpen ? 'open' : ''}`}>
      {/* Logo */}
      <div className="sidebar-logo" style={{ justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <EprocLogo size={44} />
          <div>
            <div className="sidebar-logo-text">eProc Agent</div>
            <div className="sidebar-logo-sub">ASSISTENTE JUDICIAL</div>
          </div>
        </div>
        <button aria-label="Sair" style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}>
          <LogOut size={20} />
        </button>
      </div>

      {/* New Chat */}
      <button className="btn-new-chat" onClick={() => { onClearChat(); onClose(); }}>
        <Plus size={18} /> Nova Conversa
      </button>

      {/* Suggestions */}
      <div className="sidebar-section">
        <div className="sidebar-section-title">Perguntas Frequentes</div>
        {SUGGESTIONS.map((s, i) => (
          <div key={i} className="suggestion-card" onClick={() => { onSuggestionClick(s.text); onClose(); }} style={{ display: 'flex', gap: '8px', alignItems: 'center', background: 'transparent', border: 'none', padding: '0.4rem 0' }}>
            <span style={{ color: 'var(--accent-blue-light)' }}>{s.icon}</span>
            <span>{s.text}</span>
          </div>
        ))}
      </div>

      <hr className="sidebar-divider" />

      {/* Past conversations */}
      {sessions.length > 0 && (
        <div className="sidebar-section">
          <div className="sidebar-section-title" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span>Conversas anteriores</span>
            <span style={{ background: 'var(--border)', color: 'var(--text-secondary)', padding: '2px 6px', borderRadius: '12px', fontSize: '0.65rem' }}>{sessions.length}</span>
          </div>
          <div className="session-list">
            {sessions.slice(0, 8).map((s) => (
              <div
                key={s.session_id}
                className={`session-item ${s.session_id === currentSessionId ? 'active' : ''}`}
                title={s.last_at ? new Date(s.last_at).toLocaleString() : ''}
              >
                <button
                  type="button"
                  className="session-open"
                  onClick={() => { onSelectSession(s.session_id); onClose(); }}
                >
                  <span className="session-title">{s.title}</span>
                  <span className="session-count" style={{ background: 'var(--border)', color: 'var(--text-secondary)' }}>{s.msg_count}</span>
                </button>
                <button
                  type="button"
                  className="session-delete"
                  aria-label="Excluir conversa"
                  onClick={(e) => {
                    e.stopPropagation();
                    if (confirm('Excluir esta conversa? Não dá para desfazer.')) {
                      onDeleteSession(s.session_id);
                    }
                  }}
                >
                  <Trash2 size={12} />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Section filter */}
      {sections.length > 0 && (
        <>
          <hr className="sidebar-divider" />
          <div className="sidebar-section">
            <div className="sidebar-section-title-row">
              <span className="sidebar-section-title">
                <Filter size={11} /> Filtrar por seção
              </span>
              {selectedSections.length > 0 && (
                <button
                  type="button"
                  className="sidebar-clear-btn"
                  onClick={onClearSections}
                  aria-label="Limpar filtros"
                >
                  <X size={12} /> Limpar
                </button>
              )}
            </div>
            <div className="section-chips">
              {sections.map((s) => {
                const active = selectedSections.includes(s.secao);
                return (
                  <button
                    key={s.secao}
                    type="button"
                    className={`section-chip ${active ? 'active' : ''}`}
                    onClick={() => onToggleSection(s.secao)}
                    title={`${s.count} documento(s)`}
                  >
                    {s.secao}
                    <span className="section-chip-count">{s.count}</span>
                  </button>
                );
              })}
            </div>
          </div>
        </>
      )}

      {/* Upload */}
      <div className="sidebar-section">
        <button
          className="btn-upload"
          onClick={() => fileInputRef.current?.click()}
          disabled={isUploading}
        >
          {isUploading ? (
            <><div className="spinner" /> Processando...</>
          ) : (
            <><Upload size={16} /> Enviar Manual (PDF/DOCX)</>
          )}
        </button>
        <input
          ref={fileInputRef} type="file" accept=".pdf,.doc,.docx"
          style={{ display: 'none' }} onChange={handleFileSelect}
        />
      </div>

      {/* Footer */}
      <div className="sidebar-footer">
        {modelInfo && modelInfo.provider !== 'none' && (
          <div className="sidebar-model-info">
            <span className="sidebar-model-dot" />
            {modelInfo.label}
          </div>
        )}
        <div className="sidebar-doc-count">
          <Database size={12} />
          {documents.length} documento{documents.length !== 1 ? 's' : ''} indexado{documents.length !== 1 ? 's' : ''}
        </div>
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
      </div>
    </div>
  );
};

export default Sidebar;
