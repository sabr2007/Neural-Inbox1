# neural-inbox1/src/db/search.py
"""Hybrid search: Full-text search + Vector similarity."""
import logging
from dataclasses import dataclass
from typing import List, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.embeddings import get_embedding

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    id: int
    title: str
    content: Optional[str]
    type: str
    score: float
    fts_score: float
    vector_score: float


def _format_embedding(embedding: List[float]) -> str:
    """Format embedding as PostgreSQL array literal."""
    return "[" + ",".join(str(v) for v in embedding) + "]"


async def hybrid_search(
    session: AsyncSession,
    user_id: int,
    query: str,
    limit: int = 10,
    type_filter: Optional[str] = None,
    status_filter: Optional[str] = None,
    fts_weight: float = 0.5,
    vector_weight: float = 0.5
) -> List[SearchResult]:
    """
    Hybrid search combining FTS and vector similarity.
    """
    if not query or not query.strip():
        return []

    # Get query embedding
    query_embedding = await get_embedding(query)
    if not query_embedding:
        # Fallback to FTS only
        return await fts_search(session, user_id, query, limit, type_filter, status_filter)

    # Format embedding as literal for SQL
    emb_literal = _format_embedding(query_embedding)

    # Build dynamic filter conditions to avoid asyncpg type inference issues with None
    type_condition = "AND type = :type_filter" if type_filter else ""
    status_condition = "AND status = :status_filter" if status_filter else ""

    # Build the hybrid query with embedding as literal
    # FTS scores are normalized to 0-1 range (raw ts_rank is typically 0.01-0.1)
    sql = text(f"""
        WITH fts_results AS (
            SELECT
                id,
                LEAST(1.0, ts_rank(
                    setweight(to_tsvector('russian', COALESCE(title, '')), 'A') ||
                    setweight(to_tsvector('russian', COALESCE(content, '')), 'B') ||
                    setweight(to_tsvector('russian', COALESCE(original_input, '')), 'C'),
                    plainto_tsquery('russian', :query)
                ) * 10) AS fts_score
            FROM items
            WHERE user_id = :user_id
                AND (
                    to_tsvector('russian', COALESCE(title, '') || ' ' || COALESCE(content, '') || ' ' || COALESCE(original_input, ''))
                    @@ plainto_tsquery('russian', :query)
                )
                {type_condition}
                {status_condition}
        ),
        vector_results AS (
            SELECT
                id,
                1 - (embedding <=> '{emb_literal}'::vector) AS vector_score
            FROM items
            WHERE user_id = :user_id
                AND embedding IS NOT NULL
                {type_condition}
                {status_condition}
            ORDER BY embedding <=> '{emb_literal}'::vector
            LIMIT :vec_limit
        ),
        combined AS (
            SELECT
                COALESCE(f.id, v.id) AS id,
                COALESCE(f.fts_score, 0) AS fts_score,
                COALESCE(v.vector_score, 0) AS vector_score
            FROM fts_results f
            FULL OUTER JOIN vector_results v ON f.id = v.id
        )
        SELECT
            c.id,
            i.title,
            i.content,
            i.type,
            -- Use weighted average but boost when both scores are high
            GREATEST(
                c.fts_score * :fts_weight + c.vector_score * :vector_weight,
                c.fts_score * 0.8,  -- Strong FTS match alone is valuable
                c.vector_score * 0.8  -- Strong vector match alone is valuable
            ) AS score,
            c.fts_score,
            c.vector_score
        FROM combined c
        JOIN items i ON c.id = i.id
        WHERE (c.fts_score > 0.05 OR c.vector_score > 0.3)
        ORDER BY score DESC
        LIMIT :limit
    """)

    # Build params dict dynamically
    params = {
        "user_id": user_id,
        "query": query,
        "fts_weight": fts_weight,
        "vector_weight": vector_weight,
        "vec_limit": limit * 3,
        "limit": limit
    }
    if type_filter:
        params["type_filter"] = type_filter
    if status_filter:
        params["status_filter"] = status_filter

    try:
        result = await session.execute(sql, params)

        rows = result.fetchall()
        results = [
            SearchResult(
                id=row.id,
                title=row.title or "",
                content=row.content,
                type=row.type,
                score=float(row.score),
                fts_score=float(row.fts_score),
                vector_score=float(row.vector_score)
            )
            for row in rows
        ]
        
        # If no results, try ILIKE fallback for short Russian queries
        if not results and len(query.split()) <= 3:
            results = await ilike_search(session, user_id, query, limit, type_filter, status_filter)
        
        return results

    except Exception as e:
        logger.error(f"Hybrid search error: {e}")
        # Fallback to simple search
        return await fts_search(session, user_id, query, limit, type_filter, status_filter)


