import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, MoreVertical, Trash2, Edit2 } from 'lucide-react'
import { cn, haptic } from '@/lib/utils'
import { fetchItems, fetchProjects, deleteProject, updateProject, Item, Project } from '@/api/client'
import ItemCard from '@/components/ItemCard'
import ItemDetail from '@/components/ItemDetail'
import { ItemListSkeleton } from '@/components/Skeleton'

interface ProjectDetailProps {
  projectId: number
  onBack: () => void
}

export default function ProjectDetail({ projectId, onBack }: ProjectDetailProps) {
  const queryClient = useQueryClient()
  const [selectedItem, setSelectedItem] = useState<Item | null>(null)
  const [showMenu, setShowMenu] = useState(false)
  const [isEditing, setIsEditing] = useState(false)
  const [editName, setEditName] = useState('')

  // Fetch project details
  const { data: projectsData } = useQuery({
    queryKey: ['projects'],
    queryFn: fetchProjects,
  })

  const project = projectsData?.projects.find((p) => p.id === projectId)

  // Fetch project items
  const { data: itemsData, isLoading } = useQuery({
    queryKey: ['items', 'project', projectId],
    queryFn: () => fetchItems({ project_id: projectId, limit: 100 }),
  })

  // Set up back button
  useEffect(() => {
    const tg = window.Telegram?.WebApp?.BackButton
    if (tg) {
      tg.show()
      tg.onClick(onBack)
      return () => {
        tg.hide()
        tg.offClick(onBack)
      }
    }
  }, [onBack])

  useEffect(() => {
    if (project) {
      setEditName(project.name)
    }
  }, [project])

  const deleteMutation = useMutation({
    mutationFn: () => deleteProject(projectId),
    onSuccess: () => {
      haptic('success')
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      queryClient.invalidateQueries({ queryKey: ['items'] })
      onBack()
    },
  })

  const updateMutation = useMutation({
    mutationFn: (name: string) => updateProject(projectId, { name }),
    onSuccess: () => {
      haptic('success')
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      setIsEditing(false)
    },
  })

  const handleDelete = () => {
    if (confirm(`Удалить проект "${project?.name}"? Записи не будут удалены.`)) {
      deleteMutation.mutate()
    }
  }

  const handleSaveEdit = () => {
    if (editName.trim() && editName !== project?.name) {
      updateMutation.mutate(editName.trim())
    } else {
      setIsEditing(false)
    }
  }

  const handleItemClick = (item: Item) => {
    haptic('light')
    setSelectedItem(item)
  }

  const items = itemsData?.items || []

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="sticky top-0 z-10 bg-tg-bg border-b border-tg-secondary-bg px-4 py-3">
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="p-1 rounded-full hover:bg-tg-secondary-bg"
          >
            <ArrowLeft size={24} className="text-tg-text" />
          </button>

          {isEditing ? (
            <input
              type="text"
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
              onBlur={handleSaveEdit}
              onKeyDown={(e) => e.key === 'Enter' && handleSaveEdit()}
              autoFocus
              className="flex-1 text-lg font-semibold bg-transparent border-b-2 border-primary focus:outline-none text-tg-text"
            />
          ) : (
            <div className="flex items-center gap-2 flex-1">
              {project && (
                <div
                  className="w-6 h-6 rounded flex items-center justify-center text-white text-xs"
                  style={{ backgroundColor: project.color || '#8B5CF6' }}
                >
                  {project.emoji || '📁'}
                </div>
              )}
              <h2 className="text-lg font-semibold text-tg-text">
                {project?.name || 'Проект'}
              </h2>
            </div>
          )}

          <div className="relative">
            <button
              onClick={() => setShowMenu(!showMenu)}
              className="p-2 rounded-full hover:bg-tg-secondary-bg"
            >
              <MoreVertical size={20} className="text-tg-hint" />
            </button>

            {showMenu && (
              <div className="absolute right-0 top-full mt-1 bg-tg-bg border border-tg-secondary-bg rounded-lg shadow-lg z-20 min-w-[150px]">
                <button
                  onClick={() => {
                    setShowMenu(false)
                    setIsEditing(true)
                  }}
                  className="flex items-center gap-2 px-4 py-2 w-full text-left hover:bg-tg-secondary-bg text-tg-text"
                >
                  <Edit2 size={18} />
                  <span>Переименовать</span>
                </button>
                <button
                  onClick={() => {
                    setShowMenu(false)
                    handleDelete()
                  }}
                  className="flex items-center gap-2 px-4 py-2 w-full text-left hover:bg-tg-secondary-bg text-red-500"
                >
                  <Trash2 size={18} />
                  <span>Удалить</span>
                </button>
              </div>
            )}
          </div>
        </div>

        {project && (
          <p className="text-sm text-tg-hint mt-1 ml-10">
            {project.item_count} {project.item_count === 1 ? 'запись' : 'записей'}
          </p>
        )}
      </div>

      {/* Items list */}
      <div className="flex-1 overflow-auto">
        {isLoading ? (
          <ItemListSkeleton count={6} />
        ) : items.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-tg-hint">
            <p className="text-lg">Пусто</p>
            <p className="text-sm mt-1">В этом проекте нет записей</p>
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
