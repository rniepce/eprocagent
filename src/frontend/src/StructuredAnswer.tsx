import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { ArrowRight, AlertTriangle, BookOpen, ListOrdered, Sparkles, HelpCircle } from 'lucide-react';
import type { AnswerStructured, ChatStructured, DisambiguationStructured } from './types';

type Props = {
  data: ChatStructured;
  onFollowup: (q: string) => void;
};

const md = (text: string) => (
  <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>
);

export function StructuredAnswer({ data, onFollowup }: Props) {
  if (data.mode === 'disambiguation') {
    return <Disambiguation data={data} onChoose={onFollowup} />;
  }
  return <Answer data={data} onFollowup={onFollowup} />;
}

function Disambiguation({
  data,
  onChoose,
}: {
  data: DisambiguationStructured;
  onChoose: (q: string) => void;
}) {
  return (
    <div className="structured-answer">
      <div className="sa-disamb-header">
        <HelpCircle size={18} className="sa-disamb-icon" />
        <div className="sa-disamb-pergunta">{data.pergunta}</div>
      </div>
      <div className="sa-disamb-grid">
        {data.opcoes.map((o, i) => (
          <button
            key={i}
            type="button"
            className="sa-disamb-card"
            onClick={() => onChoose(o.query)}
          >
            {o.icon && <span className="sa-disamb-card-icon">{o.icon}</span>}
            <span className="sa-disamb-card-body">
              <span className="sa-disamb-card-label">{o.label}</span>
              {o.hint && <span className="sa-disamb-card-hint">{o.hint}</span>}
            </span>
            <ArrowRight size={16} className="sa-disamb-card-arrow" />
          </button>
        ))}
      </div>
    </div>
  );
}

function Answer({
  data,
  onFollowup,
}: {
  data: AnswerStructured;
  onFollowup: (q: string) => void;
}) {
  return (
    <div className="structured-answer">
      <div className="sa-tldr">
        <Sparkles size={18} className="sa-tldr-icon" />
        <div>{md(data.tldr)}</div>
      </div>

      {data.conceitos.length > 0 && (
        <section className="sa-section">
          <h4 className="sa-section-title"><BookOpen size={16} /> Conceitos-chave</h4>
          <div className="sa-conceitos">
            {data.conceitos.map((c, i) => (
              <div key={i} className="sa-conceito">
                <strong className="sa-conceito-termo">{c.termo}</strong>
                <div className="sa-conceito-def">{md(c.definicao)}</div>
              </div>
            ))}
          </div>
        </section>
      )}

      {data.passos.length > 0 && (
        <section className="sa-section">
          <h4 className="sa-section-title"><ListOrdered size={16} /> Passo a passo</h4>
          <ol className="sa-passos">
            {data.passos.map((p, i) => (
              <li key={i} className="sa-passo">
                <div className="sa-passo-titulo"><strong>{p.titulo}</strong></div>
                <div className="sa-passo-desc">{md(p.descricao)}</div>
              </li>
            ))}
          </ol>
        </section>
      )}

      {data.atencao.length > 0 && (
        <section className="sa-section sa-atencao-box">
          <h4 className="sa-section-title sa-atencao-title">
            <AlertTriangle size={16} /> Atenção
          </h4>
          <ul className="sa-atencao-list">
            {data.atencao.map((a, i) => (
              <li key={i}>{md(a)}</li>
            ))}
          </ul>
        </section>
      )}

      {data.followups.length > 0 && (
        <section className="sa-section">
          <h4 className="sa-section-title">Quer ir mais fundo?</h4>
          <div className="sa-followups">
            {data.followups.map((f, i) => (
              <button
                key={i}
                className="sa-followup-chip"
                onClick={() => onFollowup(f)}
                type="button"
              >
                <span>{f}</span>
                <ArrowRight size={14} />
              </button>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
