import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { ChevronDown, ChevronRight, FileText, User, Scale } from 'lucide-react';
import type { ChatMessageProps } from './types';

const ChatMessage: React.FC<ChatMessageProps> = ({ message }) => {
  const isUser = message.role === 'user';
  const [sourcesExpanded, setSourcesExpanded] = useState(false);

  const getBadgeClass = (tipo: string) => {
    const t = tipo?.toLowerCase() || '';
    if (t.includes('faq')) return 'badge-faq';
    if (t.includes('tutorial')) return 'badge-tutorial';
    return 'badge-manual';
  };

  return (
    <div className={`chat-message ${message.role}`}>
      <div className={`chat-avatar ${message.role}`}>
        {isUser ? <User size={16} /> : <Scale size={16} />}
      </div>

      <div className="chat-content">
        {isUser ? (
          <p>{message.content}</p>
        ) : (
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {message.content}
          </ReactMarkdown>
        )}

        {message.sources && message.sources.length > 0 && (
          <div className="sources-expander">
            <div
              className="sources-header"
              onClick={() => setSourcesExpanded(!sourcesExpanded)}
            >
              <span>📚 Fontes consultadas ({message.sources.length})</span>
              {sourcesExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            </div>

            {sourcesExpanded && (
              <div className="sources-content">
                {message.sources.map((src, idx) => (
                  <div className="source-card" key={idx}>
                    <div className="source-title">
                      <FileText size={12} />
                      {src.titulo || src.filename}
                      <span className={`badge ${getBadgeClass(src.tipo)}`}>
                        {src.tipo}
                      </span>
                      {src.pagina && (
                        <span className="badge badge-manual">p. {src.pagina}</span>
                      )}
                      <span className="source-score">
                        {(src.score * 100).toFixed(0)}%
                      </span>
                    </div>
                    <div className="source-excerpt">
                      {src.chunk_text.substring(0, 250)}…
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default ChatMessage;
