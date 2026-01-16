import { FolderOpen, Inbox, Search, CheckSquare, Calendar } from 'lucide-react'
import { cn } from '@/lib/utils'
import { haptic } from '@/lib/utils'

type Tab = 'projects' | 'inbox' | 'search' | 'tasks' | 'calendar'

interface BottomNavProps {
  currentTab: Tab
  onTabChange: (tab: Tab) => void
}

const tabs: { id: Tab; label: string; icon: typeof Inbox }[] = [
  { id: 'projects', label: 'Проекты', icon: FolderOpen },
  { id: 'inbox', label: 'Входящие', icon: Inbox },
  { id: 'search', label: 'Поиск', icon: Search },
  { id: 'tasks', label: 'Задачи', icon: CheckSquare },
  { id: 'calendar', label: 'Календарь', icon: Calendar },
]

export default function BottomNav({ currentTab, onTabChange }: BottomNavProps) {
  const handleTabClick = (tab: Tab) => {
    haptic('light')
    onTabChange(tab)
  }

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-50 bg-tg-bg border-t border-tg-secondary-bg bottom-nav">
      <div className="flex items-center justify-around py-2">
        {tabs.map((tab) => {
          const Icon = tab.icon
          const isActive = currentTab === tab.id

          return (
            <button
              key={tab.id}
              onClick={() => handleTabClick(tab.id)}
              className={cn(
                'flex flex-col items-center justify-center min-w-[64px] py-1 px-2 rounded-lg transition-colors',
                isActive
                  ? 'text-primary'
                  : 'text-tg-hint hover:text-tg-text'
              )}
            >
              <Icon
                size={24}
                strokeWidth={isActive ? 2.5 : 2}
                className="mb-0.5"
              />
              <span className="text-[10px] font-medium">{tab.label}</span>
            </button>
          )
        })}
      </div>
    </nav>
  )
}
