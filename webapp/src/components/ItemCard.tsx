import { useState } from 'react'
import { Check, Paperclip, Loader2 } from 'lucide-react'
import { cn, formatRelativeDate, getTypeEmoji, haptic } from '@/lib/utils'
import { Item, completeItem } from '@/api/client'
import { useMutation, useQueryClient } from '@tanstack/react-query'

interface ItemCardProps {
  item: Item
  onClick?: () => void
}

export default function ItemCard({ item, onClick }: ItemCardProps) {
  const queryClient = useQueryClient()
  const [isCompleting, setIsCompleting] = useState(false)

  const completeMutation = useMutation({
    mutationFn: () => completeItem(item.id),
    onMutate: () => {
      setIsCompleting(true)
      haptic('success')
    },
    onSuccess: () => {
      // Invalidate relevant queries
      queryClient.invalidateQueries({ queryKey: ['items'] })
      queryClient.invalidateQueries({ queryKey: ['tasks'] })
    },
    onSettled: () => {
      setIsCompleting(false)
    },
  })

  const handleCheckClick = (e: React.MouseEvent) => {
    e.stopPropagation()
    if (item.type === 'task' && item.status !== 'done') {
      completeMutation.mutate()
    }
  }

  const isProcessing = item.status === 'processing'
  const isCompleted = item.status === 'done'
  const hasAttachment = !!item.attachment_file_id

  return (
    <div
      onClick={onClick}
      className={cn(
        'px-4 py-3 bg-tg-bg border-b border-tg-secondary-bg',
        'active:bg-tg-secondary-bg transition-colors cursor-pointer',
        isCompleted && 'opacity-60'
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
      </div>
    </div>
  )
}
