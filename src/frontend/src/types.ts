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

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: Source[];
  timestamp: Date;
}

export interface ChatResponse {
  answer: string;
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

export interface SidebarProps {
  onClearChat: () => void;
  onUploadFile: (file: File) => Promise<void>;
  isUploading: boolean;
  isOpen: boolean;
  onClose: () => void;
  onSuggestionClick: (text: string) => void;
  modelInfo: ModelInfo | null;
  documents: DocumentInfo[];
}
