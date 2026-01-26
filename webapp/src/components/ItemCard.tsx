import { useState } from 'react'
import { Check, Paperclip, Loader2, Trash2, Repeat } from 'lucide-react'
import { cn, formatRelativeDate, getTypeEmoji, haptic } from '@/lib/utils'
import { Item, completeItem, deleteItem } from '@/api/client'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useToast } from '@/hooks/useToast'

interface ItemCardProps {
  item: Item
  onClick?: () => void
}

// Helper to update item in cache across all query keys
function updateItemInCache(
  queryClient: ReturnType<typeof useQueryClient>,
  itemId: number,
  updater: (item: Item) => Item | null // return null to remove
) {
  const queryKeys = [['items'], ['tasks'], ['calendar'], ['projects']]
  queryKeys.forEach((queryKey) => {
    queryClient.setQueriesData<{ items?: Item[] } | Item[]>(
      { queryKey },
      (old) => {
        if (!old) return old
        // Handle { items: Item[] } structure
        if ('items' in old && Array.isArray(old.items)) {
          const updated = old.items
            .map((i) => (i.id === itemId ? updater(i) : i))
            .filter((i): i is Item => i !== null)
          return { ...old, items: updated }
        }
        // Handle Item[] structure
        if (Array.isArray(old)) {
          return old
            .map((i) => (i.id === itemId ? updater(i) : i))
            .filter((i): i is Item => i !== null)
        }
        return old
      }
    )
  })
}

export default function ItemCard({ item, onClick }: ItemCardProps) {
  const queryClient = useQueryClient()
  const { showError } = useToast()
  const [isCompleting, setIsCompleting] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)

  const completeMutation = useMutation({
    mutationFn: () => completeItem(item.id),
    onMutate: async () => {
      setIsCompleting(true)
      haptic('success')
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: ['items'] })
      await queryClient.cancelQueries({ queryKey: ['tasks'] })
      // Optimistically update to 'done'
      updateItemInCache(queryClient, item.id, (i) => ({ ...i, status: 'done' as const }))
    },
    onError: (error) => {
      console.error('Failed to complete item:', error)
      haptic('error')
      showError('Не удалось отметить как выполненное')
      // Rollback
      updateItemInCache(queryClient, item.id, (i) => ({ ...i, status: item.status }))
    },
    onSettled: () => {
      setIsCompleting(false)
      queryClient.invalidateQueries({ queryKey: ['items'] })
      queryClient.invalidateQueries({ queryKey: ['tasks'] })
      queryClient.invalidateQueries({ queryKey: ['calendar'] })
      queryClient.invalidateQueries({ queryKey: ['projects'] })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: () => deleteItem(item.id),
    onMutate: async () => {
      setIsDeleting(true)
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: ['items'] })
      await queryClient.cancelQueries({ queryKey: ['tasks'] })
      // Optimistically remove item
      updateItemInCache(queryClient, item.id, () => null)
    },
    onSuccess: () => {
      haptic('success')
    },
    onError: (error) => {
      console.error('Failed to delete item:', error)
      haptic('error')
      showError('Не удалось удалить')
      // Note: Can't easily rollback a delete, rely on invalidation
    },
    onSettled: () => {
      setIsDeleting(false)
      queryClient.invalidateQueries({ queryKey: ['items'] })
      queryClient.invalidateQueries({ queryKey: ['tasks'] })
      queryClient.invalidateQueries({ queryKey: ['calendar'] })
      queryClient.invalidateQueries({ queryKey: ['projects'] })
    },
  })

  const handleCheckClick = (e: React.MouseEvent) => {
    e.stopPropagation()
    if (item.type === 'task' && item.status !== 'done') {
      completeMutation.mutate()
    }
  }

  const handleDeleteClick = (e: React.MouseEvent) => {
    e.stopPropagation()
    deleteMutation.mutate()
  }

  const isProcessing = item.status === 'processing'
  const isCompleted = item.status === 'done'
  const hasAttachment = !!item.attachment_file_id
  const isRecurring = !!item.recurrence

  return (
    <div
      onClick={onClick}
      className={cn(
        'px-4 py-3 bg-tg-bg border-b border-tg-secondary-bg',
        'active:bg-tg-secondary-bg transition-colors cursor-pointer',
        isCompleted && 'opacity-60',
        isDeleting && 'fade-out'
      )}
    >
      <div className="flex items-start gap-3">
        {/* Checkbox for tasks */}
        {item.type === 'task' ? (
          <button
            onClick={handleCheckClick}
            disabled={isCompleting || isProcessing}
            className={cn(
              'flex-shrink-0 w-6 h-6 rounded-full border-2 flex items-center justify-center mt-0.5',
              'transition-colors',
              isCompleted
                ? 'bg-primary border-primary text-white'
                : 'border-tg-hint hover:border-primary'
            )}
          >
            {isCompleting ? (
              <Loader2 size={14} className="animate-spin" />
            ) : isCompleted ? (
              <Check size={14} />
            ) : null}
          </button>
        ) : (
          <span className="flex-shrink-0 text-lg mt-0.5">
            {getTypeEmoji(item.type)}
          </span>
        )}

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h3
              className={cn(
                'font-medium text-tg-text truncate',
                isCompleted && 'line-through'
              )}
            >
              {item.title}
            </h3>
            {isRecurring && (
              <Repeat size={14} className="flex-shrink-0 text-primary" title="Повторяющаяся" />
            )}
            {hasAttachment && (
              <Paperclip size={14} className="flex-shrink-0 text-tg-hint" />
            )}
            {isProcessing && (
              <Loader2 size={14} className="flex-shrink-0 text-primary animate-spin" />
            )}
          </div>

          {/* Meta info */}
          <div className="flex items-center gap-2 mt-1 text-sm text-tg-hint">
            {item.due_at && (
              <span className={cn(
                new Date(item.due_at) < new Date() && !isCompleted && 'text-red-500'
              )}>
                {formatRelativeDate(item.due_at)}
              </span>
            )}
            {item.tags && item.tags.length > 0 && (
              <span className="truncate">
                {item.tags.slice(0, 2).join(' ')}
              </span>
            )}
          </div>
        </div>

        {/* Delete button for completed tasks */}
        {isCompleted && (
          <button
            onClick={handleDeleteClick}
            disabled={isDeleting}
            className="flex-shrink-0 p-2 rounded-full text-red-500 hover:bg-red-500/10 transition-colors"
          >
            {isDeleting ? (
              <Loader2 size={18} className="animate-spin" />
            ) : (
              <Trash2 size={18} />
            )}
          </button>
        )}
      </div>
    </div>
  )
}
