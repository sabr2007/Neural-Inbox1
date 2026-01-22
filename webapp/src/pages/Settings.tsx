import { useState, useEffect, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeft, Globe, Bell, Moon, ChevronDown, ChevronRight,
  MessageSquare, FileText, Search, RefreshCw, Link2, Mic
} from 'lucide-react'
import {
  fetchUserSettings,
  updateUserSettings,
  UserSettingsResponse,
  NotificationSettings
} from '../api/client'

// Common timezones grouped by region
const TIMEZONES = [
  { group: 'Europe', zones: ['Europe/Moscow', 'Europe/London', 'Europe/Paris', 'Europe/Berlin', 'Europe/Kiev', 'Europe/Minsk'] },
  { group: 'Asia', zones: ['Asia/Almaty', 'Asia/Tashkent', 'Asia/Dubai', 'Asia/Singapore', 'Asia/Tokyo', 'Asia/Shanghai', 'Asia/Kolkata'] },
  { group: 'America', zones: ['America/New_York', 'America/Los_Angeles', 'America/Chicago', 'America/Denver'] },
  { group: 'Pacific', zones: ['Pacific/Auckland', 'Australia/Sydney'] },
]

interface SettingsProps {
  onBack: () => void
}

export default function Settings({ onBack }: SettingsProps) {
  const queryClient = useQueryClient()
  const [timezoneOpen, setTimezoneOpen] = useState(false)
  const [helpSection, setHelpSection] = useState<string | null>(null)

  const { data: settings, isLoading } = useQuery({
    queryKey: ['user-settings'],
    queryFn: fetchUserSettings,
  })

  const mutation = useMutation({
    mutationFn: updateUserSettings,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['user-settings'] })
    },
  })

  // Auto-detect browser timezone
  const detectedTimezone = useMemo(() => {
    try {
      return Intl.DateTimeFormat().resolvedOptions().timeZone
    } catch {
      return 'Asia/Almaty'
    }
  }, [])

  const handleTimezoneChange = (tz: string) => {
    mutation.mutate({ timezone: tz })
    setTimezoneOpen(false)
  }

  const handleAutoDetect = () => {
    handleTimezoneChange(detectedTimezone)
  }

  const handleNotificationChange = (key: keyof NotificationSettings, value: boolean | string) => {
    if (!settings) return
    const newNotifications = {
      ...settings.settings.notifications,
      [key]: value,
    }
    mutation.mutate({ notifications: newNotifications })
  }

  // Get timezone offset string
  const getTimezoneOffset = (tz: string) => {
    try {
      const now = new Date()
      const formatter = new Intl.DateTimeFormat('en', {
        timeZone: tz,
        timeZoneName: 'shortOffset',
      })
      const parts = formatter.formatToParts(now)
      const offset = parts.find(p => p.type === 'timeZoneName')?.value || ''
      return offset.replace('GMT', 'UTC')
    } catch {
      return ''
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  const notifications = settings?.settings.notifications || {
    task_reminders: true,
    daily_digest: true,
    weekly_review: false,
    dnd_enabled: false,
    dnd_start: '22:00',
    dnd_end: '08:00',
  }

  return (
    <div className="pb-4">
      {/* Header */}
      <div className="sticky top-0 z-10 bg-tg-bg border-b border-tg-secondary-bg">
        <div className="px-4 py-3 flex items-center gap-3">
          <button onClick={onBack} className="p-1 -ml-1 text-tg-hint hover:text-tg-text">
            <ArrowLeft className="w-5 h-5" />
          </button>
          <h1 className="text-lg font-semibold text-tg-text">Settings</h1>
        </div>
      </div>

      <div className="px-4 space-y-6 mt-4">
        {/* Timezone Section */}
        <section>
          <h2 className="text-sm font-medium text-tg-hint uppercase tracking-wide mb-3 flex items-center gap-2">
            <Globe className="w-4 h-4" />
            Timezone
          </h2>

          <div className="bg-tg-secondary-bg rounded-xl overflow-hidden">
            <button
              onClick={() => setTimezoneOpen(!timezoneOpen)}
              className="w-full px-4 py-3 flex items-center justify-between text-left"
            >
              <div>
                <div className="text-tg-text font-medium">{settings?.timezone || 'Asia/Almaty'}</div>
                <div className="text-sm text-tg-hint">{getTimezoneOffset(settings?.timezone || 'Asia/Almaty')}</div>
              </div>
              <ChevronDown className={`w-5 h-5 text-tg-hint transition-transform ${timezoneOpen ? 'rotate-180' : ''}`} />
            </button>

            {timezoneOpen && (
              <div className="border-t border-tg-bg">
                {/* Auto-detect button */}
                <button
                  onClick={handleAutoDetect}
                  className="w-full px-4 py-3 text-left text-primary hover:bg-tg-bg flex items-center justify-between"
                >
                  <span>Auto-detect ({detectedTimezone})</span>
                  <span className="text-xs text-tg-hint">{getTimezoneOffset(detectedTimezone)}</span>
                </button>

                {/* Timezone groups */}
                <div className="max-h-64 overflow-y-auto">
                  {TIMEZONES.map(group => (
                    <div key={group.group}>
                      <div className="px-4 py-2 text-xs font-medium text-tg-hint bg-tg-bg">
                        {group.group}
                      </div>
                      {group.zones.map(tz => (
                        <button
                          key={tz}
                          onClick={() => handleTimezoneChange(tz)}
                          className={`w-full px-4 py-2.5 text-left hover:bg-tg-bg flex items-center justify-between ${
                            settings?.timezone === tz ? 'text-primary' : 'text-tg-text'
                          }`}
                        >
                          <span>{tz.split('/')[1]?.replace('_', ' ') || tz}</span>
                          <span className="text-xs text-tg-hint">{getTimezoneOffset(tz)}</span>
                        </button>
                      ))}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </section>

        {/* Notifications Section */}
        <section>
          <h2 className="text-sm font-medium text-tg-hint uppercase tracking-wide mb-3 flex items-center gap-2">
            <Bell className="w-4 h-4" />
            Notifications
          </h2>

          <div className="bg-tg-secondary-bg rounded-xl overflow-hidden divide-y divide-tg-bg">
            {/* Task reminders */}
            <label className="flex items-center justify-between px-4 py-3 cursor-pointer">
              <span className="text-tg-text">Task reminders</span>
              <input
                type="checkbox"
                checked={notifications.task_reminders}
                onChange={(e) => handleNotificationChange('task_reminders', e.target.checked)}
                className="w-5 h-5 rounded accent-primary"
              />
            </label>

            {/* Daily digest */}
            <label className="flex items-center justify-between px-4 py-3 cursor-pointer">
              <span className="text-tg-text">Daily digest</span>
              <input
                type="checkbox"
                checked={notifications.daily_digest}
                onChange={(e) => handleNotificationChange('daily_digest', e.target.checked)}
                className="w-5 h-5 rounded accent-primary"
              />
            </label>

            {/* Weekly review */}
            <label className="flex items-center justify-between px-4 py-3 cursor-pointer">
              <span className="text-tg-text">Weekly review</span>
              <input
                type="checkbox"
                checked={notifications.weekly_review}
                onChange={(e) => handleNotificationChange('weekly_review', e.target.checked)}
                className="w-5 h-5 rounded accent-primary"
              />
            </label>
          </div>
        </section>

        {/* Do Not Disturb Section */}
        <section>
          <h2 className="text-sm font-medium text-tg-hint uppercase tracking-wide mb-3 flex items-center gap-2">
            <Moon className="w-4 h-4" />
            Do Not Disturb
          </h2>

          <div className="bg-tg-secondary-bg rounded-xl overflow-hidden divide-y divide-tg-bg">
            {/* DND toggle */}
            <label className="flex items-center justify-between px-4 py-3 cursor-pointer">
              <span className="text-tg-text">Enable quiet hours</span>
              <input
                type="checkbox"
                checked={notifications.dnd_enabled}
                onChange={(e) => handleNotificationChange('dnd_enabled', e.target.checked)}
                className="w-5 h-5 rounded accent-primary"
              />
            </label>

            {/* Time range */}
            {notifications.dnd_enabled && (
              <div className="px-4 py-3 flex items-center gap-4">
                <div className="flex-1">
                  <label className="text-sm text-tg-hint">From</label>
                  <input
                    type="time"
                    value={notifications.dnd_start}
                    onChange={(e) => handleNotificationChange('dnd_start', e.target.value)}
                    className="w-full mt-1 px-3 py-2 bg-tg-bg rounded-lg text-tg-text"
                  />
                </div>
                <div className="flex-1">
                  <label className="text-sm text-tg-hint">To</label>
                  <input
                    type="time"
                    value={notifications.dnd_end}
                    onChange={(e) => handleNotificationChange('dnd_end', e.target.value)}
                    className="w-full mt-1 px-3 py-2 bg-tg-bg rounded-lg text-tg-text"
                  />
                </div>
              </div>
            )}
          </div>
        </section>

        {/* Help Section */}
        <section>
          <h2 className="text-sm font-medium text-tg-hint uppercase tracking-wide mb-3 flex items-center gap-2">
            <MessageSquare className="w-4 h-4" />
            How to use
          </h2>

          <div className="bg-tg-secondary-bg rounded-xl overflow-hidden divide-y divide-tg-bg">
            {/* Types of records */}
            <HelpItem
              icon={<FileText className="w-5 h-5" />}
              title="Types of records"
              isOpen={helpSection === 'types'}
              onClick={() => setHelpSection(helpSection === 'types' ? null : 'types')}
            >
              <div className="space-y-2 text-sm text-tg-hint">
                <p><strong className="text-tg-text">Task</strong> - actionable items with optional due dates and reminders</p>
                <p><strong className="text-tg-text">Idea</strong> - thoughts and concepts for later</p>
                <p><strong className="text-tg-text">Note</strong> - general information and notes</p>
                <p><strong className="text-tg-text">Resource</strong> - links, files, and references</p>
                <p><strong className="text-tg-text">Contact</strong> - people and their details</p>
              </div>
            </HelpItem>

            {/* Voice messages */}
            <HelpItem
              icon={<Mic className="w-5 h-5" />}
              title="Voice messages"
              isOpen={helpSection === 'voice'}
              onClick={() => setHelpSection(helpSection === 'voice' ? null : 'voice')}
            >
              <div className="text-sm text-tg-hint">
                <p>Send voice messages to the bot and they will be automatically transcribed and processed.</p>
                <p className="mt-2">The AI will extract tasks, ideas, and other information from your speech.</p>
              </div>
            </HelpItem>

            {/* Smart search */}
            <HelpItem
              icon={<Search className="w-5 h-5" />}
              title="Smart search"
              isOpen={helpSection === 'search'}
              onClick={() => setHelpSection(helpSection === 'search' ? null : 'search')}
            >
              <div className="text-sm text-tg-hint">
                <p>Search uses semantic understanding - it finds related items even if exact words don't match.</p>
                <p className="mt-2">Try searching for concepts like "meetings this week" or "project ideas".</p>
              </div>
            </HelpItem>

            {/* Recurring tasks */}
            <HelpItem
              icon={<RefreshCw className="w-5 h-5" />}
              title="Recurring tasks"
              isOpen={helpSection === 'recurring'}
              onClick={() => setHelpSection(helpSection === 'recurring' ? null : 'recurring')}
            >
              <div className="text-sm text-tg-hint">
                <p>Tasks can repeat daily, weekly, or monthly. When you complete a recurring task, the next instance is automatically created.</p>
                <p className="mt-2">Set recurrence when creating or editing a task.</p>
              </div>
            </HelpItem>

            {/* Links and documents */}
            <HelpItem
              icon={<Link2 className="w-5 h-5" />}
              title="Links and documents"
              isOpen={helpSection === 'links'}
              onClick={() => setHelpSection(helpSection === 'links' ? null : 'links')}
            >
              <div className="text-sm text-tg-hint">
                <p>Send links and they will be automatically fetched and summarized.</p>
                <p className="mt-2">PDFs and images are processed with AI to extract text and key information.</p>
              </div>
            </HelpItem>
          </div>
        </section>
      </div>
    </div>
  )
}

// Help accordion item component
function HelpItem({
  icon,
  title,
  isOpen,
  onClick,
  children
}: {
  icon: React.ReactNode
  title: string
  isOpen: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <div>
      <button
        onClick={onClick}
        className="w-full px-4 py-3 flex items-center gap-3 text-left"
      >
        <span className="text-tg-hint">{icon}</span>
        <span className="flex-1 text-tg-text">{title}</span>
        <ChevronRight className={`w-5 h-5 text-tg-hint transition-transform ${isOpen ? 'rotate-90' : ''}`} />
      </button>
      {isOpen && (
        <div className="px-4 pb-3 pl-12">
          {children}
        </div>
      )}
    </div>
  )
}
