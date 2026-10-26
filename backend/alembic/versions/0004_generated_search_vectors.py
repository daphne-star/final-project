"""make search vectors generated columns

Revision ID: 0004_tsvector
Revises: 0003_subject
Create Date: 2026-10-25

The search_vector columns were populated by application code, which meant any
row written by a path that forgot to set them was invisible to search — a
silent retrieval gap rather than an error. Postgres can maintain them itself,
so it does. Generated columns cannot be inserted into, so there is no longer
a write path that can get this wrong.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004_tsvector"
down_revision: str | None = "0003_subject"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # A column cannot be converted to generated in place; drop and re-add.
    op.drop_index("ix_memory_search", table_name="company_memories")
    op.drop_column("company_memories", "search_vector")
    op.execute(
        """
        ALTER TABLE company_memories
        ADD COLUMN search_vector tsvector
        GENERATED ALWAYS AS (
            to_tsvector('english', coalesce(key, '') || ' ' || coalesce(value, ''))
        ) STORED
        """
    )
    op.create_index(
        "ix_memory_search",
        "company_memories",
        ["search_vector"],
        postgresql_using="gin",
    )

    op.drop_index("ix_chunk_search", table_name="document_chunks")
    op.drop_column("document_chunks", "search_vector")
    op.execute(
        """
        ALTER TABLE document_chunks
        ADD COLUMN search_vector tsvector
        GENERATED ALWAYS AS (to_tsvector('english', coalesce(content, ''))) STORED
        """
    )
    op.create_index(
        "ix_chunk_search",
        "document_chunks",
        ["search_vector"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    for table, index in (
        ("company_memories", "ix_memory_search"),
        ("document_chunks", "ix_chunk_search"),
    ):
        op.drop_index(index, table_name=table)
        op.drop_column(table, "search_vector")
        op.execute(f"ALTER TABLE {table} ADD COLUMN search_vector tsvector")
        op.create_index(index, table, ["search_vector"], postgresql_using="gin")
