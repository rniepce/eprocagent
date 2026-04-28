import React, { useRef, type ChangeEvent } from 'react';
import { Plus, Upload, Database, Filter, X, MessageCircle, Trash2 } from 'lucide-react';
import type { SidebarProps } from './types';
import { EprocLogo } from './EprocLogo';

const SUGGESTIONS = [
  '📋 Como peticionar no eProc?',
  '🔐 Como configurar o certificado digital?',
  '📄 Como consultar um processo?',
  '⏰ Como funcionam os prazos processuais?',
  '📎 Como anexar documentos?',
  '🔍 Como fazer busca avançada?',
];

const Sidebar: React.FC<SidebarProps> = ({
  onClearChat, onUploadFile, isUploading,
  isOpen, onClose, onSuggestionClick,
  modelInfo, documents,
  sections, selectedSections, onToggleSection, onClearSections,
  sessions, currentSessionId, onSelectSession, onDeleteSession,
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
      <div className="sidebar-logo">
        <EprocLogo size={44} />
        <div>
          <div className="sidebar-logo-text">eProc Agent</div>
          <div className="sidebar-logo-sub">ASSISTENTE JUDICIAL</div>
        </div>
      </div>

      {/* New Chat */}
      <button className="btn-new-chat" onClick={() => { onClearChat(); onClose(); }}>
        <Plus size={18} /> Nova Conversa
      </button>

      {/* Suggestions */}
      <div className="sidebar-section">
        <div className="sidebar-section-title">Perguntas Frequentes</div>
        {SUGGESTIONS.map((s, i) => (
          <div key={i} className="suggestion-card" onClick={() => { onSuggestionClick(s.replace(/^.{2} /, '')); onClose(); }}>
            {s}
          </div>
        ))}
      </div>

      <hr className="sidebar-divider" />

      {/* Past conversations */}
      {sessions.length > 0 && (
        <div className="sidebar-section">
          <div className="sidebar-section-title">
            <MessageCircle size={11} /> Conversas anteriores
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
                  <span className="session-count">{s.msg_count}</span>
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

      <hr className="sidebar-divider" />

      {/* Section filter */}
      {sections.length > 0 && (
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
      )}

      <hr className="sidebar-divider" />

      {/* Upload */}
      <div className="sidebar-section">
        <div className="sidebar-section-title">Gerenciar Manuais</div>
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
      </div>
    </div>
  );
};

export default Sidebar;
