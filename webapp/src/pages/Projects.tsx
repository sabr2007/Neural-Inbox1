import { useState, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Folder, ChevronRight } from 'lucide-react'
import { cn, haptic } from '@/lib/utils'
import { fetchProjects, createProject, Project, ProjectsListResponse } from '@/api/client'
import { ProjectCardSkeleton } from '@/components/Skeleton'
import { useToast } from '@/hooks/useToast'

interface ProjectsProps {
  onProjectSelect: (projectId: number) => void
}

const PROJECT_COLORS = [
  '#8B5CF6', // Purple
  '#3B82F6', // Blue
  '#10B981', // Green
  '#F59E0B', // Amber
  '#EF4444', // Red
  '#EC4899', // Pink
  '#6366F1', // Indigo
  '#14B8A6', // Teal
]

export default function Projects({ onProjectSelect }: ProjectsProps) {
  const queryClient = useQueryClient()
  const { showError } = useToast()
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [newProjectName, setNewProjectName] = useState('')
  const [newProjectColor, setNewProjectColor] = useState(PROJECT_COLORS[0])
  const tempIdRef = useRef(-1)

  const { data, isLoading } = useQuery({
    queryKey: ['projects'],
    queryFn: fetchProjects,
  })

  const createMutation = useMutation({
    mutationFn: createProject,
    onMutate: async (newProject) => {
      await queryClient.cancelQueries({ queryKey: ['projects'] })
      const previous = queryClient.getQueryData<ProjectsListResponse>(['projects'])

      // Create optimistic project with temporary negative ID
      const tempId = tempIdRef.current--
      const optimisticProject: Project = {
        id: tempId,
        name: newProject.name,
        color: newProject.color,
        emoji: undefined,
        item_count: 0,
        created_at: new Date().toISOString(),
      }

      queryClient.setQueryData<ProjectsListResponse>(['projects'], (old) => {
        if (!old) return { projects: [optimisticProject], total: 1 }
        return {
          ...old,
          projects: [...old.projects, optimisticProject],
          total: old.total + 1,
        }
      })

      haptic('success')
      setShowCreateForm(false)
      setNewProjectName('')
      setNewProjectColor(PROJECT_COLORS[0])

      return { previous, tempId }
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) {
        queryClient.setQueryData(['projects'], context.previous)
      }
      haptic('error')
      showError('Не удалось создать проект')
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
    },
  })

  const handleCreateProject = () => {
    if (!newProjectName.trim()) return
    createMutation.mutate({
      name: newProjectName.trim(),
      color: newProjectColor,
    })
  }

  const handleProjectClick = (project: Project) => {
    haptic('light')
    onProjectSelect(project.id)
  }

  const projects = data?.projects || []

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="sticky top-0 z-10 bg-tg-bg border-b border-tg-secondary-bg px-4 py-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-tg-text">Проекты</h2>
          <button
            onClick={() => {
              haptic('light')
              setShowCreateForm(true)
            }}
            className="p-2 rounded-full hover:bg-tg-secondary-bg text-primary"
          >
            <Plus size={24} />
          </button>
        </div>
      </div>

      {/* Create project form */}
      {showCreateForm && (
        <div className="px-4 py-4 border-b border-tg-secondary-bg bg-tg-secondary-bg/30">
          <input
            type="text"
            value={newProjectName}
            onChange={(e) => setNewProjectName(e.target.value)}
            placeholder="Название проекта"
            autoFocus
            className="w-full px-3 py-2 bg-tg-bg border border-tg-secondary-bg rounded-lg text-tg-text placeholder:text-tg-hint focus:outline-none focus:border-primary"
          />

          {/* Color picker */}
          <div className="flex items-center gap-2 mt-3">
            {PROJECT_COLORS.map((color) => (
              <button
                key={color}
                onClick={() => setNewProjectColor(color)}
                className={cn(
                  'w-8 h-8 rounded-full transition-transform',
                  newProjectColor === color && 'ring-2 ring-offset-2 ring-primary scale-110'
                )}
                style={{ backgroundColor: color }}
              />
            ))}
          </div>

          {/* Actions */}
          <div className="flex items-center gap-2 mt-4">
            <button
              onClick={() => setShowCreateForm(false)}
              className="flex-1 py-2 text-tg-hint hover:text-tg-text transition-colors"
            >
              Отмена
            </button>
            <button
              onClick={handleCreateProject}
              disabled={!newProjectName.trim() || createMutation.isPending}
              className="flex-1 py-2 bg-primary text-white rounded-lg font-medium disabled:opacity-50"
            >
              {createMutation.isPending ? 'Создание...' : 'Создать'}
            </button>
          </div>
        </div>
      )}

      {/* Projects list */}
      <div className="flex-1 overflow-auto">
        {isLoading ? (
          <div>
            {Array.from({ length: 4 }).map((_, i) => (
              <ProjectCardSkeleton key={i} />
            ))}
          </div>
        ) : projects.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-tg-hint">
            <Folder size={48} className="mb-4 opacity-50" />
            <p className="text-lg">Нет проектов</p>
            <p className="text-sm mt-1">Создайте первый проект</p>
          </div>
        ) : (
          <div>
            {projects.map((project) => (
              <button
                key={project.id}
                onClick={() => handleProjectClick(project)}
                className="w-full px-4 py-3 flex items-center gap-3 border-b border-tg-secondary-bg hover:bg-tg-secondary-bg/50 transition-colors"
              >
                {/* Project icon */}
                <div
                  className="w-10 h-10 rounded-lg flex items-center justify-center text-white"
                  style={{ backgroundColor: project.color || '#8B5CF6' }}
                >
                  {project.emoji || <Folder size={20} />}
                </div>

                {/* Project info */}
                <div className="flex-1 text-left">
                  <h3 className="font-medium text-tg-text">{project.name}</h3>
                  <p className="text-sm text-tg-hint">
                    {project.item_count} {project.item_count === 1 ? 'запись' : 'записей'}
                  </p>
                </div>

                <ChevronRight size={20} className="text-tg-hint" />
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
