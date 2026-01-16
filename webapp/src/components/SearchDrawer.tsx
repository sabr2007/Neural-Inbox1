import { useState, useEffect, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Drawer } from 'vaul'
import { Search, X, Loader2 } from 'lucide-react'
import { cn, haptic } from '@/lib/utils'
import { searchItems, Item } from '@/api/client'
import ItemCard from './ItemCard'
import ItemDetail from './ItemDetail'

interface SearchDrawerProps {
  open: boolean
  onClose: () => void
}

export default function SearchDrawer({ open, onClose }: SearchDrawerProps) {
  const [query, setQuery] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')
  const [selectedItem, setSelectedItem] = useState<Item | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // Debounce search query
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQuery(query)
    }, 300)
    return () => clearTimeout(timer)
  }, [query])

  // Focus input when drawer opens
  useEffect(() => {
    if (open) {
      setTimeout(() => {
        inputRef.current?.focus()
      }, 100)
    } else {
      setQuery('')
      setDebouncedQuery('')
    }
  }, [open])

  const { data, isLoading, isFetching } = useQuery({
    queryKey: ['search', debouncedQuery],
    queryFn: () => searchItems(debouncedQuery, { limit: 30 }),
    enabled: debouncedQuery.length >= 2,
  })

  const handleItemClick = (item: Item) => {
    haptic('light')
    setSelectedItem(item)
  }

  const handleClear = () => {
    setQuery('')
    setDebouncedQuery('')
    inputRef.current?.focus()
  }

  const results = data?.items || []
  const showResults = debouncedQuery.length >= 2
  const isSearching = isLoading || isFetching

  return (
    <>
      <Drawer.Root open={open} onOpenChange={(o) => !o && onClose()}>
        <Drawer.Portal>
          <Drawer.Overlay className="fixed inset-0 bg-black/50 z-50" />
          <Drawer.Content className="fixed inset-0 z-50 bg-tg-bg flex flex-col">
            {/* Header with search input */}
            <div className="sticky top-0 bg-tg-bg border-b border-tg-secondary-bg safe-area-top z-10">
              {/* Handle */}
              <div className="flex justify-center py-2">
                <div className="w-10 h-1 bg-tg-hint/30 rounded-full" />
              </div>

              {/* Search input */}
              <div className="px-4 pb-3">
                <div className="relative">
                  <Search
                    size={20}
                    className={cn(
                      'absolute left-3 top-1/2 -translate-y-1/2',
                      isSearching ? 'text-primary' : 'text-tg-hint'
                    )}
                  />
                  <input
                    ref={inputRef}
                    type="text"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="Поиск..."
                    className="w-full pl-10 pr-10 py-3 bg-tg-secondary-bg rounded-xl text-tg-text placeholder:text-tg-hint focus:outline-none focus:ring-2 focus:ring-primary/50"
                  />
                  {query && (
                    <button
                      onClick={handleClear}
                      className="absolute right-3 top-1/2 -translate-y-1/2 p-1 rounded-full hover:bg-tg-hint/20"
                    >
                      <X size={18} className="text-tg-hint" />
                    </button>
                  )}
                </div>
              </div>
            </div>

            {/* Results */}
            <div className="flex-1 overflow-auto">
              {!showResults ? (
                <div className="flex flex-col items-center justify-center py-16 text-tg-hint">
                  <Search size={48} className="mb-4 opacity-50" />
                  <p className="text-lg">Семантический поиск</p>
                  <p className="text-sm mt-1">Введите минимум 2 символа</p>
                </div>
              ) : isSearching && results.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-16">
                  <Loader2 size={32} className="text-primary animate-spin" />
                  <p className="text-tg-hint mt-4">Ищем...</p>
                </div>
              ) : results.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-16 text-tg-hint">
                  <p className="text-lg">Ничего не найдено</p>
                  <p className="text-sm mt-1">Попробуйте другой запрос</p>
                </div>
              ) : (
                <div>
                  <div className="px-4 py-2 text-sm text-tg-hint">
                    Найдено: {data?.total || results.length}
                  </div>
                  {results.map((item) => (
                    <ItemCard
                      key={item.id}
                      item={item}
                      onClick={() => handleItemClick(item)}
                    />
                  ))}
                </div>
              )}
            </div>

            {/* Close button */}
            <div className="sticky bottom-0 p-4 bg-tg-bg border-t border-tg-secondary-bg safe-area-bottom">
              <button
                onClick={onClose}
                className="w-full py-3 bg-tg-secondary-bg text-tg-text rounded-xl font-medium hover:bg-tg-hint/20 transition-colors"
              >
                Закрыть
              </button>
            </div>
          </Drawer.Content>
        </Drawer.Portal>
      </Drawer.Root>

      {/* Item detail drawer */}
      {selectedItem && (
        <ItemDetail
          item={selectedItem}
          open={!!selectedItem}
          onClose={() => setSelectedItem(null)}
        />
      )}
    </>
  )
}
