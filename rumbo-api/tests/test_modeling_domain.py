from uuid import uuid4

import pytest

from app.modeling.domain.entities import MapNode, Point2D, PointOfInterest, SpatialModel, WallSegment, pixel_distance
from app.shared_kernel.errors import ValidationError


def test_pixel_distance():
    assert pixel_distance(Point2D(0, 0), Point2D(3, 4)) == 5


def test_calibration_and_measurement():
    model = SpatialModel(floorplan_id=uuid4())
    model.calibrate(a=Point2D(0, 0), b=Point2D(500, 0), meters=10)
    assert model.pixels_per_meter == 50
    assert model.meters_between(Point2D(0, 0), Point2D(250, 0)) == 5


def test_wall_rejects_zero_length():
    with pytest.raises(ValidationError):
        WallSegment.create(Point2D(10, 10), Point2D(10, 10))


def test_poi_must_reference_existing_node():
    with pytest.raises(ValidationError):
        SpatialModel(
            floorplan_id=uuid4(),
            nodes=[MapNode(id=uuid4(), position=Point2D(10, 10), label="N1")],
            pois=[PointOfInterest(id=uuid4(), name="Caja", category="atencion", position=Point2D(20, 20), node_id=uuid4())],
        )
