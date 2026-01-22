import { useState, useEffect } from 'react'
import Layout from './components/Layout'
import Inbox from './pages/Inbox'
import Tasks from './pages/Tasks'
import Calendar from './pages/Calendar'
import Projects from './pages/Projects'
import ProjectDetail from './pages/ProjectDetail'
import Settings from './pages/Settings'
import SearchDrawer from './components/SearchDrawer'

// Telegram WebApp type declaration
declare global {
  interface Window {
    Telegram: {
      WebApp: {
        ready: () => void
        expand: () => void
        close: () => void
        initData: string
        initDataUnsafe: {
          user?: {
            id: number
            first_name: string
            last_name?: string
            username?: string
            language_code?: string
          }
        }
        themeParams: {
          bg_color?: string
          text_color?: string
          hint_color?: string
          link_color?: string
          button_color?: string
          button_text_color?: string
          secondary_bg_color?: string
        }
        setHeaderColor: (color: string) => void
        setBackgroundColor: (color: string) => void
        enableClosingConfirmation: () => void
        disableClosingConfirmation: () => void
        MainButton: {
          show: () => void
          hide: () => void
          setText: (text: string) => void
          onClick: (callback: () => void) => void
          offClick: (callback: () => void) => void
        }
        BackButton: {
          show: () => void
          hide: () => void
          onClick: (callback: () => void) => void
          offClick: (callback: () => void) => void
        }
        HapticFeedback: {
          impactOccurred: (style: 'light' | 'medium' | 'heavy' | 'rigid' | 'soft') => void
          notificationOccurred: (type: 'error' | 'success' | 'warning') => void
          selectionChanged: () => void
        }
      }
    }
  }
}

type Tab = 'projects' | 'inbox' | 'search' | 'tasks' | 'calendar'
type View =
  | { type: 'tab'; tab: Tab }
  | { type: 'project'; projectId: number }
  | { type: 'settings' }

export default function App() {
  const [view, setView] = useState<View>({ type: 'tab', tab: 'inbox' })
  const [searchOpen, setSearchOpen] = useState(false)
  const [isReady, setIsReady] = useState(false)

  useEffect(() => {
    // Initialize Telegram WebApp
    const tg = window.Telegram?.WebApp
    if (tg) {
      // Call ready() after initial render
      tg.ready()
      tg.expand()

      // Apply theme colors to CSS variables
      const theme = tg.themeParams
      if (theme.bg_color) {
        document.documentElement.style.setProperty('--tg-theme-bg-color', theme.bg_color)
      }
      if (theme.text_color) {
        document.documentElement.style.setProperty('--tg-theme-text-color', theme.text_color)
      }
      if (theme.hint_color) {
        document.documentElement.style.setProperty('--tg-theme-hint-color', theme.hint_color)
      }
      if (theme.secondary_bg_color) {
        document.documentElement.style.setProperty('--tg-theme-secondary-bg-color', theme.secondary_bg_color)
      }
    }

    setIsReady(true)
  }, [])

  const handleTabChange = (tab: Tab) => {
    if (tab === 'search') {
      setSearchOpen(true)
    } else {
      setView({ type: 'tab', tab })
    }
  }

  const handleProjectSelect = (projectId: number) => {
    setView({ type: 'project', projectId })
  }

  const handleBackFromProject = () => {
    setView({ type: 'tab', tab: 'projects' })
  }

  const handleSettingsClick = () => {
    setView({ type: 'settings' })
  }

  const handleBackFromSettings = () => {
    setView({ type: 'tab', tab: 'inbox' })
  }

  // Show skeleton while initializing
  if (!isReady) {
    return (
      <div className="min-h-screen bg-tg-bg flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  const currentTab = view.type === 'tab' ? view.tab : 'projects'

  // Settings page has its own layout
  if (view.type === 'settings') {
    return <Settings onBack={handleBackFromSettings} />
  }

  return (
    <Layout currentTab={currentTab} onTabChange={handleTabChange} onSettingsClick={handleSettingsClick}>
      {view.type === 'project' ? (
        <ProjectDetail projectId={view.projectId} onBack={handleBackFromProject} />
      ) : (
        <>
          {view.tab === 'inbox' && <Inbox />}
          {view.tab === 'tasks' && <Tasks />}
          {view.tab === 'calendar' && <Calendar />}
          {view.tab === 'projects' && <Projects onProjectSelect={handleProjectSelect} />}
        </>
      )}

      <SearchDrawer open={searchOpen} onClose={() => setSearchOpen(false)} />
    </Layout>
  )
}
