import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { cn, haptic } from '@/lib/utils'
import { fetchTasks, Item } from '@/api/client'
import ItemCard from '@/components/ItemCard'
import ItemDetail from '@/components/ItemDetail'
import { ItemListSkeleton } from '@/components/Skeleton'

export default function Tasks() {
  const [selectedItem, setSelectedItem] = useState<Item | null>(null)
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(new Set())
  const [showCompleted, setShowCompleted] = useState(true)

  const { data, isLoading } = useQuery({
    queryKey: ['tasks', showCompleted],
    queryFn: () => fetchTasks(showCompleted),
  })

  const toggleGroup = (label: string) => {
    haptic('selection')
    setCollapsedGroups((prev) => {
      const next = new Set(prev)
      if (next.has(label)) {
        next.delete(label)
      } else {
        next.add(label)
      }
      return next
    })
  }

  const handleItemClick = (item: Item) => {
    haptic('light')
    setSelectedItem(item)
  }

  const groups = data?.groups || []

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="sticky top-0 z-10 bg-tg-bg border-b border-tg-secondary-bg px-4 py-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-tg-text">Задачи</h2>
          <button
            onClick={() => {
              haptic('selection')
              setShowCompleted(!showCompleted)
            }}
            className={cn(
              'text-sm px-3 py-1 rounded-full transition-colors',
              showCompleted
                ? 'bg-primary text-white'
                : 'bg-tg-secondary-bg text-tg-hint'
            )}
          >
            {showCompleted ? 'Скрыть выполненные' : 'Показать выполненные'}
          </button>
        </div>
      </div>

      {/* Task groups */}
      <div className="flex-1 overflow-auto">
        {isLoading ? (
          <ItemListSkeleton count={8} />
        ) : groups.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-tg-hint">
            <p className="text-lg">Нет задач</p>
            <p className="text-sm mt-1">Отправьте задачу боту</p>
          </div>
        ) : (
          <div>
            {groups.map((group) => {
              const isCollapsed = collapsedGroups.has(group.label)
              const isCompletedGroup = group.label === 'Выполненные'

              return (
                <div key={group.label}>
                  {/* Group header */}
                  <button
                    onClick={() => toggleGroup(group.label)}
                    className="w-full flex items-center justify-between px-4 py-2 bg-tg-secondary-bg/50"
                  >
                    <div className="flex items-center gap-2">
                      {isCollapsed ? (
                        <ChevronRight size={18} className="text-tg-hint" />
                      ) : (
                        <ChevronDown size={18} className="text-tg-hint" />
                      )}
                      <span className={cn(
                        'font-medium',
                        isCompletedGroup ? 'text-tg-hint' : 'text-tg-text'
                      )}>
                        {group.label}
                      </span>
                    </div>
                    <span className="text-sm text-tg-hint">
                      {group.items.length}
                    </span>
                  </button>

                  {/* Group items */}
                  {!isCollapsed && (
                    <div>
                      {group.items.map((item) => (
                        <ItemCard
                          key={item.id}
                          item={item}
                          onClick={() => handleItemClick(item)}
                        />
                      ))}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Item detail drawer */}
      {selectedItem && (
        <ItemDetail
          item={selectedItem}
          open={!!selectedItem}
          onClose={() => setSelectedItem(null)}
        />
      )}
    </div>
  )
}
