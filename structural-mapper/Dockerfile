# syntax=docker/dockerfile:1.7
FROM python:3.11-slim

ARG BUILDINGCV_COMMIT=ccc19723d98b097b521b8289287c5143e535df0d

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_PREFER_BINARY=1 \
    BUILDINGCV_DEVICE=cpu \
    BUILDINGCV_RUN_DIR=/opt/buildingcv/weights

RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl libglib2.0-0 libgl1 \
    && rm -rf /var/lib/apt/lists/*

RUN git clone https://github.com/Yytsi/floorplan-to-3d.git /opt/buildingcv \
    && git -C /opt/buildingcv checkout "$BUILDINGCV_COMMIT" \
    && rm -rf /opt/buildingcv/.git

# The mapper runs on CPU. Installing torch from the regular PyPI index on
# linux/amd64 also pulls the CUDA runtime stack (multiple GB) even though it is
# never used. Install the official CPU wheels first; BuildingCV then reuses
# them because its torch/torchvision requirements are already satisfied.
WORKDIR /workspace/structural-mapper
COPY requirements-geometry.txt ./requirements-geometry.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --index-url https://download.pytorch.org/whl/cpu torch torchvision \
    && pip install "/opt/buildingcv[serve]" -r requirements-geometry.txt

RUN mkdir -p /opt/buildingcv/weights \
    && curl -L --retry 4 --fail -o /opt/buildingcv/weights/best.safetensors \
      https://huggingface.co/Yytsi/floorplan-to-3d-walls/resolve/main/best.safetensors \
    && curl -L --retry 4 --fail -o /opt/buildingcv/weights/config.yaml \
      https://huggingface.co/Yytsi/floorplan-to-3d-walls/resolve/main/config.yaml

COPY app.py ./app.py
COPY mapper ./mapper

EXPOSE 8010
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8010"]
