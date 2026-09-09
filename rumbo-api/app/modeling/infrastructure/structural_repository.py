from sqlalchemy.orm import Session

from ..domain.structural import StructuralMap, StructuralPolygon
from ..domain.structural_repositories import StructuralMapRepository
from .models import StructuralMapRecord


def _polygon_payload(polygon: StructuralPolygon) -> dict:
    return {
        "outer": [[point.x, point.y] for point in polygon.outer],
        "holes": [[[point.x, point.y] for point in ring] for ring in polygon.holes],
    }


class SqlAlchemyStructuralMapRepository(StructuralMapRepository):
    def __init__(self, db: Session):
        self.db = db

    def save(self, structural_map: StructuralMap) -> StructuralMap:
        payload = {
            "parser": structural_map.parser,
            "parser_version": structural_map.parser_version,
            "image_width": structural_map.image_width,
            "image_height": structural_map.image_height,
            "wall_polygons": [_polygon_payload(item) for item in structural_map.wall_polygons],
            "obstacle_polygons": [_polygon_payload(item) for item in structural_map.obstacle_polygons],
            "doors": [
                {
                    "id": str(item.id),
                    "kind": item.kind,
                    "confidence": item.confidence,
                    "width_px": item.width_px,
                    "center": [item.center.x, item.center.y] if item.center else None,
                    "spaces": list(item.space_keys),
                    "source_key": item.source_key,
                    "polygon": _polygon_payload(item.polygon),
                }
                for item in structural_map.doors
            ],
            "window_polygons": [_polygon_payload(item) for item in structural_map.window_polygons],
            "spaces": [
                {
                    "id": str(item.id),
                    "kind": item.kind,
                    "label": item.label,
                    "connector_kind": item.connector_kind,
                    "confidence": item.confidence,
                    "source_key": item.source_key,
                    "polygon": _polygon_payload(item.polygon),
                }
                for item in structural_map.spaces
            ],
            "walkable_areas": [
                {"id": str(item.id), "kind": item.kind, "polygon": _polygon_payload(item.polygon)}
                for item in structural_map.walkable_areas
            ],
            "validation": {
                "status": structural_map.validation.status,
                "issues": [
                    {"code": i.code, "severity": i.severity, "message": i.message, "subjects": list(i.subjects)}
                    for i in structural_map.validation.issues
                ],
                "metrics": dict(structural_map.validation.metrics),
            },
            "estimated_pixels_per_meter": structural_map.estimated_pixels_per_meter,
            "scale_source": structural_map.scale_source,
        }
        record = self.db.get(StructuralMapRecord, str(structural_map.floorplan_id))
        if record is None:
            record = StructuralMapRecord(floorplan_id=str(structural_map.floorplan_id), **payload)
            self.db.add(record)
        else:
            for key, value in payload.items():
                setattr(record, key, value)
        self.db.commit()
        return structural_map
