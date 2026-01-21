import { useState, useMemo } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Drawer } from 'vaul'
import {
  X, Calendar, Tag, Folder, Trash2, Check, MoreVertical,
  Paperclip, Clock, Send, FileText, Image, Repeat, ChevronDown
} from 'lucide-react'
import { RecurrenceRule, updateItem } from '@/api/client'
import { cn, formatRelativeDate, getTypeEmoji, getTypeLabel, haptic } from '@/lib/utils'
import { Item, completeItem, deleteItem, sendToChat } from '@/api/client'

// Day names for weekly recurrence
const DAY_NAMES = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']

interface RecurrenceEditorProps {
  itemId: number
  currentRecurrence?: RecurrenceRule
  onSave: () => void
  onCancel: () => void
}

/**
 * Recurrence editor component for setting up recurring tasks
 */
function RecurrenceEditor({ itemId, currentRecurrence, onSave, onCancel }: RecurrenceEditorProps) {
  const queryClient = useQueryClient()

  const [type, setType] = useState<'daily' | 'weekly' | 'monthly'>(
    currentRecurrence?.type || 'daily'
  )
  const [interval, setInterval] = useState(currentRecurrence?.interval || 1)
  const [days, setDays] = useState<number[]>(currentRecurrence?.days || [0, 1, 2, 3, 4])

  const saveMutation = useMutation({
    mutationFn: () => {
      const recurrence: RecurrenceRule = {
        type,
        interval,
        ...(type === 'weekly' && { days }),
      }
      return updateItem(itemId, { recurrence })
    },
    onSuccess: () => {
      haptic('success')
      queryClient.invalidateQueries({ queryKey: ['items'] })
      queryClient.invalidateQueries({ queryKey: ['tasks'] })
      onSave()
    },
    onError: (error) => {
      console.error('Failed to save recurrence:', error)
      haptic('error')
    },
  })

  const removeMutation = useMutation({
    mutationFn: () => updateItem(itemId, { recurrence: null } as any),
    onSuccess: () => {
      haptic('success')
      queryClient.invalidateQueries({ queryKey: ['items'] })
      queryClient.invalidateQueries({ queryKey: ['tasks'] })
      onSave()
    },
    onError: (error) => {
      console.error('Failed to remove recurrence:', error)
      haptic('error')
    },
  })

  const toggleDay = (dayIndex: number) => {
    setDays(prev =>
      prev.includes(dayIndex)
        ? prev.filter(d => d !== dayIndex)
        : [...prev, dayIndex].sort()
    )
  }

  return (
    <div className="p-4 bg-tg-secondary-bg rounded-xl space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="font-medium text-tg-text">Настройка повтора</h3>
        {currentRecurrence && (
          <button
            onClick={() => removeMutation.mutate()}
            disabled={removeMutation.isPending}
            className="text-sm text-red-500 hover:text-red-600"
          >
            Удалить
          </button>
        )}
      </div>

      {/* Type selector */}
      <div className="space-y-2">
        <label className="text-sm text-tg-hint">Частота</label>
        <div className="grid grid-cols-3 gap-2">
          {(['daily', 'weekly', 'monthly'] as const).map((t) => (
            <button
              key={t}
              onClick={() => setType(t)}
              className={cn(
                'py-2 px-3 rounded-lg text-sm font-medium transition-colors',
                type === t
                  ? 'bg-primary text-white'
                  : 'bg-tg-bg text-tg-text hover:bg-tg-bg/80'
              )}
            >
              {t === 'daily' && 'Ежедневно'}
              {t === 'weekly' && 'Еженедельно'}
              {t === 'monthly' && 'Ежемесячно'}
            </button>
          ))}
        </div>
      </div>

      {/* Interval selector */}
      <div className="space-y-2">
        <label className="text-sm text-tg-hint">
          Каждые
        </label>
        <div className="flex items-center gap-2">
          <input
            type="number"
            min={1}
            max={30}
            value={interval}
            onChange={(e) => setInterval(Math.max(1, parseInt(e.target.value) || 1))}
            className="w-20 py-2 px-3 rounded-lg bg-tg-bg text-tg-text text-center border-none outline-none focus:ring-2 focus:ring-primary"
          />
          <span className="text-tg-text">
            {type === 'daily' && (interval === 1 ? 'день' : 'дней')}
            {type === 'weekly' && (interval === 1 ? 'неделю' : 'недель')}
            {type === 'monthly' && (interval === 1 ? 'месяц' : 'месяцев')}
          </span>
        </div>
      </div>

      {/* Day selector for weekly */}
      {type === 'weekly' && (
        <div className="space-y-2">
          <label className="text-sm text-tg-hint">Дни недели</label>
          <div className="flex gap-1">
            {DAY_NAMES.map((name, index) => (
              <button
                key={index}
                onClick={() => toggleDay(index)}
                className={cn(
                  'flex-1 py-2 rounded-lg text-sm font-medium transition-colors',
                  days.includes(index)
                    ? 'bg-primary text-white'
                    : 'bg-tg-bg text-tg-hint hover:text-tg-text'
                )}
              >
                {name}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-2 pt-2">
        <button
          onClick={onCancel}
          className="flex-1 py-2 rounded-lg bg-tg-bg text-tg-text font-medium hover:bg-tg-bg/80 transition-colors"
        >
          Отмена
        </button>
        <button
          onClick={() => saveMutation.mutate()}
          disabled={saveMutation.isPending || (type === 'weekly' && days.length === 0)}
          className="flex-1 py-2 rounded-lg bg-primary text-white font-medium hover:bg-primary-600 transition-colors disabled:opacity-50"
        >
          {saveMutation.isPending ? 'Сохранение...' : 'Сохранить'}
        </button>
      </div>
    </div>
  )
}

// Regex to match URLs in text
const URL_REGEX = /https?:\/\/[^\s<>"{}|\\^`\[\]]+/g

/**
 * Renders text with clickable links.
 * Converts plain URLs to <a> tags that open in new tab.
 */
function TextWithLinks({ text }: { text: string }) {
  const parts = useMemo(() => {
    const result: (string | { url: string; key: number })[] = []
    let lastIndex = 0
    let match: RegExpExecArray | null
    let keyCounter = 0

    // Reset regex state
    URL_REGEX.lastIndex = 0

    while ((match = URL_REGEX.exec(text)) !== null) {
      // Add text before the URL
      if (match.index > lastIndex) {
        result.push(text.slice(lastIndex, match.index))
      }
      // Add the URL as an object
      result.push({ url: match[0], key: keyCounter++ })
      lastIndex = match.index + match[0].length
    }

    // Add remaining text after last URL
    if (lastIndex < text.length) {
      result.push(text.slice(lastIndex))
    }

    return result
  }, [text])

  return (
    <>
      {parts.map((part, index) =>
        typeof part === 'string' ? (
          <span key={index}>{part}</span>
        ) : (
          <a
            key={part.key}
            href={part.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-primary hover:underline break-all"
            onClick={(e) => e.stopPropagation()}
          >
            {part.url}
          </a>
        )
      )}
    </>
  )
}

/**
 * Format recurrence rule to human-readable string
 */
function formatRecurrence(recurrence: RecurrenceRule): string {
  const { type, interval } = recurrence

  if (type === 'daily') {
    return interval === 1 ? 'Каждый день' : `Каждые ${interval} дн.`
  }

  if (type === 'weekly') {
    const days = recurrence.days || []
    const dayNames = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
    const selectedDays = days.map(d => dayNames[d]).join(', ')

    if (interval === 1) {
      return days.length > 0 ? `Каждую нед. (${selectedDays})` : 'Каждую неделю'
    }
    return `Каждые ${interval} нед.`
  }

  if (type === 'monthly') {
    return interval === 1 ? 'Каждый месяц' : `Каждые ${interval} мес.`
  }

  return 'Повторяется'
}

interface ItemDetailProps {
  item: Item
  open: boolean
  onClose: () => void
}

export default function ItemDetail({ item, open, onClose }: ItemDetailProps) {
  const queryClient = useQueryClient()
  const [showMenu, setShowMenu] = useState(false)
  const [showRecurrenceEditor, setShowRecurrenceEditor] = useState(false)

  const completeMutation = useMutation({
    mutationFn: () => completeItem(item.id),
    onSuccess: () => {
      haptic('success')
      // Invalidate all relevant queries
      queryClient.invalidateQueries({ queryKey: ['items'] })
      queryClient.invalidateQueries({ queryKey: ['tasks'] })
      queryClient.invalidateQueries({ queryKey: ['calendar'] })
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      onClose()
    },
    onError: (error) => {
      console.error('Failed to complete item:', error)
      haptic('error')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: () => deleteItem(item.id),
    onSuccess: () => {
      haptic('success')
      // Invalidate all relevant queries
      queryClient.invalidateQueries({ queryKey: ['items'] })
      queryClient.invalidateQueries({ queryKey: ['tasks'] })
      queryClient.invalidateQueries({ queryKey: ['calendar'] })
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      onClose()
    },
    onError: (error) => {
      console.error('Failed to delete item:', error)
      haptic('error')
    },
  })

  const sendToChatMutation = useMutation({
    mutationFn: () => sendToChat(item.id),
    onSuccess: () => {
      haptic('success')
    },
    onError: (error) => {
      console.error('Failed to send to chat:', error)
      haptic('error')
    },
  })

  const handleComplete = () => {
    if (item.type === 'task' && item.status !== 'done') {
      completeMutation.mutate()
    }
  }

  const handleDelete = () => {
    if (confirm('Удалить эту запись?')) {
      deleteMutation.mutate()
    }
  }

  const isCompleted = item.status === 'done'

  return (
    <Drawer.Root open={open} onOpenChange={(o) => !o && onClose()}>
      <Drawer.Portal>
        <Drawer.Overlay className="fixed inset-0 bg-black/50 z-50" />
        <Drawer.Content className="fixed bottom-0 left-0 right-0 z-50 bg-tg-bg rounded-t-2xl max-h-[85vh] flex flex-col">
          {/* Handle */}
          <div className="flex justify-center py-3">
            <div className="w-10 h-1 bg-tg-hint/30 rounded-full" />
          </div>

          {/* Header */}
          <div className="flex items-center justify-between px-4 pb-3 border-b border-tg-secondary-bg">
            <div className="flex items-center gap-2">
              <span className="text-lg">{getTypeEmoji(item.type)}</span>
              <span className="text-tg-hint">{getTypeLabel(item.type)}</span>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setShowMenu(!showMenu)}
                className="p-2 rounded-full hover:bg-tg-secondary-bg"
              >
                <MoreVertical size={20} className="text-tg-hint" />
              </button>
              <button
                onClick={onClose}
                className="p-2 rounded-full hover:bg-tg-secondary-bg"
              >
                <X size={20} className="text-tg-hint" />
              </button>
            </div>
          </div>

          {/* Menu dropdown */}
          {showMenu && (
            <div className="absolute right-4 top-16 bg-tg-bg border border-tg-secondary-bg rounded-lg shadow-lg z-10">
              {item.type === 'task' && item.status !== 'done' && (
                <button
                  onClick={() => {
                    setShowMenu(false)
                    handleComplete()
                  }}
                  className="flex items-center gap-2 px-4 py-2 w-full text-left hover:bg-tg-secondary-bg"
                >
                  <Check size={18} />
                  <span>Выполнено</span>
                </button>
              )}
              <button
                onClick={() => {
                  setShowMenu(false)
                  handleDelete()
                }}
                className="flex items-center gap-2 px-4 py-2 w-full text-left hover:bg-tg-secondary-bg text-red-500"
              >
                <Trash2 size={18} />
                <span>Удалить</span>
              </button>
            </div>
          )}

          {/* Content */}
          <div className="flex-1 overflow-auto px-4 py-4">
            {/* Title */}
            <h2 className={cn(
              'text-xl font-semibold text-tg-text mb-4',
              isCompleted && 'line-through opacity-60'
            )}>
              {item.title}
            </h2>

            {/* Meta info */}
            <div className="space-y-3 mb-6">
              {item.due_at && (
                <div className="flex items-center gap-3 text-tg-text">
                  <Calendar size={18} className="text-tg-hint" />
                  <span>{formatRelativeDate(item.due_at)}</span>
                </div>
              )}

              {/* Recurrence section - editable for tasks */}
              {item.type === 'task' && item.status !== 'done' && (
                <div className="space-y-3">
                  {showRecurrenceEditor ? (
                    <RecurrenceEditor
                      itemId={item.id}
                      currentRecurrence={item.recurrence}
                      onSave={() => setShowRecurrenceEditor(false)}
                      onCancel={() => setShowRecurrenceEditor(false)}
                    />
                  ) : item.recurrence ? (
                    <button
                      onClick={() => setShowRecurrenceEditor(true)}
                      className="flex items-center gap-3 text-tg-text hover:bg-tg-secondary-bg rounded-lg p-2 -m-2 transition-colors w-full"
                    >
                      <Repeat size={18} className="text-primary" />
                      <span>{formatRecurrence(item.recurrence)}</span>
                      <ChevronDown size={16} className="text-tg-hint ml-auto" />
                    </button>
                  ) : (
                    <button
                      onClick={() => setShowRecurrenceEditor(true)}
                      className="flex items-center gap-3 text-tg-hint hover:text-tg-text hover:bg-tg-secondary-bg rounded-lg p-2 -m-2 transition-colors w-full"
                    >
                      <Repeat size={18} />
                      <span>Добавить повтор</span>
                    </button>
                  )}
                </div>
              )}

              {/* Show recurrence for non-task items or completed tasks (read-only) */}
              {(item.type !== 'task' || item.status === 'done') && item.recurrence && (
                <div className="flex items-center gap-3 text-tg-text">
                  <Repeat size={18} className="text-primary" />
                  <span>{formatRecurrence(item.recurrence)}</span>
                </div>
              )}

              {item.tags && item.tags.length > 0 && (
                <div className="flex items-center gap-3 text-tg-text">
                  <Tag size={18} className="text-tg-hint" />
                  <span>{item.tags.join(' ')}</span>
                </div>
              )}

              {item.project_id && (
                <div className="flex items-center gap-3 text-tg-text">
                  <Folder size={18} className="text-tg-hint" />
                  <span>Проект #{item.project_id}</span>
                </div>
              )}

              <div className="flex items-center gap-3 text-tg-hint text-sm">
                <Clock size={16} />
                <span>
                  Создано: {new Date(item.created_at).toLocaleDateString('ru-RU', {
                    day: 'numeric',
                    month: 'long',
                    hour: '2-digit',
                    minute: '2-digit'
                  })}
                </span>
              </div>
            </div>

            {/* Attachment section for documents/photos */}
            {item.attachment_file_id && (item.attachment_type === 'document' || item.attachment_type === 'photo') && (
              <div className="border-t border-tg-secondary-bg pt-4">
                <div className="flex items-center gap-2 mb-3 text-tg-hint text-sm">
                  {item.attachment_type === 'photo' ? (
                    <Image size={14} />
                  ) : (
                    <FileText size={14} />
                  )}
                  <span>Вложение</span>
                </div>
                <div className="p-4 bg-tg-secondary-bg rounded-lg">
                  <p className="text-tg-text font-medium mb-3">
                    {item.attachment_filename || (item.attachment_type === 'photo' ? 'Фото' : 'Документ')}
                  </p>
                  <button
                    onClick={() => sendToChatMutation.mutate()}
                    disabled={sendToChatMutation.isPending}
                    className="flex items-center gap-2 px-4 py-2 bg-primary text-white rounded-lg font-medium hover:bg-primary-600 transition-colors disabled:opacity-50"
                  >
                    <Send size={16} />
                    {sendToChatMutation.isPending ? 'Отправка...' : 'Отправить в Telegram'}
                  </button>
                </div>
              </div>
            )}

            {/* Original content - only for non-document/photo items */}
            {(item.content || item.original_input) &&
              !(item.attachment_type === 'document' || item.attachment_type === 'photo') && (
                <div className="border-t border-tg-secondary-bg pt-4">
                  <div className="flex items-center gap-2 mb-2 text-tg-hint text-sm">
                    <Paperclip size={14} />
                    <span>Исходное сообщение</span>
                  </div>
                  <div className="p-3 bg-tg-secondary-bg rounded-lg text-tg-text text-sm whitespace-pre-wrap">
                    <TextWithLinks text={item.content || item.original_input || ''} />
                  </div>
                </div>
              )}
          </div>

          {/* Actions */}
          {item.type === 'task' && item.status !== 'done' && (
            <div className="p-4 border-t border-tg-secondary-bg safe-area-bottom">
              <button
                onClick={handleComplete}
                disabled={completeMutation.isPending}
                className="w-full py-3 bg-primary text-white rounded-lg font-medium hover:bg-primary-600 transition-colors disabled:opacity-50"
              >
                {completeMutation.isPending ? 'Сохранение...' : 'Выполнено'}
              </button>
            </div>
          )}
        </Drawer.Content>
      </Drawer.Portal>
    </Drawer.Root>
  )
}
