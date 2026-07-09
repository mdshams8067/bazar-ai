import { apiRequest } from './client'
import type { ChatResponse } from '../types/api'

export interface ChatHistoryTurn {
  role: 'user' | 'assistant'
  text: string
}

export function sendChatMessage(
  message: string,
  history: ChatHistoryTurn[] = [],
): Promise<ChatResponse> {
  return apiRequest<ChatResponse>('/chat', { method: 'POST', body: { message, history } })
}
