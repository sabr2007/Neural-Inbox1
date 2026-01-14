# neural-inbox1/src/ai/tools.py
"""AI Agent tool definitions and execution functions."""
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.db.database import get_session
from src.db.repository import ItemRepository, ProjectRepository, UserRepository
from src.ai.batch_confirmations import (
    PendingOperation, generate_token, store_pending, get_pending, clear_pending
)
from src.ai.embeddings import get_embedding


# Tool definitions for AI agent
TOOL_DEFINITIONS = [
    {
        "name": "search_items",
        "description": "Search items by text and filters. Use to find item IDs for further operations.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Text search query (searches in title, content, original_input)"
                },
                "type": {
                    "type": "string",
                    "enum": ["task", "idea", "note", "resource", "contact", "event"],
                    "description": "Filter by item type"
                },
                "status": {
                    "type": "string",
                    "enum": ["inbox", "active", "done", "archived"],
                    "description": "Filter by status"
                },
                "date_field": {
                    "type": "string",
                    "enum": ["due_at", "created_at"],
                    "description": "Which date field to filter by"
                },
                "date_from": {
                    "type": "string",
                    "description": "Start of date range (ISO format)"
                },
                "date_to": {
                    "type": "string",
                    "description": "End of date range (ISO format)"
                },
                "project": {
                    "type": ["string", "integer"],
                    "description": "Project name or ID"
                },
                "priority": {
                    "type": "string",
                    "enum": ["high", "medium", "low"],
                    "description": "Filter by priority"
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Filter by tags (items must have ALL specified tags)"
                },
                "limit": {
                    "type": "integer",
                    "default": 10,
                    "description": "Maximum results to return"
                }
            },
            "required": []
        }
    },
    {
        "name": "get_item_details",
        "description": "Get full details of an item by ID.",
        "parameters": {
            "type": "object",
            "properties": {
                "item_id": {
                    "type": "integer",
                    "description": "ID of the item to retrieve"
                }
            },
            "required": ["item_id"]
        }
    },
    {
        "name": "batch_update_items",
        "description": "Batch update items matching filters. Requires confirmation for execution.",
        "parameters": {
            "type": "object",
            "properties": {
                "filter": {
                    "type": "object",
                    "description": "Filters to select items (same as search_items)",
                    "properties": {
                        "query": {"type": "string"},
                        "type": {"type": "string"},
                        "status": {"type": "string"},
                        "date_field": {"type": "string"},
                        "date_from": {"type": "string"},
                        "date_to": {"type": "string"},
                        "project": {"type": ["string", "integer"]},
                        "priority": {"type": "string"},
                        "tags": {"type": "array", "items": {"type": "string"}}
                    }
                },
                "updates": {
                    "type": "object",
                    "description": "Fields to update",
                    "properties": {
                        "due_at": {"type": "string", "description": "New due date (ISO format)"},
                        "due_at_raw": {"type": "string", "description": "Original text for due date"},
                        "status": {"type": "string", "enum": ["inbox", "active", "done", "archived"]},
                        "priority": {"type": "string", "enum": ["high", "medium", "low"]},
                        "project_id": {"type": "integer", "description": "New project ID"},
                        "tags": {"type": "array", "items": {"type": "string"}}
                    }
                },
                "confirmed": {
                    "type": "boolean",
                    "default": False,
                    "description": "Set to true after user confirmation"
                },
                "confirmation_token": {
                    "type": "string",
                    "description": "Token from preview response"
                }
            },
            "required": ["filter", "updates"]
        }
    },
    {
        "name": "batch_delete_items",
        "description": "Batch delete items matching filters. Requires confirmation for execution.",
        "parameters": {
            "type": "object",
            "properties": {
                "filter": {
                    "type": "object",
                    "description": "Filters to select items (same as search_items)",
                    "properties": {
                        "query": {"type": "string"},
                        "type": {"type": "string"},
                        "status": {"type": "string"},
                        "date_field": {"type": "string"},
                        "date_from": {"type": "string"},
                        "date_to": {"type": "string"},
                        "project": {"type": ["string", "integer"]},
                        "priority": {"type": "string"},
                        "tags": {"type": "array", "items": {"type": "string"}}
                    }
                },
                "confirmed": {
                    "type": "boolean",
                    "default": False,
                    "description": "Set to true after user confirmation"
                },
                "confirmation_token": {
                    "type": "string",
                    "description": "Token from preview response"
                }
            },
            "required": ["filter"]
        }
    },
    {
        "name": "manage_projects",
        "description": "Manage projects: create, list, get, rename, update, delete, move items.",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["create", "list", "get", "rename", "update", "delete", "move_items"],
                    "description": "Action to perform"
                },
                "name": {
                    "type": "string",
                    "description": "Project name (for create/rename)"
                },
                "color": {
                    "type": "string",
                    "description": "Project color (#HEX format)"
                },
                "emoji": {
                    "type": "string",
                    "description": "Project emoji"
                },
                "project_id": {
                    "type": "integer",
                    "description": "Project ID (for get/rename/update/delete/move_items)"
                },
                "target_project_id": {
                    "type": ["integer", "null"],
                    "description": "Target project ID for move_items (null to remove from project)"
                },
                "confirmed": {
                    "type": "boolean",
                    "default": False,
                    "description": "Confirmation for delete/move_items"
                },
                "confirmation_token": {
                    "type": "string",
                    "description": "Token from preview response"
                }
            },
            "required": ["action"]
        }
    },
    {
        "name": "save_item",
        "description": "Create a new item (task, idea, note, resource, contact, event). Use when user asks to ADD or CREATE a new record.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Item title/name"
                },
                "content": {
                    "type": "string",
                    "description": "Full content (optional)"
                },
                "type": {
                    "type": "string",
                    "enum": ["task", "idea", "note", "resource", "contact", "event"],
                    "description": "Item type"
                },
                "due_at": {
                    "type": "string",
                    "description": "Due date in ISO format (optional)"
                },
                "due_at_raw": {
                    "type": "string",
                    "description": "Original due date text like 'завтра в 15:00' (optional)"
                },
                "priority": {
                    "type": "string",
                    "enum": ["high", "medium", "low"],
                    "description": "Priority level (optional)"
                },
                "project_id": {
                    "type": "integer",
                    "description": "Project ID to add item to (optional)"
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Tags list (optional)"
                }
            },
            "required": ["title", "type"]
        }
    }
]


