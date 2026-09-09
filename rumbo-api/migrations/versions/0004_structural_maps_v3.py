"""structural mapping v3: obstacles, semantic openings, validation, scale

Revision ID: 0004_structural_maps_v3
Revises: 0003_structural_maps
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_structural_maps_v3"
down_revision = "0003_structural_maps"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("structural_maps", sa.Column("obstacle_polygons", sa.JSON(), nullable=False, server_default="[]"))
    op.add_column("structural_maps", sa.Column("validation", sa.JSON(), nullable=False, server_default="{}"))
    op.add_column("structural_maps", sa.Column("estimated_pixels_per_meter", sa.Float(), nullable=True))
    op.add_column("structural_maps", sa.Column("scale_source", sa.String(length=40), nullable=True))


def downgrade() -> None:
    op.drop_column("structural_maps", "scale_source")
    op.drop_column("structural_maps", "estimated_pixels_per_meter")
    op.drop_column("structural_maps", "validation")
    op.drop_column("structural_maps", "obstacle_polygons")
