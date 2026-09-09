"""persist structural mapping analysis

Revision ID: 0003_structural_maps
Revises: 0002_navigation_and_positioning
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_structural_maps"
down_revision = "0002_navigation_and_positioning"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "structural_maps",
        sa.Column("floorplan_id", sa.String(length=36), primary_key=True),
        sa.Column("parser", sa.String(length=120), nullable=False),
        sa.Column("parser_version", sa.String(length=40), nullable=False),
        sa.Column("image_width", sa.Integer(), nullable=False),
        sa.Column("image_height", sa.Integer(), nullable=False),
        sa.Column("wall_polygons", sa.JSON(), nullable=False),
        sa.Column("doors", sa.JSON(), nullable=False),
        sa.Column("window_polygons", sa.JSON(), nullable=False),
        sa.Column("spaces", sa.JSON(), nullable=False),
        sa.Column("walkable_areas", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["floorplan_id"], ["floorplans.id"], ondelete="CASCADE"),
    )


def downgrade() -> None:
    op.drop_table("structural_maps")