async def _resolve_project_id(
    project_repo: ProjectRepository,
    project: Optional[Any],
    user_id: int
) -> Optional[int]:
    """Resolve project name or ID to project ID."""
    if project is None:
        return None
    if isinstance(project, int):
        return project
    if isinstance(project, str):
        if project.isdigit():
            return int(project)
        proj = await project_repo.get_by_name(project, user_id)
        return proj.id if proj else None
    return None


async def _parse_filter_params(
    filter_dict: Dict[str, Any],
    user_id: int,
    session
) -> Dict[str, Any]:
    """Parse filter dictionary into repository method parameters."""
    project_repo = ProjectRepository(session)

    params = {
        "user_id": user_id,
        "query": filter_dict.get("query"),
        "type_filter": filter_dict.get("type"),
        "status_filter": filter_dict.get("status"),
        "date_field": filter_dict.get("date_field"),
        "priority": filter_dict.get("priority"),
        "tags": filter_dict.get("tags"),
        "limit": filter_dict.get("limit", 100)  # Higher limit for batch ops
    }

    # Parse dates
    if filter_dict.get("date_from"):
        try:
            params["date_from"] = datetime.fromisoformat(filter_dict["date_from"].replace("Z", "+00:00"))
        except ValueError:
            pass

    if filter_dict.get("date_to"):
        try:
            params["date_to"] = datetime.fromisoformat(filter_dict["date_to"].replace("Z", "+00:00"))
        except ValueError:
            pass

    # Resolve project
    if filter_dict.get("project"):
        params["project_id"] = await _resolve_project_id(
            project_repo, filter_dict["project"], user_id
        )

    return params


async def execute_search_items(user_id: int, params: Dict[str, Any]) -> Dict[str, Any]:
    """Execute search_items tool."""
    async with get_session() as session:
        filter_params = await _parse_filter_params(params, user_id, session)
        filter_params["limit"] = params.get("limit", 10)

        item_repo = ItemRepository(session)
        items = await item_repo.search_advanced(**filter_params)

        results = []
        for item in items:
            results.append({
                "id": item.id,
                "title": item.title,
                "type": item.type,
                "status": item.status,
                "due_at": item.due_at.isoformat() if item.due_at else None,
                "priority": item.priority
            })

        return {
            "results": results,
            "total_count": len(results)
        }


