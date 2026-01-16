"""
Projects API routes.
CRUD operations for projects.
"""
from fastapi import APIRouter, Depends, HTTPException

from src.api.auth import get_user_id
from src.api.schemas import (
    ProjectResponse, ProjectCreate, ProjectUpdate,
    ProjectsListResponse, SuccessResponse
)
from src.db.database import get_session
from src.db.repository import ProjectRepository, ItemRepository

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("", response_model=ProjectsListResponse)
async def list_projects(
    user_id: int = Depends(get_user_id)
):
    """List all projects with item counts."""
    async with get_session() as session:
        project_repo = ProjectRepository(session)
        item_repo = ItemRepository(session)

        projects = await project_repo.get_all(user_id)

        # Enrich with item counts
        project_responses = []
        for project in projects:
            item_count = await project_repo.get_items_count(project.id, user_id)
            response = ProjectResponse(
                id=project.id,
                name=project.name,
                color=project.color,
                emoji=project.emoji,
                item_count=item_count,
                created_at=project.created_at
            )
            project_responses.append(response)

        return ProjectsListResponse(
            projects=project_responses,
            total=len(project_responses)
        )


@router.post("", response_model=ProjectResponse, status_code=201)
async def create_project(
    data: ProjectCreate,
    user_id: int = Depends(get_user_id)
):
    """Create a new project."""
    async with get_session() as session:
        project_repo = ProjectRepository(session)

        # Check for duplicate name
        existing = await project_repo.get_by_name(data.name, user_id)
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Project '{data.name}' already exists"
            )

        project = await project_repo.create(
            user_id=user_id,
            name=data.name,
            color=data.color,
            emoji=data.emoji
        )

        return ProjectResponse(
            id=project.id,
            name=project.name,
            color=project.color,
            emoji=project.emoji,
            item_count=0,
            created_at=project.created_at
        )


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: int,
    user_id: int = Depends(get_user_id)
):
    """Get project by ID."""
    async with get_session() as session:
        project_repo = ProjectRepository(session)

        project = await project_repo.get(project_id, user_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        item_count = await project_repo.get_items_count(project_id, user_id)

        return ProjectResponse(
            id=project.id,
            name=project.name,
            color=project.color,
            emoji=project.emoji,
            item_count=item_count,
            created_at=project.created_at
        )


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int,
    data: ProjectUpdate,
    user_id: int = Depends(get_user_id)
):
    """Update project (partial update)."""
    async with get_session() as session:
        project_repo = ProjectRepository(session)

        # Check if name is being changed and if it conflicts
        update_data = data.model_dump(exclude_unset=True)
        if "name" in update_data:
            existing = await project_repo.get_by_name(update_data["name"], user_id)
            if existing and existing.id != project_id:
                raise HTTPException(
                    status_code=400,
                    detail=f"Project '{update_data['name']}' already exists"
                )

        project = await project_repo.update(project_id, user_id, **update_data)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        item_count = await project_repo.get_items_count(project_id, user_id)

        return ProjectResponse(
            id=project.id,
            name=project.name,
            color=project.color,
            emoji=project.emoji,
            item_count=item_count,
            created_at=project.created_at
        )


@router.delete("/{project_id}", response_model=SuccessResponse)
async def delete_project(
    project_id: int,
    user_id: int = Depends(get_user_id)
):
    """
    Delete project.
    Items in the project will have their project_id set to NULL.
    """
    async with get_session() as session:
        project_repo = ProjectRepository(session)

        # First, remove project_id from all items
        await project_repo.move_items(project_id, None, user_id)

        # Then delete the project
        deleted = await project_repo.delete(project_id, user_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Project not found")

        return SuccessResponse(message="Project deleted")
