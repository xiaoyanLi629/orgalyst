"""路径与模型注册表。所有权重路径集中在这里，换机器只改此处或设环境变量 ORGALYST_ROOT。"""
import os
ROOT = os.environ.get("ORGALYST_ROOT", "/root/autodl-fs/AI4S")
WEIGHTS = f"{ROOT}/weights"
CELLPOSE_MODELS_DIR = os.environ.get("CELLPOSE_LOCAL_MODELS_PATH", "/root/autodl-tmp/.cellpose/models")
ORGANS = ("brain", "intestine", "pdac", "colon")
# 按器官的专用分割权重（E1 微调产物）；"diam_mode" 为该器官的默认直径策略：
#   model=模型训练直径；refine=两遍推理（第二遍用第一遍目标的中位直径）；sizemodel=cyto3 尺寸估计器逐图估计（对大目标失效，brain 不可用）
SEG_MODELS = {
    "brain":     dict(path=f"{WEIGHTS}/cellpose_ft/brain/brain",         diam_mode="refine"),   # E3 验证：两遍推理漏检 10→3、≤10% 误差 81%→93%
    "intestine": dict(path=f"{WEIGHTS}/cellpose_ft/intestine/intestine", diam_mode="sizemodel"),
    "pdac":      dict(path=f"{WEIGHTS}/cellpose_ft/pdac/pdac",           diam_mode="sizemodel"),
    "colon":     dict(path=f"{WEIGHTS}/cellpose_ft/colon/colon",         diam_mode="model"),
    "generic":   dict(path="cyto3",                                        diam_mode="sizemodel"),   # 未知器官兜底：零样本 cyto3
}
DET_MODELS = {o: f"{WEIGHTS}/yolo/{o}/weights/best.pt" for o in ("intestine", "brain", "lung", "all")}
# 检测计数默认用联合模型 all；置信度阈值在各器官 val 集上按计数 MAPE 最小标定（scripts/calibrate_det_conf.py → results/e2_conf_calibration.json，2026-09-16）：
#   intestine 0.50（test MAPE 0.26→0.21）、brain 0.45（0.018→0.004）、lung 0.40（0.235→0.168）；未知器官用三器官合并最优 0.45
DET_CONF = {"intestine": 0.50, "brain": 0.45, "lung": 0.40, "generic": 0.45}
DET_IMGSZ = 1024
# 已核实的像素物理尺寸（µm/px）；None 表示未知，只报像素单位
PIXEL_SIZE_UM = {"brain_labA_1024": 3.1646, "brain_labB_1388": 2.9940}