async def execute_get_item_details(user_id: int, params: Dict[str, Any]) -> Dict[str, Any]:
    """Execute get_item_details tool."""
    item_id = params.get("item_id")
    if not item_id:
        return {"error": "item_id is required"}

    async with get_session() as session:
        item_repo = ItemRepository(session)
        item = await item_repo.get(item_id, user_id)

        if not item:
            return {"error": f"Item {item_id} not found"}

        return {
            "id": item.id,
            "title": item.title,
            "content": item.content,
            "type": item.type,
            "status": item.status,
            "due_at": item.due_at.isoformat() if item.due_at else None,
            "due_at_raw": item.due_at_raw,
            "priority": item.priority,
            "tags": item.tags,
            "entities": item.entities,
            "project_id": item.project_id,
            "created_at": item.created_at.isoformat() if item.created_at else None
        }


async def execute_batch_update_items(user_id: int, params: Dict[str, Any]) -> Dict[str, Any]:
    """Execute batch_update_items tool."""
    filter_dict = params.get("filter", {})
    updates = params.get("updates", {})
    confirmed = params.get("confirmed", False)
    token = params.get("confirmation_token")

    if not updates:
        return {"error": "updates is required"}

    # If confirmed with token, execute the operation
    if confirmed and token:
        pending = get_pending(token)
        if not pending:
            return {"error": "Confirmation token expired or invalid"}
        if pending.user_id != user_id:
            return {"error": "Invalid token for this user"}

        async with get_session() as session:
            item_repo = ItemRepository(session)

            # Parse update values
            update_values = {}
            if "status" in updates:
                update_values["status"] = updates["status"]
            if "priority" in updates:
                update_values["priority"] = updates["priority"]
            if "project_id" in updates:
                update_values["project_id"] = updates["project_id"]
            if "tags" in updates:
                update_values["tags"] = updates["tags"]
            if "due_at" in updates:
                try:
                    update_values["due_at"] = datetime.fromisoformat(
                        updates["due_at"].replace("Z", "+00:00")
                    )
                except ValueError:
                    pass
            if "due_at_raw" in updates:
                update_values["due_at_raw"] = updates["due_at_raw"]

            count = await item_repo.batch_update(pending.matched_ids, user_id, **update_values)
            clear_pending(token)

            return {
                "success": True,
                "updated_count": count
            }

    # Otherwise, return preview
    async with get_session() as session:
        filter_params = await _parse_filter_params(filter_dict, user_id, session)
        item_repo = ItemRepository(session)
        items = await item_repo.search_advanced(**filter_params)

        if not items:
            return {
                "matched_count": 0,
                "items_preview": [],
                "needs_confirmation": False
            }

        token = generate_token("upd")
        operation = PendingOperation(
            token=token,
            action="update",
            user_id=user_id,
            filter=filter_dict,
            updates=updates,
            matched_ids=[item.id for item in items],
            created_at=datetime.utcnow()
        )
        store_pending(operation)

        preview = [{"id": item.id, "title": item.title} for item in items[:5]]

        return {
            "action": "update",
            "matched_count": len(items),
            "items_preview": preview,
            "needs_confirmation": True,
            "confirmation_token": token
        }