async def fts_search(
    session: AsyncSession,
    user_id: int,
    query: str,
    limit: int = 10,
    type_filter: Optional[str] = None,
    status_filter: Optional[str] = None
) -> List[SearchResult]:
    """Fallback: Full-text search only."""
    # Build dynamic filter conditions to avoid asyncpg type inference issues with None
    type_condition = "AND type = :type_filter" if type_filter else ""
    status_condition = "AND status = :status_filter" if status_filter else ""

    sql = text(f"""
        SELECT
            id,
            title,
            content,
            type,
            ts_rank(
                setweight(to_tsvector('russian', COALESCE(title, '')), 'A') ||
                setweight(to_tsvector('russian', COALESCE(content, '')), 'B'),
                plainto_tsquery('russian', :query)
            ) AS score
        FROM items
        WHERE user_id = :user_id
            AND (
                to_tsvector('russian', COALESCE(title, '') || ' ' || COALESCE(content, '') || ' ' || COALESCE(original_input, ''))
                @@ plainto_tsquery('russian', :query)
            )
            {type_condition}
            {status_condition}
        ORDER BY score DESC
        LIMIT :limit
    """)

    # Build params dict dynamically
    params = {
        "user_id": user_id,
        "query": query,
        "limit": limit
    }
    if type_filter:
        params["type_filter"] = type_filter
    if status_filter:
        params["status_filter"] = status_filter

    try:
        result = await session.execute(sql, params)

        rows = result.fetchall()
        return [
            SearchResult(
                id=row.id,
                title=row.title or "",
                content=row.content,
                type=row.type,
                score=float(row.score),
                fts_score=float(row.score),
                vector_score=0.0
            )
            for row in rows
        ]

    except Exception as e:
        logger.error(f"FTS search error: {e}")
        return []


async def ilike_search(
    session: AsyncSession,
    user_id: int,
    query: str,
    limit: int = 10,
    type_filter: Optional[str] = None,
    status_filter: Optional[str] = None
) -> List[SearchResult]:
    """Fallback: ILIKE search for short Russian queries that FTS may miss."""
    type_condition = "AND type = :type_filter" if type_filter else ""
    status_condition = "AND status = :status_filter" if status_filter else ""
    
    # Build search pattern with wildcards
    pattern = f"%{query}%"
    
    sql = text(f"""
        SELECT
            id,
            title,
            content,
            type,
            0.5 AS score  -- Default score for ILIKE matches
        FROM items
        WHERE user_id = :user_id
            AND (
                title ILIKE :pattern
                OR content ILIKE :pattern
                OR original_input ILIKE :pattern
            )
            {type_condition}
            {status_condition}
        ORDER BY 
            CASE WHEN title ILIKE :pattern THEN 0 ELSE 1 END,
            created_at DESC
        LIMIT :limit
    """)
    
    params = {
        "user_id": user_id,
        "pattern": pattern,
        "limit": limit
    }
    if type_filter:
        params["type_filter"] = type_filter
    if status_filter:
        params["status_filter"] = status_filter
    
    try:
        result = await session.execute(sql, params)
        rows = result.fetchall()
        return [
            SearchResult(
                id=row.id,
                title=row.title or "",
                content=row.content,
                type=row.type,
                score=float(row.score),
                fts_score=0.0,
                vector_score=0.0
            )
            for row in rows
        ]
    except Exception as e:
        logger.error(f"ILIKE search error: {e}")
        return []


async def vector_search(
    session: AsyncSession,
    user_id: int,
    query: str,
    limit: int = 10,
    type_filter: Optional[str] = None
) -> List[SearchResult]:
    """Vector-only semantic search."""
    query_embedding = await get_embedding(query)
    if not query_embedding:
        return []

    emb_literal = _format_embedding(query_embedding)

    # Build dynamic filter to avoid asyncpg type inference issues with None
    type_condition = "AND type = :type_filter" if type_filter else ""

    sql = text(f"""
        SELECT
            id,
            title,
            content,
            type,
            1 - (embedding <=> '{emb_literal}'::vector) AS score
        FROM items
        WHERE user_id = :user_id
            AND embedding IS NOT NULL
            {type_condition}
        ORDER BY embedding <=> '{emb_literal}'::vector
        LIMIT :limit
    """)

    # Build params dict dynamically
    params = {
        "user_id": user_id,
        "limit": limit
    }
    if type_filter:
        params["type_filter"] = type_filter

    try:
        result = await session.execute(sql, params)

        rows = result.fetchall()
        return [
            SearchResult(
                id=row.id,
                title=row.title or "",
                content=row.content,
                type=row.type,
                score=float(row.score),
                fts_score=0.0,
                vector_score=float(row.score)
            )
            for row in rows
        ]

    except Exception as e:
        logger.error(f"Vector search error: {e}")
        return []


async def find_similar(
    session: AsyncSession,
    item_id: int,
    user_id: int,
    limit: int = 5,
    min_similarity: float = 0.7
) -> List[SearchResult]:
    """Find similar items to a given item (for auto-linking)."""
    sql = text("""
        SELECT
            i2.id,
            i2.title,
            i2.content,
            i2.type,
            1 - (i1.embedding <=> i2.embedding) AS score
        FROM items i1
        JOIN items i2 ON i1.user_id = i2.user_id AND i1.id != i2.id
        WHERE i1.id = :item_id
            AND i1.user_id = :user_id
            AND i1.embedding IS NOT NULL
            AND i2.embedding IS NOT NULL
            AND 1 - (i1.embedding <=> i2.embedding) >= :min_similarity
        ORDER BY i1.embedding <=> i2.embedding
        LIMIT :limit
    """)

    try:
        result = await session.execute(
            sql,
            {
                "item_id": item_id,
                "user_id": user_id,
                "min_similarity": min_similarity,
                "limit": limit
            }
        )

        rows = result.fetchall()
        return [
            SearchResult(
                id=row.id,
                title=row.title or "",
                content=row.content,
                type=row.type,
                score=float(row.score),
                fts_score=0.0,
                vector_score=float(row.score)
            )
            for row in rows
        ]

    except Exception as e:
        logger.error(f"Find similar error: {e}")
        return []
