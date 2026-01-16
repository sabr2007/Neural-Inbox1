import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { RefreshCw } from 'lucide-react'
import { cn, haptic } from '@/lib/utils'
import { fetchItems, Item } from '@/api/client'
import ItemCard from '@/components/ItemCard'
import { ItemListSkeleton } from '@/components/Skeleton'
import ItemDetail from '@/components/ItemDetail'

type FilterType = 'all' | 'task' | 'note' | 'idea' | 'resource' | 'contact'

const filters: { id: FilterType; label: string }[] = [
  { id: 'all', label: 'Все' },
  { id: 'task', label: 'Задачи' },
  { id: 'note', label: 'Заметки' },
  { id: 'idea', label: 'Идеи' },
  { id: 'resource', label: 'Ресурсы' },
  { id: 'contact', label: 'Контакты' },
]

export default function Inbox() {
  const [activeFilter, setActiveFilter] = useState<FilterType>('all')
  const [selectedItem, setSelectedItem] = useState<Item | null>(null)

  const { data, isLoading, isRefetching, refetch } = useQuery({
    queryKey: ['items', activeFilter],
    queryFn: () =>
      fetchItems({
        type: activeFilter === 'all' ? undefined : activeFilter,
        limit: 50,
      }),
    refetchInterval: 5000, // Poll every 5 seconds for processing items
  })

  const handleFilterChange = (filter: FilterType) => {
    haptic('selection')
    setActiveFilter(filter)
  }

  const handleRefresh = () => {
    haptic('light')
    refetch()
  }

  const handleItemClick = (item: Item) => {
    haptic('light')
    setSelectedItem(item)
  }

  const items = data?.items || []

  return (
    <div className="flex flex-col h-full">
      {/* Filter chips */}
      <div className="sticky top-0 z-10 bg-tg-bg border-b border-tg-secondary-bg">
        <div className="flex items-center gap-2 px-4 py-2 overflow-x-auto scrollbar-hide">
          {filters.map((filter) => (
            <button
              key={filter.id}
              onClick={() => handleFilterChange(filter.id)}
              className={cn(
                'flex-shrink-0 px-3 py-1.5 rounded-full text-sm font-medium transition-colors',
                activeFilter === filter.id
                  ? 'bg-primary text-white'
                  : 'bg-tg-secondary-bg text-tg-text hover:bg-opacity-80'
              )}
            >
              {filter.label}
            </button>
          ))}

          {/* Refresh button */}
          <button
            onClick={handleRefresh}
            disabled={isRefetching}
            className="flex-shrink-0 p-1.5 rounded-full text-tg-hint hover:text-tg-text ml-auto"
          >
            <RefreshCw
              size={18}
              className={cn(isRefetching && 'animate-spin')}
            />
          </button>
        </div>
      </div>

      {/* Items list */}
      <div className="flex-1 overflow-auto">
        {isLoading ? (
          <ItemListSkeleton count={8} />
        ) : items.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-tg-hint">
            <p className="text-lg">Пусто</p>
            <p className="text-sm mt-1">Отправьте что-нибудь боту</p>
          </div>
        ) : (
          <div>
            {items.map((item) => (
              <ItemCard
                key={item.id}
                item={item}
                onClick={() => handleItemClick(item)}
              />
            ))}
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
