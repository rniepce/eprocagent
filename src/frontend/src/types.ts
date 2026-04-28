/**
 * TypeScript interfaces for the eProc Agent application.
 */

export interface Source {
  document_id: number;
  filename: string;
  titulo?: string;
  tipo: string;
  secao?: string;
  chunk_text: string;
  score: number;
  pagina?: number;
}

export interface Conceito {
  termo: string;
  definicao: string;
}

export interface Passo {
  titulo: string;
  descricao: string;
}

export interface AnswerStructured {
  mode: 'answer';
  tldr: string;
  conceitos: Conceito[];
  passos: Passo[];
  atencao: string[];
  followups: string[];
}

export interface DisambiguationOption {
  label: string;
  icon?: string;
  query: string;
  hint?: string;
}

export interface DisambiguationStructured {
  mode: 'disambiguation';
  pergunta: string;
  opcoes: DisambiguationOption[];
}

export type ChatStructured = AnswerStructured | DisambiguationStructured;

export type StreamingStatus = 'searching' | 'thinking' | 'error';

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  structured?: ChatStructured;
  sources?: Source[];
  status?: StreamingStatus;
  timestamp: Date;
}

export interface ChatResponse {
  answer: string;
  structured?: ChatStructured;
  sources: Source[];
  session_id?: string;
}

export interface ModelInfo {
  provider: string;
  model: string;
  label: string;
}

export interface DocumentInfo {
  id: number;
  filename: string;
  titulo?: string;
  tipo: string;
  secao?: string;
  assunto_resumo?: string;
  tags: string[];
  total_chunks: number;
  created_at?: string;
}

export interface ChatMessageProps {
  message: Message;
}

export interface SectionInfo {
  secao: string;
  count: number;
}

export interface SessionSummaryItem {
  session_id: string;
  title: string;
  msg_count: number;
  last_at?: string | null;
}

export interface SidebarProps {
  onClearChat: () => void;
  onUploadFile: (file: File) => Promise<void>;
  isUploading: boolean;
  isOpen: boolean;
  onClose: () => void;
  onSuggestionClick: (text: string) => void;
  modelInfo: ModelInfo | null;
  documents: DocumentInfo[];
  sections: SectionInfo[];
  selectedSections: string[];
  onToggleSection: (secao: string) => void;
  onClearSections: () => void;
  sessions: SessionSummaryItem[];
  currentSessionId: string;
  onSelectSession: (id: string) => void;
}