async def execute_batch_delete_items(user_id: int, params: Dict[str, Any]) -> Dict[str, Any]:
    """Execute batch_delete_items tool."""
    filter_dict = params.get("filter", {})
    confirmed = params.get("confirmed", False)
    token = params.get("confirmation_token")

    # If confirmed with token, execute the operation
    if confirmed and token:
        pending = get_pending(token)
        if not pending:
            return {"error": "Confirmation token expired or invalid"}
        if pending.user_id != user_id:
            return {"error": "Invalid token for this user"}

        async with get_session() as session:
            item_repo = ItemRepository(session)
            count = await item_repo.batch_delete(pending.matched_ids, user_id)
            clear_pending(token)

            return {
                "success": True,
                "deleted_count": count
            }

    # Otherwise, return preview
    async with get_session() as session:
        filter_params = await _parse_filter_params(filter_dict, user_id, session)
        item_repo = ItemRepository(session)
        items = await item_repo.search_advanced(**filter_params)

        if not items:
            return {
                "matched_count": 0,
                "items_preview": [],
                "needs_confirmation": False
            }

        token = generate_token("del")
        operation = PendingOperation(
            token=token,
            action="delete",
            user_id=user_id,
            filter=filter_dict,
            updates=None,
            matched_ids=[item.id for item in items],
            created_at=datetime.utcnow()
        )
        store_pending(operation)

        preview = [{"id": item.id, "title": item.title} for item in items[:5]]

        return {
            "action": "delete",
            "matched_count": len(items),
            "items_preview": preview,
            "needs_confirmation": True,
            "confirmation_token": token
        }


async def execute_manage_projects(user_id: int, params: Dict[str, Any]) -> Dict[str, Any]:
    """Execute manage_projects tool."""
    action = params.get("action")
    if not action:
        return {"error": "action is required"}

    async with get_session() as session:
        project_repo = ProjectRepository(session)

        if action == "create":
            name = params.get("name")
            if not name:
                return {"error": "name is required for create"}
            project = await project_repo.create(
                user_id=user_id,
                name=name,
                color=params.get("color"),
                emoji=params.get("emoji")
            )
            return {
                "success": True,
                "project": {
                    "id": project.id,
                    "name": project.name,
                    "color": project.color,
                    "emoji": project.emoji
                }
            }

        elif action == "list":
            projects = await project_repo.get_all(user_id)
            return {
                "projects": [
                    {
                        "id": p.id,
                        "name": p.name,
                        "color": p.color,
                        "emoji": p.emoji
                    }
                    for p in projects
                ]
            }

        elif action == "get":
            project_id = params.get("project_id")
            if not project_id:
                return {"error": "project_id is required for get"}
            project = await project_repo.get(project_id, user_id)
            if not project:
                return {"error": f"Project {project_id} not found"}
            items_count = await project_repo.get_items_count(project_id, user_id)
            return {
                "id": project.id,
                "name": project.name,
                "color": project.color,
                "emoji": project.emoji,
                "items_count": items_count
            }

        elif action == "rename":
            project_id = params.get("project_id")
            name = params.get("name")
            if not project_id or not name:
                return {"error": "project_id and name are required for rename"}
            project = await project_repo.update(project_id, user_id, name=name)
            if not project:
                return {"error": f"Project {project_id} not found"}
            return {
                "success": True,
                "project": {
                    "id": project.id,
                    "name": project.name
                }
            }

        elif action == "update":
            project_id = params.get("project_id")
            if not project_id:
                return {"error": "project_id is required for update"}
            update_fields = {}
            if "name" in params:
                update_fields["name"] = params["name"]
            if "color" in params:
                update_fields["color"] = params["color"]
            if "emoji" in params:
                update_fields["emoji"] = params["emoji"]
            if not update_fields:
                return {"error": "No fields to update"}
            project = await project_repo.update(project_id, user_id, **update_fields)
            if not project:
                return {"error": f"Project {project_id} not found"}
            return {
                "success": True,
                "project": {
                    "id": project.id,
                    "name": project.name,
                    "color": project.color,
                    "emoji": project.emoji
                }
            }

        elif action == "delete":
            project_id = params.get("project_id")
            if not project_id:
                return {"error": "project_id is required for delete"}

            confirmed = params.get("confirmed", False)
            token = params.get("confirmation_token")

            if confirmed and token:
                pending = get_pending(token)
                if not pending:
                    return {"error": "Confirmation token expired or invalid"}
                if pending.user_id != user_id:
                    return {"error": "Invalid token for this user"}

                deleted = await project_repo.delete(project_id, user_id)
                clear_pending(token)
                return {
                    "success": deleted,
                    "deleted": deleted
                }

            # Return preview
            project = await project_repo.get(project_id, user_id)
            if not project:
                return {"error": f"Project {project_id} not found"}

            items_count = await project_repo.get_items_count(project_id, user_id)
            token = generate_token("delp")
            operation = PendingOperation(
                token=token,
                action="delete_project",
                user_id=user_id,
                filter={"project_id": project_id},
                updates=None,
                matched_ids=[project_id],
                created_at=datetime.utcnow()
            )
            store_pending(operation)

            return {
                "action": "delete_project",
                "project": {
                    "id": project.id,
                    "name": project.name
                },
                "items_count": items_count,
                "needs_confirmation": True,
                "confirmation_token": token
            }

        elif action == "move_items":
            project_id = params.get("project_id")
            target_project_id = params.get("target_project_id")
            if not project_id:
                return {"error": "project_id is required for move_items"}

            confirmed = params.get("confirmed", False)
            token = params.get("confirmation_token")

            if confirmed and token:
                pending = get_pending(token)
                if not pending:
                    return {"error": "Confirmation token expired or invalid"}
                if pending.user_id != user_id:
                    return {"error": "Invalid token for this user"}

                count = await project_repo.move_items(project_id, target_project_id, user_id)
                clear_pending(token)
                return {
                    "success": True,
                    "moved_count": count
                }

            # Return preview
            items_count = await project_repo.get_items_count(project_id, user_id)
            if items_count == 0:
                return {
                    "matched_count": 0,
                    "needs_confirmation": False
                }

            token = generate_token("mov")
            operation = PendingOperation(
                token=token,
                action="move_items",
                user_id=user_id,
                filter={"project_id": project_id, "target_project_id": target_project_id},
                updates=None,
                matched_ids=[],  # Not tracking individual items here
                created_at=datetime.utcnow()
            )
            store_pending(operation)

            source_project = await project_repo.get(project_id, user_id)
            target_project = None
            if target_project_id:
                target_project = await project_repo.get(target_project_id, user_id)

            return {
                "action": "move_items",
                "source_project": {
                    "id": source_project.id,
                    "name": source_project.name
                } if source_project else None,
                "target_project": {
                    "id": target_project.id,
                    "name": target_project.name
                } if target_project else None,
                "items_count": items_count,
                "needs_confirmation": True,
                "confirmation_token": token
            }

        else:
            return {"error": f"Unknown action: {action}"}


