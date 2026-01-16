import { ReactNode } from 'react'
import BottomNav from './BottomNav'

type Tab = 'projects' | 'inbox' | 'search' | 'tasks' | 'calendar'

interface LayoutProps {
  children: ReactNode
  currentTab: Tab
  onTabChange: (tab: Tab) => void
}

export default function Layout({ children, currentTab, onTabChange }: LayoutProps) {
  return (
    <div className="min-h-screen bg-tg-bg flex flex-col">
      {/* Header */}
      <header className="sticky top-0 z-40 bg-tg-bg border-b border-tg-secondary-bg safe-area-top">
        <div className="px-4 py-3 flex items-center justify-between">
          <h1 className="text-lg font-semibold text-tg-text">Neural Inbox</h1>
        </div>
      </header>

      {/* Main content */}
      <main className="flex-1 overflow-auto pb-20">
        {children}
      </main>

      {/* Bottom navigation */}
      <BottomNav currentTab={currentTab} onTabChange={onTabChange} />
    </div>
  )
}
