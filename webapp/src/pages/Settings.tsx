import { useState, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeft, Globe, Bell, Moon, ChevronDown, ChevronRight,
  MessageSquare, FileText, Search, RefreshCw, Link2, Mic
} from 'lucide-react'
import {
  fetchUserSettings,
  updateUserSettings,
  NotificationSettings,
  UserSettingsResponse
} from '../api/client'
import { useToast } from '../hooks/useToast'

// Часовые пояса по регионам
const TIMEZONES = [
  { group: 'Европа', zones: ['Europe/Moscow', 'Europe/London', 'Europe/Paris', 'Europe/Berlin', 'Europe/Kiev', 'Europe/Minsk'] },
  { group: 'Азия', zones: ['Asia/Almaty', 'Asia/Tashkent', 'Asia/Dubai', 'Asia/Singapore', 'Asia/Tokyo', 'Asia/Shanghai', 'Asia/Kolkata'] },
  { group: 'Америка', zones: ['America/New_York', 'America/Los_Angeles', 'America/Chicago', 'America/Denver'] },
  { group: 'Океания', zones: ['Pacific/Auckland', 'Australia/Sydney'] },
]

// Названия городов на русском
const TIMEZONE_NAMES: Record<string, string> = {
  'Europe/Moscow': 'Москва',
  'Europe/London': 'Лондон',
  'Europe/Paris': 'Париж',
  'Europe/Berlin': 'Берлин',
  'Europe/Kiev': 'Киев',
  'Europe/Minsk': 'Минск',
  'Asia/Almaty': 'Алматы',
  'Asia/Tashkent': 'Ташкент',
  'Asia/Dubai': 'Дубай',
  'Asia/Singapore': 'Сингапур',
  'Asia/Tokyo': 'Токио',
  'Asia/Shanghai': 'Шанхай',
  'Asia/Kolkata': 'Калькутта',
  'America/New_York': 'Нью-Йорк',
  'America/Los_Angeles': 'Лос-Анджелес',
  'America/Chicago': 'Чикаго',
  'America/Denver': 'Денвер',
  'Pacific/Auckland': 'Окленд',
  'Australia/Sydney': 'Сидней',
}

interface SettingsProps {
  onBack: () => void
}

