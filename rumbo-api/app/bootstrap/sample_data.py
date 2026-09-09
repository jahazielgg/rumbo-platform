from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from app.floorplans.domain.entities import Floorplan
from app.floorplans.infrastructure.repositories import SqlAlchemyFloorplanRepository
from app.infrastructure.settings import Settings
from app.modeling.domain.entities import MapNode, Point2D, PointOfInterest, SpatialModel, WallSegment
from app.modeling.infrastructure.repositories import SqlAlchemySpatialModelRepository
from app.navigation.domain.entities import NavigationConfig, NavigationEdge
from app.navigation.infrastructure.repositories import SqlAlchemyNavigationConfigRepository
from app.positioning.domain.entities import PositioningConfig, QRAnchor
from app.positioning.infrastructure.repositories import SqlAlchemyPositioningConfigRepository


SAMPLE_FLOORPLAN_ID = UUID("10000000-0000-4000-8000-000000000001")
SAMPLE_FILENAME = "sample-clinic-floor-1.jpg"
SAMPLE_BUILDING = "Clínica Santa María · Ejemplo"

NODE_IDS = {
    "entrada": UUID("20000000-0000-4000-8000-000000000001"),
    "recepcion": UUID("20000000-0000-4000-8000-000000000002"),
    "espera": UUID("20000000-0000-4000-8000-000000000003"),
    "cruce_oeste": UUID("20000000-0000-4000-8000-000000000004"),
    "pasillo_norte": UUID("20000000-0000-4000-8000-000000000005"),
    "consultorio_101": UUID("20000000-0000-4000-8000-000000000006"),
    "ascensor": UUID("20000000-0000-4000-8000-000000000007"),
    "escaleras": UUID("20000000-0000-4000-8000-000000000008"),
    "pasillo_norte_este": UUID("20000000-0000-4000-8000-000000000009"),
    "consultorio_103": UUID("20000000-0000-4000-8000-000000000010"),
    "banos": UUID("20000000-0000-4000-8000-000000000011"),
    "pasillo_este": UUID("20000000-0000-4000-8000-000000000012"),
    "consultorio_104": UUID("20000000-0000-4000-8000-000000000013"),
    "pasillo_sur": UUID("20000000-0000-4000-8000-000000000014"),
    "laboratorio": UUID("20000000-0000-4000-8000-000000000015"),
    "rayos_x": UUID("20000000-0000-4000-8000-000000000016"),
    "farmacia": UUID("20000000-0000-4000-8000-000000000017"),
    "salida": UUID("20000000-0000-4000-8000-000000000018"),
}


def _node(key: str, x: float, y: float, label: str, kind: str = "waypoint") -> MapNode:
    return MapNode(id=NODE_IDS[key], position=Point2D(x=x, y=y), label=label, kind=kind)


def _edge(index: int, a: str, b: str, *, accessible: bool = True) -> NavigationEdge:
    return NavigationEdge(
        id=UUID(f"30000000-0000-4000-8000-{index:012d}"),
        from_node_id=NODE_IDS[a],
        to_node_id=NODE_IDS[b],
        kind="corridor",
        accessible=accessible,
    )