async def execute_save_item(user_id: int, params: Dict[str, Any]) -> Dict[str, Any]:
    """Execute save_item tool - create a new item."""
    title = params.get("title")
    item_type = params.get("type")
    
    if not title:
        return {"error": "title is required"}
    if not item_type:
        return {"error": "type is required"}
    
    async with get_session() as session:
        # Ensure user exists
        user_repo = UserRepository(session)
        await user_repo.get_or_create(user_id)
        
        # Parse due_at if provided
        due_at = None
        if params.get("due_at"):
            try:
                due_at = datetime.fromisoformat(params["due_at"].replace("Z", "+00:00"))
            except ValueError:
                pass
        
        # Create item
        item_repo = ItemRepository(session)
        item = await item_repo.create(
            user_id=user_id,
            type=item_type,
            title=title,
            content=params.get("content"),
            original_input=title,
            source="agent",
            due_at=due_at,
            due_at_raw=params.get("due_at_raw"),
            priority=params.get("priority"),
            project_id=params.get("project_id"),
            tags=params.get("tags", [])
        )
        
        # Generate embedding for semantic search
        embedding_text = f"{title} {params.get('content', '')}"
        embedding = await get_embedding(embedding_text)
        if embedding:
            await item_repo.update(item.id, user_id, embedding=embedding)
        
        return {
            "success": True,
            "item": {
                "id": item.id,
                "title": item.title,
                "type": item.type,
                "project_id": item.project_id
            }
        }


# Tool executor mapping
TOOL_EXECUTORS = {
    "search_items": execute_search_items,
    "get_item_details": execute_get_item_details,
    "batch_update_items": execute_batch_update_items,
    "batch_delete_items": execute_batch_delete_items,
    "manage_projects": execute_manage_projects,
    "save_item": execute_save_item,
}


async def execute_tool(tool_name: str, user_id: int, params: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a tool by name."""
    executor = TOOL_EXECUTORS.get(tool_name)
    if not executor:
        return {"error": f"Unknown tool: {tool_name}"}
    return await executor(user_id, params)
