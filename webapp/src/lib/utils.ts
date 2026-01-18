import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * Format date with time (Russian) - shows exact date and time
 */
export function formatRelativeDate(dateStr: string): string {
  const date = new Date(dateStr)
  const now = new Date()

  // Check if same day
  const isToday = date.toDateString() === now.toDateString()
  const tomorrow = new Date(now)
  tomorrow.setDate(tomorrow.getDate() + 1)
  const isTomorrow = date.toDateString() === tomorrow.toDateString()

  const timeStr = date.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })

  if (isToday) {
    return `Сегодня, ${timeStr}`
  }
  if (isTomorrow) {
    return `Завтра, ${timeStr}`
  }

  // Show full date with time
  return date.toLocaleDateString('ru-RU', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit'
  })
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
