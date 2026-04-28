import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { ChevronDown, ChevronRight, FileText, User, Scale, Search, Brain, ThumbsUp, ThumbsDown } from 'lucide-react';
import type { ChatMessageProps } from './types';
import { StructuredAnswer } from './StructuredAnswer';

const API_BASE = import.meta.env.DEV ? 'http://localhost:8080' : '';

type Props = ChatMessageProps & {
  onFollowup?: (q: string) => void;
  userQuery?: string;
  languageMode?: string;
};

const STATUS_LABEL: Record<string, { icon: React.ReactNode; text: string }> = {
  searching: { icon: <Search size={14} />, text: 'Buscando nos manuais…' },
  thinking: { icon: <Brain size={14} />, text: 'Consultando o gpt-5.5…' },
};

const ChatMessage: React.FC<Props> = ({ message, onFollowup, userQuery, languageMode }) => {
  const isUser = message.role === 'user';
  const [sourcesExpanded, setSourcesExpanded] = useState(false);
  const [vote, setVote] = useState<-1 | 0 | 1>(0);
  const [showComment, setShowComment] = useState(false);
  const [comment, setComment] = useState('');
  const [commentSent, setCommentSent] = useState(false);

  const sendFeedback = async (v: -1 | 1, withComment?: string) => {
    setVote(v);
    if (v === -1 && withComment === undefined) {
      setShowComment(true);
    }
    try {
      await fetch(`${API_BASE}/api/feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: userQuery ?? '',
          answer: message.content,
          structured: message.structured ?? null,
          sources_doc_ids: (message.sources ?? []).map(s => s.document_id),
          vote: v,
          comment: withComment ?? null,
          language_mode: languageMode ?? null,
        }),
      });
      if (withComment) {
        setCommentSent(true);
        setShowComment(false);
      }
    } catch {
      /* silent */
    }
  };

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
        ) : message.structured ? (
          <StructuredAnswer
            data={message.structured}
            onFollowup={(q) => onFollowup?.(q)}
          />
        ) : message.content ? (
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {message.content}
          </ReactMarkdown>
        ) : message.status && STATUS_LABEL[message.status] ? (
          <div className="chat-status">
            <span className="chat-status-dot" />
            {STATUS_LABEL[message.status].icon}
            <span>{STATUS_LABEL[message.status].text}</span>
          </div>
        ) : null}

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

        {!isUser && (message.structured || message.content) && !message.status && (
          <div className="feedback-bar">
            <button
              type="button"
              className={`feedback-btn ${vote === 1 ? 'active up' : ''}`}
              aria-label="Resposta útil"
              disabled={vote !== 0}
              onClick={() => sendFeedback(1)}
            >
              <ThumbsUp size={14} />
            </button>
            <button
              type="button"
              className={`feedback-btn ${vote === -1 ? 'active down' : ''}`}
              aria-label="Resposta não ajudou"
              disabled={vote !== 0}
              onClick={() => sendFeedback(-1)}
            >
              <ThumbsDown size={14} />
            </button>
            {vote === 1 && <span className="feedback-thanks">Obrigado!</span>}
            {commentSent && <span className="feedback-thanks">Feedback registrado.</span>}

            {showComment && !commentSent && (
              <div className="feedback-comment">
                <textarea
                  className="feedback-textarea"
                  placeholder="O que faltou ou ficou impreciso? (opcional)"
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                  rows={2}
                  maxLength={2000}
                />
                <div className="feedback-comment-actions">
                  <button
                    type="button"
                    className="feedback-skip"
                    onClick={() => { setShowComment(false); setCommentSent(true); }}
                  >
                    Pular
                  </button>
                  <button
                    type="button"
                    className="feedback-send"
                    onClick={() => sendFeedback(-1, comment.trim() || '(sem comentário)')}
                  >
                    Enviar
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default ChatMessage;
