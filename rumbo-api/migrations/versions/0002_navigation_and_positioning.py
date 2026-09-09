"""navigation, positioning and enriched modeling

Revision ID: 0002_navigation_and_positioning
Revises: 0001_initial
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_navigation_and_positioning"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "spatial_models",
        sa.Column("nodes", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )
    op.add_column(
        "spatial_models",
        sa.Column("pois", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )

    op.create_table(
        "navigation_configs",
        sa.Column("floorplan_id", sa.String(length=36), primary_key=True),
        sa.Column("edges", sa.JSON(), nullable=False),
        sa.Column("vertical_connectors", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["floorplan_id"], ["floorplans.id"], ondelete="CASCADE"),
    )
    op.create_table(
        "positioning_configs",
        sa.Column("floorplan_id", sa.String(length=36), primary_key=True),
        sa.Column("qr_anchors", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["floorplan_id"], ["floorplans.id"], ondelete="CASCADE"),
    )


def downgrade() -> None:
    op.drop_table("positioning_configs")
    op.drop_table("navigation_configs")
    op.drop_column("spatial_models", "pois")
    op.drop_column("spatial_models", "nodes")
