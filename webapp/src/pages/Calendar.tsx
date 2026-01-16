import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { format, startOfMonth, endOfMonth, eachDayOfInterval, isSameDay, isToday, addMonths, subMonths } from 'date-fns'
import { ru } from 'date-fns/locale'
import { cn, haptic } from '@/lib/utils'
import { fetchCalendarTasks, Item } from '@/api/client'
import ItemCard from '@/components/ItemCard'
import ItemDetail from '@/components/ItemDetail'
import { Skeleton } from '@/components/Skeleton'

const WEEKDAYS = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']

export default function Calendar() {
  const [currentMonth, setCurrentMonth] = useState(new Date())
  const [selectedDate, setSelectedDate] = useState<Date | null>(null)
  const [selectedItem, setSelectedItem] = useState<Item | null>(null)

  const year = currentMonth.getFullYear()
  const month = currentMonth.getMonth() + 1

  const { data, isLoading } = useQuery({
    queryKey: ['calendar', year, month],
    queryFn: () => fetchCalendarTasks(year, month),
  })

  // Create a map of date -> task count
  const taskCountMap = useMemo(() => {
    const map = new Map<string, number>()
    data?.days.forEach((day) => {
      map.set(day.date, day.count)
    })
    return map
  }, [data?.days])

  // Get tasks for selected date
  const selectedDateTasks = useMemo(() => {
    if (!selectedDate || !data?.tasks) return []
    return data.tasks.filter((task) => {
      if (!task.due_at) return false
      return isSameDay(new Date(task.due_at), selectedDate)
    })
  }, [selectedDate, data?.tasks])

  // Generate calendar days
  const calendarDays = useMemo(() => {
    const start = startOfMonth(currentMonth)
    const end = endOfMonth(currentMonth)
    const days = eachDayOfInterval({ start, end })

    // Pad start with empty cells (Monday = 0)
    const startDay = start.getDay()
    const paddingStart = startDay === 0 ? 6 : startDay - 1
    const padding = Array(paddingStart).fill(null)

    return [...padding, ...days]
  }, [currentMonth])

  const handlePrevMonth = () => {
    haptic('light')
    setCurrentMonth(subMonths(currentMonth, 1))
    setSelectedDate(null)
  }

  const handleNextMonth = () => {
    haptic('light')
    setCurrentMonth(addMonths(currentMonth, 1))
    setSelectedDate(null)
  }

  const handleDateClick = (date: Date) => {
    haptic('selection')
    setSelectedDate(isSameDay(date, selectedDate || new Date(0)) ? null : date)
  }

  const handleItemClick = (item: Item) => {
    haptic('light')
    setSelectedItem(item)
  }

  return (
    <div className="flex flex-col h-full">
      {/* Month navigation */}
      <div className="sticky top-0 z-10 bg-tg-bg border-b border-tg-secondary-bg px-4 py-3">
        <div className="flex items-center justify-between">
          <button
            onClick={handlePrevMonth}
            className="p-2 rounded-full hover:bg-tg-secondary-bg"
          >
            <ChevronLeft size={20} className="text-tg-hint" />
          </button>
          <h2 className="text-lg font-semibold text-tg-text capitalize">
            {format(currentMonth, 'LLLL yyyy', { locale: ru })}
          </h2>
          <button
            onClick={handleNextMonth}
            className="p-2 rounded-full hover:bg-tg-secondary-bg"
          >
            <ChevronRight size={20} className="text-tg-hint" />
          </button>
        </div>
      </div>

      {/* Calendar grid */}
      <div className="px-2 py-3">
        {/* Weekday headers */}
        <div className="grid grid-cols-7 mb-2">
          {WEEKDAYS.map((day) => (
            <div
              key={day}
              className="text-center text-xs font-medium text-tg-hint py-1"
            >
              {day}
            </div>
          ))}
        </div>

        {/* Days grid */}
        {isLoading ? (
          <div className="grid grid-cols-7 gap-1">
            {Array.from({ length: 35 }).map((_, i) => (
              <Skeleton key={i} className="aspect-square rounded-lg" />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-7 gap-1">
            {calendarDays.map((day, index) => {
              if (!day) {
                return <div key={`empty-${index}`} />
              }

              const dateStr = format(day, 'yyyy-MM-dd')
              const taskCount = taskCountMap.get(dateStr) || 0
              const isSelected = selectedDate && isSameDay(day, selectedDate)
              const isTodayDate = isToday(day)

              return (
                <button
                  key={dateStr}
                  onClick={() => handleDateClick(day)}
                  className={cn(
                    'aspect-square rounded-lg flex flex-col items-center justify-center relative',
                    'transition-colors',
                    isSelected
                      ? 'bg-primary text-white'
                      : isTodayDate
                      ? 'bg-primary/10 text-primary'
                      : 'hover:bg-tg-secondary-bg text-tg-text'
                  )}
                >
                  <span className="text-sm font-medium">
                    {format(day, 'd')}
                  </span>
                  {taskCount > 0 && (
                    <div
                      className={cn(
                        'absolute bottom-1 w-1.5 h-1.5 rounded-full',
                        isSelected ? 'bg-white' : 'bg-primary'
                      )}
                    />
                  )}
                </button>
              )
            })}
          </div>
        )}
      </div>

      {/* Selected date tasks */}
      {selectedDate && (
        <div className="flex-1 border-t border-tg-secondary-bg overflow-auto">
          <div className="px-4 py-2 bg-tg-secondary-bg/50">
            <span className="text-sm font-medium text-tg-text">
              {format(selectedDate, 'd MMMM', { locale: ru })}
            </span>
            <span className="text-sm text-tg-hint ml-2">
              {selectedDateTasks.length} {selectedDateTasks.length === 1 ? 'задача' : 'задач'}
            </span>
          </div>

          {selectedDateTasks.length === 0 ? (
            <div className="py-8 text-center text-tg-hint">
              Нет задач на этот день
            </div>
          ) : (
            <div>
              {selectedDateTasks.map((task) => (
                <ItemCard
                  key={task.id}
                  item={task}
                  onClick={() => handleItemClick(task)}
                />
              ))}
            </div>
          )}
        </div>
      )}

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
