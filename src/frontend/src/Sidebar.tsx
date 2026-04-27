import React, { useRef, type ChangeEvent } from 'react';
import { Plus, Upload, Database, Zap } from 'lucide-react';
import type { SidebarProps } from './types';

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
        <div className="sidebar-logo-icon">
          <Zap size={20} />
        </div>
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
