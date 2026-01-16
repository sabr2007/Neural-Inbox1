import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * Format date relative to now (Russian)
 */
export function formatRelativeDate(dateStr: string): string {
  const date = new Date(dateStr)
  const now = new Date()
  const diffMs = date.getTime() - now.getTime()
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

  if (diffDays < -1) {
    return date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })
  }
  if (diffDays === -1) {
    return 'Вчера'
  }
  if (diffDays === 0) {
    return 'Сегодня'
  }
  if (diffDays === 1) {
    return 'Завтра'
  }
  if (diffDays < 7) {
    return date.toLocaleDateString('ru-RU', { weekday: 'long' })
  }

  return date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })
}

/**
 * Format time from ISO string
 */
export function formatTime(dateStr: string): string {
  const date = new Date(dateStr)
  return date.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
}

/**
 * Get type emoji
 */
export function getTypeEmoji(type: string): string {
  const emojis: Record<string, string> = {
    task: '✅',
    idea: '💡',
    note: '📝',
    resource: '🔗',
    contact: '👤',
  }
  return emojis[type] || '📝'
}

/**
 * Get type label in Russian
 */
export function getTypeLabel(type: string): string {
  const labels: Record<string, string> = {
    task: 'Задача',
    idea: 'Идея',
    note: 'Заметка',
    resource: 'Ресурс',
    contact: 'Контакт',
  }
  return labels[type] || 'Запись'
}

/**
 * Trigger haptic feedback if available
 */
export function haptic(type: 'light' | 'medium' | 'heavy' | 'success' | 'error' | 'warning' | 'selection' = 'light') {
  const tg = window.Telegram?.WebApp?.HapticFeedback
  if (!tg) return

  if (type === 'success' || type === 'error' || type === 'warning') {
    tg.notificationOccurred(type)
  } else if (type === 'selection') {
    tg.selectionChanged()
  } else {
    tg.impactOccurred(type)
  }
}
