import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Drawer } from 'vaul'
import {
  X, Calendar, Tag, Folder, Trash2, Check, MoreVertical,
  Paperclip, Clock, Send, FileText, Image
} from 'lucide-react'
import { cn, formatRelativeDate, formatTime, getTypeEmoji, getTypeLabel, haptic } from '@/lib/utils'
import { Item, completeItem, deleteItem, sendToChat } from '@/api/client'

interface ItemDetailProps {
  item: Item
  open: boolean
  onClose: () => void
}

export default function ItemDetail({ item, open, onClose }: ItemDetailProps) {
  const queryClient = useQueryClient()
  const [showMenu, setShowMenu] = useState(false)

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
                  <span>
                    {formatRelativeDate(item.due_at)}
                    {' '}
                    <span className="text-tg-hint">{formatTime(item.due_at)}</span>
                  </span>
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
                  {item.content || item.original_input}
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