def ensure_sample_data(db: Session, settings: Settings) -> None:
    """Install an idempotent, editable sample map for the guided tutorial.

    This lives in the composition/bootstrap layer intentionally: it coordinates several
    bounded contexts without making any of them depend on another one.
    """
    floorplans = SqlAlchemyFloorplanRepository(db)
    if floorplans.get(SAMPLE_FLOORPLAN_ID) is not None:
        return

    asset_path = Path(__file__).resolve().parents[2] / "assets" / SAMPLE_FILENAME
    settings.upload_path.mkdir(parents=True, exist_ok=True)
    target_path = settings.upload_path / SAMPLE_FILENAME
    if not target_path.exists():
        target_path.write_bytes(asset_path.read_bytes())

    floorplan = Floorplan(
        id=SAMPLE_FLOORPLAN_ID,
        name="Ejemplo guiado · Clínica Santa María",
        building_name=SAMPLE_BUILDING,
        floor_label="Piso 1",
        original_filename=SAMPLE_FILENAME,
        stored_filename=SAMPLE_FILENAME,
        media_type="image/jpeg",
        created_at=datetime.now(timezone.utc),
    )
    floorplans.add(floorplan)

    nodes = [
        _node("entrada", 145, 520, "Entrada", "entrance"),
        _node("recepcion", 345, 520, "Recepción", "decision"),
        _node("espera", 590, 520, "Sala de espera", "decision"),
        _node("cruce_oeste", 785, 520, "Cruce central", "decision"),
        _node("pasillo_norte", 785, 300, "Pasillo norte", "decision"),
        _node("consultorio_101", 650, 300, "Acceso C101", "waypoint"),
        _node("ascensor", 550, 300, "Ascensor", "decision"),
        _node("escaleras", 435, 300, "Escaleras", "decision"),
        _node("pasillo_norte_este", 1190, 300, "Pasillo norte este", "decision"),
        _node("consultorio_103", 1085, 300, "Acceso C103", "waypoint"),
        _node("banos", 1320, 300, "Baños", "waypoint"),
        _node("pasillo_este", 1190, 520, "Pasillo este", "decision"),
        _node("consultorio_104", 1260, 520, "Acceso C104", "waypoint"),
        _node("pasillo_sur", 785, 680, "Pasillo sur", "decision"),
        _node("laboratorio", 545, 680, "Laboratorio", "waypoint"),
        _node("rayos_x", 750, 680, "Rayos X", "waypoint"),
        _node("farmacia", 1015, 680, "Farmacia", "waypoint"),
        _node("salida", 1300, 680, "Salida emergencia", "waypoint"),
    ]

    walls = [
        WallSegment(id=UUID("40000000-0000-4000-8000-000000000001"), start=Point2D(330, 30), end=Point2D(1220, 30)),
        WallSegment(id=UUID("40000000-0000-4000-8000-000000000002"), start=Point2D(1220, 30), end=Point2D(1220, 345)),
        WallSegment(id=UUID("40000000-0000-4000-8000-000000000003"), start=Point2D(120, 325), end=Point2D(120, 680)),
        WallSegment(id=UUID("40000000-0000-4000-8000-000000000004"), start=Point2D(120, 680), end=Point2D(1450, 680)),
        WallSegment(id=UUID("40000000-0000-4000-8000-000000000005"), start=Point2D(810, 345), end=Point2D(1130, 345)),
        WallSegment(id=UUID("40000000-0000-4000-8000-000000000006"), start=Point2D(1130, 345), end=Point2D(1130, 635)),
        WallSegment(id=UUID("40000000-0000-4000-8000-000000000007"), start=Point2D(1130, 635), end=Point2D(810, 635)),
        WallSegment(id=UUID("40000000-0000-4000-8000-000000000008"), start=Point2D(810, 635), end=Point2D(810, 345)),
    ]

    pois = [
        PointOfInterest(id=UUID("50000000-0000-4000-8000-000000000001"), name="Recepción", category="servicio", position=Point2D(355, 535), node_id=NODE_IDS["recepcion"]),
        PointOfInterest(id=UUID("50000000-0000-4000-8000-000000000002"), name="Consultorio 101", category="consultorio", position=Point2D(730, 175), node_id=NODE_IDS["consultorio_101"]),
        PointOfInterest(id=UUID("50000000-0000-4000-8000-000000000003"), name="Consultorio 103", category="consultorio", position=Point2D(1115, 175), node_id=NODE_IDS["consultorio_103"]),
        PointOfInterest(id=UUID("50000000-0000-4000-8000-000000000004"), name="Baños de pacientes", category="servicio", position=Point2D(1370, 180), node_id=NODE_IDS["banos"]),
        PointOfInterest(id=UUID("50000000-0000-4000-8000-000000000005"), name="Consultorio 104", category="consultorio", position=Point2D(1370, 430), node_id=NODE_IDS["consultorio_104"]),
        PointOfInterest(id=UUID("50000000-0000-4000-8000-000000000006"), name="Laboratorio", category="servicio", position=Point2D(525, 770), node_id=NODE_IDS["laboratorio"]),
        PointOfInterest(id=UUID("50000000-0000-4000-8000-000000000007"), name="Rayos X", category="servicio", position=Point2D(750, 770), node_id=NODE_IDS["rayos_x"]),
        PointOfInterest(id=UUID("50000000-0000-4000-8000-000000000008"), name="Farmacia", category="servicio", position=Point2D(1015, 770), node_id=NODE_IDS["farmacia"]),
        PointOfInterest(id=UUID("50000000-0000-4000-8000-000000000009"), name="Salida de emergencia", category="salida", position=Point2D(1300, 770), node_id=NODE_IDS["salida"]),
    ]

    SqlAlchemySpatialModelRepository(db).save(
        SpatialModel(
            floorplan_id=SAMPLE_FLOORPLAN_ID,
            pixels_per_meter=20.3,  # La barra de escala impresa: ~203 px = 10 m.
            walls=walls,
            nodes=nodes,
            pois=pois,
        )
    )

    edges = [
        _edge(1, "entrada", "recepcion"),
        _edge(2, "recepcion", "espera"),
        _edge(3, "espera", "cruce_oeste"),
        _edge(4, "cruce_oeste", "pasillo_norte"),
        _edge(5, "pasillo_norte", "consultorio_101"),
        _edge(6, "consultorio_101", "ascensor"),
        _edge(7, "ascensor", "escaleras"),
        _edge(8, "pasillo_norte", "pasillo_norte_este"),
        _edge(9, "pasillo_norte_este", "consultorio_103"),
        _edge(10, "pasillo_norte_este", "banos"),
        _edge(11, "pasillo_norte_este", "pasillo_este"),
        _edge(12, "cruce_oeste", "pasillo_este"),
        _edge(13, "pasillo_este", "consultorio_104"),
        _edge(14, "cruce_oeste", "pasillo_sur"),
        _edge(15, "pasillo_sur", "laboratorio"),
        _edge(16, "pasillo_sur", "rayos_x"),
        _edge(17, "pasillo_sur", "farmacia"),
        _edge(18, "farmacia", "salida"),
    ]
    SqlAlchemyNavigationConfigRepository(db).save(
        NavigationConfig(floorplan_id=SAMPLE_FLOORPLAN_ID, edges=edges, vertical_connectors=[])
    )

    SqlAlchemyPositioningConfigRepository(db).save(
        PositioningConfig(
            floorplan_id=SAMPLE_FLOORPLAN_ID,
            qr_anchors=[
                QRAnchor(id=UUID("60000000-0000-4000-8000-000000000001"), code="rumbo://sample/entrada", label="QR Entrada principal", node_id=NODE_IDS["entrada"]),
                QRAnchor(id=UUID("60000000-0000-4000-8000-000000000002"), code="rumbo://sample/ascensor", label="QR Ascensor", node_id=NODE_IDS["ascensor"]),
            ],
        )
    )
