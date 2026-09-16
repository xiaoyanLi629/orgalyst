# OrgLine 数据集说明

- Zenodo 记录：https://zenodo.org/records/16355179（发布 2025-02-25，许可证 CC-BY-4.0；原始图像与标注沿用各自原许可证）
- 论文：OrgLine: A versatile pipeline for organoid morphometry using detector-guided prompts（Cell Reports Methods 2026，PMC13494547）
- 文件：`OrgDet.zip`（1.91 GB，md5 5a3cf0c001c387cf641456f6d0ccb153）、`InstanceSeg.zip`（1.75 GB，md5 6ddc154981785f48cf97f682d6c40e3c）

## 内容

**Part 1 目标检测（OrgDet）**
- 肠类器官：来自 Tellu、OrgaQuant、OrgaSegment；Tellu 子集的松散检测框已人工收紧。
- 肺球体：来自 DeepLUMEN；原标注只区分 lumen / no lumen，OrgLine 补标了被忽略的非失焦类器官。
- 脑类器官：来自 Schröter et al. 2024，转为统一检测格式。

**Part 2 实例分割（InstanceSeg）**
- 胰腺导管腺癌（PDAC）：来自 OrganoID（原为语义分割，OrgLine 人工拆成实例掩码）与 OrganoidNet。
- 其他：肠（OrgaSegment）、脑（Schröter et al.）、结肠（OrgaExtractor）。

## 原始来源（引用时须同时引用 OrgLine 与对应原始数据集）

| 器官 | 原始数据集 | 文献 | 地址 |
|---|---|---|---|
| 肠 | OrgaQuant | Kassis et al. 2019 | https://osf.io/etz8r |
| 肠 | OrgaSegment | Lefferts et al. 2024 | https://doi.org/10.5281/zenodo.10278229 |
| 肠 | Tellu | Domènech-Moreno et al. 2023 | https://doi.org/10.5281/zenodo.6768583 |
| 脑 | Brain Organoid | Schröter et al. 2024 | https://doi.org/10.5281/zenodo.10301912 |
| 肺 | DeepLUMEN | Abdul et al. 2021 | https://osf.io/g2a7r/ |
| 结肠 | OrgaExtractor | Park et al. 2023 | https://github.com/tpark16/orgaextractor |
| PDAC | OrganoID | Matthews et al. 2022 | https://osf.io/xmes4/ |
| PDAC | OrganoidNet | Ferreira et al. 2025 | https://zenodo.org/records/10643410 |

## 合规说明（写入技术报告）

全部为公开数据集，无个人/临床受限数据；OrgLine 精修标注为 CC-BY-4.0，原始图像遵循各自许可证；本项目不使用任何公司内部数据。