export default function Settings({ onBack }: SettingsProps) {
  const queryClient = useQueryClient()
  const { showError } = useToast()
  const [timezoneOpen, setTimezoneOpen] = useState(false)
  const [helpSection, setHelpSection] = useState<string | null>(null)

  const { data: settings, isLoading } = useQuery({
    queryKey: ['user-settings'],
    queryFn: fetchUserSettings,
  })

  const mutation = useMutation({
    mutationFn: updateUserSettings,
    onMutate: async (newSettings) => {
      await queryClient.cancelQueries({ queryKey: ['user-settings'] })
      const previous = queryClient.getQueryData<UserSettingsResponse>(['user-settings'])
      queryClient.setQueryData<UserSettingsResponse>(['user-settings'], (old) => {
        if (!old) return old
        return {
          ...old,
          timezone: newSettings.timezone ?? old.timezone,
          settings: {
            ...old.settings,
            notifications: newSettings.notifications ?? old.settings.notifications,
          },
        }
      })
      return { previous }
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) {
        queryClient.setQueryData(['user-settings'], context.previous)
      }
      showError('Не удалось сохранить настройки')
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['user-settings'] })
    },
  })

  // Автоопределение часового пояса браузера
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

  // Получить смещение часового пояса
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

  // Получить название часового пояса
  const getTimezoneName = (tz: string) => {
    return TIMEZONE_NAMES[tz] || tz.split('/')[1]?.replace('_', ' ') || tz
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
      {/* Заголовок */}
      <div className="sticky top-0 z-10 bg-tg-bg border-b border-tg-secondary-bg">
        <div className="px-4 py-3 flex items-center gap-3">
          <button onClick={onBack} className="p-1 -ml-1 text-tg-hint hover:text-tg-text">
            <ArrowLeft className="w-5 h-5" />
          </button>
          <h1 className="text-lg font-semibold text-tg-text">Настройки</h1>
        </div>
      </div>

      <div className="px-4 space-y-6 mt-4">
        {/* Часовой пояс */}
        <section>
          <h2 className="text-sm font-medium text-tg-hint uppercase tracking-wide mb-3 flex items-center gap-2">
            <Globe className="w-4 h-4" />
            Часовой пояс
          </h2>

          <div className="bg-tg-secondary-bg rounded-xl overflow-hidden">
            <button
              onClick={() => setTimezoneOpen(!timezoneOpen)}
              className="w-full px-4 py-3 flex items-center justify-between text-left"
            >
              <div>
                <div className="text-tg-text font-medium">{getTimezoneName(settings?.timezone || 'Asia/Almaty')}</div>
                <div className="text-sm text-tg-hint">{getTimezoneOffset(settings?.timezone || 'Asia/Almaty')}</div>
              </div>
              <ChevronDown className={`w-5 h-5 text-tg-hint transition-transform ${timezoneOpen ? 'rotate-180' : ''}`} />
            </button>

            {timezoneOpen && (
              <div className="border-t border-tg-bg">
                {/* Кнопка автоопределения */}
                <button
                  onClick={handleAutoDetect}
                  className="w-full px-4 py-3 text-left text-primary hover:bg-tg-bg flex items-center justify-between"
                >
                  <span>Определить автоматически ({getTimezoneName(detectedTimezone)})</span>
                  <span className="text-xs text-tg-hint">{getTimezoneOffset(detectedTimezone)}</span>
                </button>

                {/* Группы часовых поясов */}
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
                          <span>{getTimezoneName(tz)}</span>
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

        {/* Уведомления */}
        <section>
          <h2 className="text-sm font-medium text-tg-hint uppercase tracking-wide mb-3 flex items-center gap-2">
            <Bell className="w-4 h-4" />
            Уведомления
          </h2>

          <div className="bg-tg-secondary-bg rounded-xl overflow-hidden divide-y divide-tg-bg">
            {/* Напоминания о задачах */}
            <label className={`flex items-center justify-between px-4 py-3 cursor-pointer ${mutation.isPending ? 'opacity-70' : ''}`}>
              <span className="text-tg-text">Напоминания о задачах</span>
              <input
                type="checkbox"
                checked={notifications.task_reminders}
                onChange={(e) => handleNotificationChange('task_reminders', e.target.checked)}
                disabled={mutation.isPending}
                className="w-5 h-5 rounded accent-primary"
              />
            </label>

            {/* Ежедневный дайджест */}
            <label className={`flex items-center justify-between px-4 py-3 cursor-pointer ${mutation.isPending ? 'opacity-70' : ''}`}>
              <span className="text-tg-text">Ежедневный дайджест</span>
              <input
                type="checkbox"
                checked={notifications.daily_digest}
                onChange={(e) => handleNotificationChange('daily_digest', e.target.checked)}
                disabled={mutation.isPending}
                className="w-5 h-5 rounded accent-primary"
              />
            </label>

            {/* Еженедельный обзор */}
            <label className={`flex items-center justify-between px-4 py-3 cursor-pointer ${mutation.isPending ? 'opacity-70' : ''}`}>
              <span className="text-tg-text">Еженедельный обзор</span>
              <input
                type="checkbox"
                checked={notifications.weekly_review}
                onChange={(e) => handleNotificationChange('weekly_review', e.target.checked)}
                disabled={mutation.isPending}
                className="w-5 h-5 rounded accent-primary"
              />
            </label>
          </div>
        </section>

        {/* Не беспокоить */}
        <section>
          <h2 className="text-sm font-medium text-tg-hint uppercase tracking-wide mb-3 flex items-center gap-2">
            <Moon className="w-4 h-4" />
            Не беспокоить
          </h2>

          <div className="bg-tg-secondary-bg rounded-xl overflow-hidden divide-y divide-tg-bg">
            {/* Переключатель */}
            <label className={`flex items-center justify-between px-4 py-3 cursor-pointer ${mutation.isPending ? 'opacity-70' : ''}`}>
              <span className="text-tg-text">Включить тихие часы</span>
              <input
                type="checkbox"
                checked={notifications.dnd_enabled}
                onChange={(e) => handleNotificationChange('dnd_enabled', e.target.checked)}
                disabled={mutation.isPending}
                className="w-5 h-5 rounded accent-primary"
              />
            </label>

            {/* Диапазон времени */}
            {notifications.dnd_enabled && (
              <div className={`px-4 py-3 flex items-center gap-4 ${mutation.isPending ? 'opacity-70' : ''}`}>
                <div className="flex-1">
                  <label className="text-sm text-tg-hint">С</label>
                  <input
                    type="time"
                    value={notifications.dnd_start}
                    onChange={(e) => handleNotificationChange('dnd_start', e.target.value)}
                    disabled={mutation.isPending}
                    className="w-full mt-1 px-3 py-2 bg-tg-bg rounded-lg text-tg-text"
                  />
                </div>
                <div className="flex-1">
                  <label className="text-sm text-tg-hint">До</label>
                  <input
                    type="time"
                    value={notifications.dnd_end}
                    onChange={(e) => handleNotificationChange('dnd_end', e.target.value)}
                    disabled={mutation.isPending}
                    className="w-full mt-1 px-3 py-2 bg-tg-bg rounded-lg text-tg-text"
                  />
                </div>
              </div>
            )}
          </div>
        </section>

        {/* Справка */}
        <section>
          <h2 className="text-sm font-medium text-tg-hint uppercase tracking-wide mb-3 flex items-center gap-2">
            <MessageSquare className="w-4 h-4" />
            Как пользоваться
          </h2>

          <div className="bg-tg-secondary-bg rounded-xl overflow-hidden divide-y divide-tg-bg">
            {/* Типы записей */}
            <HelpItem
              icon={<FileText className="w-5 h-5" />}
              title="Типы записей"
              isOpen={helpSection === 'types'}
              onClick={() => setHelpSection(helpSection === 'types' ? null : 'types')}
            >
              <div className="space-y-2 text-sm text-tg-hint">
                <p><strong className="text-tg-text">Задача</strong> — действия с датами и напоминаниями</p>
                <p><strong className="text-tg-text">Идея</strong> — мысли и концепции на будущее</p>
                <p><strong className="text-tg-text">Заметка</strong> — общая информация</p>
                <p><strong className="text-tg-text">Ресурс</strong> — ссылки, файлы и материалы</p>
                <p><strong className="text-tg-text">Контакт</strong> — люди и их данные</p>
              </div>
            </HelpItem>

            {/* Голосовые сообщения */}
            <HelpItem
              icon={<Mic className="w-5 h-5" />}
              title="Голосовые сообщения"
              isOpen={helpSection === 'voice'}
              onClick={() => setHelpSection(helpSection === 'voice' ? null : 'voice')}
            >
              <div className="text-sm text-tg-hint">
                <p>Отправляйте голосовые сообщения боту — они автоматически расшифруются и обработаются.</p>
                <p className="mt-2">ИИ извлечёт задачи, идеи и другую информацию из вашей речи.</p>
              </div>
            </HelpItem>

            {/* Умный поиск */}
            <HelpItem
              icon={<Search className="w-5 h-5" />}
              title="Умный поиск"
              isOpen={helpSection === 'search'}
              onClick={() => setHelpSection(helpSection === 'search' ? null : 'search')}
            >
              <div className="text-sm text-tg-hint">
                <p>Поиск использует семантическое понимание — находит связанные записи, даже если слова не совпадают.</p>
                <p className="mt-2">Попробуйте искать по смыслу: «встречи на этой неделе» или «идеи для проекта».</p>
              </div>
            </HelpItem>

            {/* Повторяющиеся задачи */}
            <HelpItem
              icon={<RefreshCw className="w-5 h-5" />}
              title="Повторяющиеся задачи"
              isOpen={helpSection === 'recurring'}
              onClick={() => setHelpSection(helpSection === 'recurring' ? null : 'recurring')}
            >
              <div className="text-sm text-tg-hint">
                <p>Задачи могут повторяться ежедневно, еженедельно или ежемесячно. При завершении автоматически создаётся следующая.</p>
                <p className="mt-2">Настройте повтор при создании или редактировании задачи.</p>
              </div>
            </HelpItem>

            {/* Ссылки и документы */}
            <HelpItem
              icon={<Link2 className="w-5 h-5" />}
              title="Ссылки и документы"
              isOpen={helpSection === 'links'}
              onClick={() => setHelpSection(helpSection === 'links' ? null : 'links')}
            >
              <div className="text-sm text-tg-hint">
                <p>Отправляйте ссылки — они автоматически загрузятся и будут кратко пересказаны.</p>
                <p className="mt-2">PDF и изображения обрабатываются ИИ для извлечения текста и ключевой информации.</p>
              </div>
            </HelpItem>
          </div>
        </section>
      </div>
    </div>
  )
}

// Компонент раскрывающегося раздела справки
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
