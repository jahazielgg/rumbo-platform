from uuid import uuid4

import pytest

from app.positioning.domain.entities import PositioningConfig, QRAnchor
from app.shared_kernel.errors import ValidationError


def test_qr_codes_are_unique_per_floor():
    code = "rumbo://anchor/entrada"
    with pytest.raises(ValidationError):
        PositioningConfig(
            floorplan_id=uuid4(),
            qr_anchors=[
                QRAnchor(id=uuid4(), code=code, label="Entrada A", node_id=uuid4()),
                QRAnchor(id=uuid4(), code=code.upper(), label="Entrada B", node_id=uuid4()),
            ],
        )
