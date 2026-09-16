# Orgalyst：类器官明场图像分析工具包（命令行路径，不需要任何大模型）。
# 构建：docker build -t orgalyst .
# 运行：docker run --gpus all -v /path/to/images:/data -v $PWD/runs:/runs orgalyst analyze --organ intestine --images /data --out /runs
FROM pytorch/pytorch:2.4.0-cuda12.4-cudnn9-runtime
ENV DEBIAN_FRONTEND=noninteractive PIP_NO_CACHE_DIR=1 CELLPOSE_LOCAL_MODELS_PATH=/weights/cellpose ORGALYST_ROOT=/app YOLO_OFFLINE=1
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 aria2 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY orgalyst ./orgalyst
COPY scripts ./scripts
COPY configs ./configs
# 权重不进镜像：运行前执行 scripts/download_weights.sh，或把已下载的 weights/ 挂到 /app/weights
ENTRYPOINT ["python", "-m", "orgalyst"]
