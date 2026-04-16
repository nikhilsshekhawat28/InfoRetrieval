import type { Source, EvaluationScores } from "./api";

export type MessageRole = "user" | "assistant" | "system";
export type ChatMode = "chat" | "search";

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  sources?: Source[];
  searchResults?: Source[];
  evaluation?: EvaluationScores;
  cragTriggered?: boolean;
  timestamp: Date;
}

export const SOURCE_TYPE_ICONS: Record<string, string> = {
  document: "📄",
  url: "🔗",
  image_caption: "🖼️",
  text: "📝",
  bookmark: "🔖",
  image_ocr: "👁️",
};
