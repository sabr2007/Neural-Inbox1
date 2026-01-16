import { cn } from '@/lib/utils'

interface SkeletonProps {
  className?: string
}

export function Skeleton({ className }: SkeletonProps) {
  return (
    <div className={cn('skeleton rounded', className)} />
  )
}

export function ItemCardSkeleton() {
  return (
    <div className="px-4 py-3 border-b border-tg-secondary-bg">
      <div className="flex items-start gap-3">
        <Skeleton className="w-6 h-6 rounded-full flex-shrink-0" />
        <div className="flex-1">
          <Skeleton className="h-5 w-3/4 mb-2" />
          <Skeleton className="h-4 w-1/2" />
        </div>
      </div>
    </div>
  )
}

export function ItemListSkeleton({ count = 5 }: { count?: number }) {
  return (
    <div>
      {Array.from({ length: count }).map((_, i) => (
        <ItemCardSkeleton key={i} />
      ))}
    </div>
  )
}

export function ProjectCardSkeleton() {
  return (
    <div className="p-4 border-b border-tg-secondary-bg">
      <div className="flex items-center gap-3">
        <Skeleton className="w-10 h-10 rounded-lg flex-shrink-0" />
        <div className="flex-1">
          <Skeleton className="h-5 w-1/2 mb-2" />
          <Skeleton className="h-4 w-1/4" />
        </div>
      </div>
    </div>
  )
}
