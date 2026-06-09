"""训练数据集管理路由：列表 / 增删 / 版本 / 预览 / 统计。"""
from __future__ import annotations

import csv
import io
import json
import os
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, select, delete
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import get_db
from app.db.models import Dataset, DatasetVersion
from app.registry.model_registry import SCENE_CATALOG, MODEL_REGISTRY
from app.schemas.model import (
    DatasetBrief,
    DatasetDetail,
    DatasetVersionBrief,
    YoloObject,
    YoloPreviewItem,
)

router = APIRouter()

SCENE_CODES = {s["code"] for s in SCENE_CATALOG}
VALID_FORMATS = {"csv", "txt", "jpg", "png", "mp4", "zip"}
ALLOWED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}


# ── helpers ────────────────────────────────────────────────────────────────────────

def _dataset_dir(scene: str, model_code: str) -> Path:
    return Path(settings.data_dir) / "datasets" / scene / model_code


def _row_to_brief(row: Dataset, version_count: int = 0) -> DatasetBrief:
    return DatasetBrief(
        id=row.id,
        name=row.name,
        scene=row.scene,
        model_code=row.model_code,
        format=row.format,
        dataset_type=row.dataset_type,
        description=row.description,
        classes=json.loads(row.classes_json) if row.classes_json else None,
        image_count=row.image_count,
        label_count=row.label_count,
        sample_count=row.sample_count,
        file_count=row.file_count,
        size_bytes=row.size_bytes,
        current_version=row.current_version,
        version_count=version_count,
        created_at=row.created_at,
    )


def _row_to_detail(row: Dataset, versions: list[DatasetVersion]) -> DatasetDetail:
    vc = len(versions)
    return DatasetDetail(
        id=row.id,
        name=row.name,
        scene=row.scene,
        model_code=row.model_code,
        format=row.format,
        dataset_type=row.dataset_type,
        description=row.description,
        classes=json.loads(row.classes_json) if row.classes_json else None,
        image_count=row.image_count,
        label_count=row.label_count,
        sample_count=row.sample_count,
        file_count=row.file_count,
        size_bytes=row.size_bytes,
        current_version=row.current_version,
        version_count=vc,
        schema_json=row.schema_json,
        updated_at=row.updated_at,
        created_at=row.created_at,
        versions=[
            DatasetVersionBrief(
                id=v.id,
                version=v.version,
                file_count=v.file_count,
                sample_count=v.sample_count,
                size_bytes=v.size_bytes,
                created_at=v.created_at,
            )
            for v in versions
        ],
    )


def _parse_yolo_classes(extract_dir: Path) -> list[str] | None:
    """从 classes.txt 或 dataset.yaml 解析 YOLO 类别名列表。"""
    # 优先 classes.txt
    ct = extract_dir / "classes.txt"
    if ct.exists():
        return [line.strip() for line in ct.read_text(encoding="utf-8").splitlines() if line.strip()]

    # 其次 dataset.yaml
    dy = extract_dir / "dataset.yaml"
    if dy.exists():
        try:
            import yaml
            data = yaml.safe_load(dy.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "names" in data:
                names = data["names"]
                if isinstance(names, dict):
                    return [names[i] for i in sorted(names)]
                if isinstance(names, list):
                    return names
        except Exception:
            pass
    return None


def _scan_extracted_dir(extract_dir: Path) -> dict:
    """扫描解压后的目录，返回统计信息。

    Returns:
        dict 含 dataset_type, format, classes, image_count, label_count,
        sample_count, file_count, size_bytes
    """
    result = {
        "dataset_type": "general",
        "format": "zip",
        "classes": None,
        "image_count": 0,
        "label_count": 0,
        "sample_count": 0,
        "file_count": 0,
        "size_bytes": 0,
    }

    # 检测是否为 YOLO 格式
    labels_dir = extract_dir / "labels"
    images_dir = extract_dir / "images"
    is_yolo = labels_dir.exists() and labels_dir.is_dir()

    if is_yolo:
        result["dataset_type"] = "yolo_detection"
        result["classes"] = _parse_yolo_classes(extract_dir)

    # 统计文件
    for f in extract_dir.rglob("*"):
        if not f.is_file():
            continue
        result["file_count"] += 1
        result["size_bytes"] += f.stat().st_size

        if is_yolo:
            # 判断相对路径
            try:
                rel = f.relative_to(extract_dir)
            except ValueError:
                continue
            parts = rel.parts
            if parts[0] == "images" and f.suffix.lower() in ALLOWED_IMAGE_EXTS:
                result["image_count"] += 1
            elif parts[0] == "labels" and f.suffix == ".txt":
                try:
                    lines = f.read_text(encoding="utf-8").strip().splitlines()
                    result["label_count"] += len([l for l in lines if l.strip()])
                except Exception:
                    pass
        else:
            # 通用模式：检测 CSV 文件
            if f.suffix.lower() == ".csv":
                result["format"] = "csv"
                try:
                    with open(f, encoding="utf-8") as fh:
                        reader = csv.reader(fh)
                        rows = sum(1 for _ in reader) - 1  # 减去表头
                        if rows > 0:
                            result["sample_count"] += rows
                except Exception:
                    pass
            elif f.suffix.lower() == ".txt":
                result["format"] = "txt"
            elif f.suffix.lower() in ALLOWED_IMAGE_EXTS:
                result["format"] = f.suffix.lower().lstrip(".")
                result["image_count"] += 1

    return result


def _safe_extract(zip_file: zipfile.ZipFile, target_dir: Path) -> None:
    """安全解压 ZIP，过滤路径遍历攻击。"""
    target_dir = target_dir.resolve()
    for member in zip_file.infolist():
        # 过滤路径遍历
        member_path = (target_dir / member.filename).resolve()
        if not str(member_path).startswith(str(target_dir)):
            raise HTTPException(status_code=400, detail=f"ZIP 包含非法路径: {member.filename}")
        if member.is_dir():
            member_path.mkdir(parents=True, exist_ok=True)
        else:
            member_path.parent.mkdir(parents=True, exist_ok=True)
            with zip_file.open(member) as src, open(member_path, "wb") as dst:
                shutil.copyfileobj(src, dst)


# ── API 端点 ────────────────────────────────────────────────────────────────────────

@router.get("", response_model=dict)
def list_datasets(
    scene: Optional[str] = Query(None, description="按场景过滤"),
    format: Optional[str] = Query(None, description="按格式过滤"),
    dataset_type: Optional[str] = Query(None, description="general / yolo_detection"),
    model_code: Optional[str] = Query(None, description="按模型编码过滤"),
    db: Session = Depends(get_db),
):
    stmt = select(Dataset)
    if scene:
        stmt = stmt.where(Dataset.scene == scene)
    if format:
        stmt = stmt.where(Dataset.format == format)
    if dataset_type:
        stmt = stmt.where(Dataset.dataset_type == dataset_type)
    if model_code:
        stmt = stmt.where(Dataset.model_code == model_code)

    rows = db.execute(stmt.order_by(Dataset.created_at.desc())).scalars().all()

    # 批量查询各 dataset 的版本数
    ds_ids = [r.id for r in rows]
    vc_map: dict[int, int] = {}
    if ds_ids:
        vc_rows = (
            db.execute(
                select(DatasetVersion.dataset_id, func.count(DatasetVersion.id))
                .where(DatasetVersion.dataset_id.in_(ds_ids))
                .group_by(DatasetVersion.dataset_id)
            )
            .all()
        )
        vc_map = {row[0]: row[1] for row in vc_rows}

    return {
        "code": 0,
        "total": len(rows),
        "data": [_row_to_brief(r, vc_map.get(r.id, 0)).model_dump() for r in rows],
    }


@router.post("", response_model=dict)
async def create_dataset(
    file: UploadFile = File(...),
    name: str = Form(...),
    scene: str = Form(...),
    model_code: str = Form(...),
    description: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    # 校验 scene
    if scene not in SCENE_CODES:
        raise HTTPException(status_code=400, detail=f"无效场景: {scene}，有效值: {SCENE_CODES}")

    # 校验 model_code
    if model_code not in MODEL_REGISTRY:
        raise HTTPException(status_code=400, detail=f"无效模型编码: {model_code}")

    # 校验 ZIP 文件
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="仅支持 .zip 文件上传")

    # 检查是否已存在同名数据集
    existing = (
        db.execute(
            select(Dataset).where(
                Dataset.scene == scene,
                Dataset.model_code == model_code,
            )
        )
        .scalars()
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail=f"数据集 {scene}/{model_code} 已存在，请上传新版本")

    # 目标目录
    target_dir = _dataset_dir(scene, model_code)
    target_dir.mkdir(parents=True, exist_ok=True)

    # 读取上传内容到内存
    zip_bytes = await file.read()

    # 解压
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            _safe_extract(zf, target_dir)
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="无效的 ZIP 文件")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"解压失败: {e}")

    # 扫描目录
    scan = _scan_extracted_dir(target_dir)

    # 写入 metadata.json
    meta = {
        "name": name,
        "scene": scene,
        "model_code": model_code,
        "description": description,
        "dataset_type": scan["dataset_type"],
        "format": scan["format"],
        "classes": scan["classes"],
        "image_count": scan["image_count"],
        "label_count": scan["label_count"],
        "sample_count": scan["sample_count"],
        "file_count": scan["file_count"],
        "size_bytes": scan["size_bytes"],
        "updated_at": datetime.now().isoformat(),
    }
    (target_dir / "metadata.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # 创建 dataset 记录
    ds = Dataset(
        name=name,
        scene=scene,
        model_code=model_code,
        format=scan["format"],
        dataset_type=scan["dataset_type"],
        description=description,
        classes_json=json.dumps(scan["classes"], ensure_ascii=False) if scan["classes"] else None,
        image_count=scan["image_count"],
        label_count=scan["label_count"],
        sample_count=scan["sample_count"],
        file_count=scan["file_count"],
        size_bytes=scan["size_bytes"],
        current_version="v1",
    )
    db.add(ds)
    db.flush()

    # 创建 v1 版本记录
    rel_path = f"{scene}/{model_code}"
    dv = DatasetVersion(
        dataset_id=ds.id,
        version="v1",
        file_path=rel_path,
        file_count=scan["file_count"],
        sample_count=scan["sample_count"],
        size_bytes=scan["size_bytes"],
    )
    db.add(dv)
    db.commit()
    db.refresh(ds)

    return {"code": 0, "data": _row_to_detail(ds, [dv]).model_dump()}


@router.get("/{ds_id}", response_model=dict)
def get_dataset(ds_id: int, db: Session = Depends(get_db)):
    row = db.get(Dataset, ds_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"数据集 {ds_id} 不存在")
    versions = (
        db.execute(
            select(DatasetVersion)
            .where(DatasetVersion.dataset_id == ds_id)
            .order_by(DatasetVersion.created_at.desc())
        )
        .scalars()
        .all()
    )
    return {"code": 0, "data": _row_to_detail(row, versions).model_dump()}


@router.delete("/{ds_id}", response_model=dict)
def delete_dataset(ds_id: int, db: Session = Depends(get_db)):
    row = db.get(Dataset, ds_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"数据集 {ds_id} 不存在")

    # 删除物理文件
    target_dir = _dataset_dir(row.scene, row.model_code or "")
    if target_dir.exists():
        shutil.rmtree(target_dir, ignore_errors=True)

    # 删除版本记录
    db.execute(delete(DatasetVersion).where(DatasetVersion.dataset_id == ds_id))
    db.delete(row)
    db.commit()
    return {"code": 0, "message": "已删除"}


@router.post("/{ds_id}/versions", response_model=dict)
async def upload_version(
    ds_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    row = db.get(Dataset, ds_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"数据集 {ds_id} 不存在")

    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="仅支持 .zip 文件上传")

    # 确定下一版本号
    max_v = (
        db.execute(
            select(DatasetVersion.version)
            .where(DatasetVersion.dataset_id == ds_id)
        )
        .scalars()
        .all()
    )
    nums = []
    for v in max_v:
        try:
            nums.append(int(v.lstrip("v")))
        except ValueError:
            pass
    next_num = max(nums) + 1 if nums else 1
    next_ver = f"v{next_num}"

    # 覆盖写入目标目录
    target_dir = _dataset_dir(row.scene, row.model_code or "")
    if target_dir.exists():
        shutil.rmtree(target_dir, ignore_errors=True)
    target_dir.mkdir(parents=True, exist_ok=True)

    zip_bytes = await file.read()
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            _safe_extract(zf, target_dir)
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="无效的 ZIP 文件")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"解压失败: {e}")

    scan = _scan_extracted_dir(target_dir)

    # 更新 dataset 行
    row.format = scan["format"]
    row.dataset_type = scan["dataset_type"]
    row.classes_json = json.dumps(scan["classes"], ensure_ascii=False) if scan["classes"] else None
    row.image_count = scan["image_count"]
    row.label_count = scan["label_count"]
    row.sample_count = scan["sample_count"]
    row.file_count = scan["file_count"]
    row.size_bytes = scan["size_bytes"]
    row.current_version = next_ver
    row.updated_at = datetime.now()

    rel_path = f"{row.scene}/{row.model_code}"
    dv = DatasetVersion(
        dataset_id=ds_id,
        version=next_ver,
        file_path=rel_path,
        file_count=scan["file_count"],
        sample_count=scan["sample_count"],
        size_bytes=scan["size_bytes"],
    )
    db.add(dv)
    db.commit()

    # 重新获取版本列表
    versions = (
        db.execute(
            select(DatasetVersion)
            .where(DatasetVersion.dataset_id == ds_id)
            .order_by(DatasetVersion.created_at.desc())
        )
        .scalars()
        .all()
    )
    return {"code": 0, "data": _row_to_detail(row, versions).model_dump()}


@router.delete("/{ds_id}/versions/{vid}", response_model=dict)
def delete_version(ds_id: int, vid: int, db: Session = Depends(get_db)):
    row = db.get(Dataset, ds_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"数据集 {ds_id} 不存在")

    dv = db.get(DatasetVersion, vid)
    if dv is None or dv.dataset_id != ds_id:
        raise HTTPException(status_code=404, detail=f"版本 {vid} 不存在")

    db.delete(dv)
    db.commit()
    return {"code": 0, "message": f"版本 {vid} 已删除"}


@router.get("/{ds_id}/preview", response_model=dict)
def preview_dataset(
    ds_id: int,
    page: int = Query(1, ge=1),
    size: Optional[int] = Query(None, ge=1, le=200),
    db: Session = Depends(get_db),
):
    row = db.get(Dataset, ds_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"数据集 {ds_id} 不存在")

    target_dir = _dataset_dir(row.scene, row.model_code or "")
    if not target_dir.exists():
        return {"code": 0, "data": {"type": "empty", "content": []}}

    page_size = size or settings.dataset_preview_page_size
    max_rows = settings.dataset_preview_max

    # ── YOLO / CSV / 图片 统一走分页 ────────────────────────────────────────────

    if row.dataset_type == "yolo_detection":
        images_dir = target_dir / "images"
        if not images_dir.exists():
            return {"code": 0, "data": {"type": "yolo_detection", "items": [], "total": 0, "page": page, "page_size": page_size, "total_pages": 0}}

        all_images = sorted(
            [f for f in images_dir.iterdir() if f.suffix.lower() in ALLOWED_IMAGE_EXTS]
        )
        total = min(len(all_images), max_rows)
        total_pages = max((total + page_size - 1) // page_size, 1)
        start = (page - 1) * page_size
        end = min(start + page_size, total)
        page_images = all_images[start:end]

        items = []
        labels_dir = target_dir / "labels"
        classes = json.loads(row.classes_json) if row.classes_json else []

        for img_file in page_images:
            label_file = labels_dir / f"{img_file.stem}.txt"
            objects = []
            if label_file.exists():
                try:
                    for line in label_file.read_text(encoding="utf-8").strip().splitlines():
                        parts = line.strip().split()
                        if len(parts) >= 5:
                            cid = int(parts[0])
                            cx, cy, w, h = float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])
                            cname = classes[cid] if 0 <= cid < len(classes) else str(cid)
                            objects.append(
                                {"class_id": cid, "class_name": cname, "cx": cx, "cy": cy, "w": w, "h": h}
                            )
                except Exception:
                    pass
            items.append({
                "image_url": f"/api/datasets/{ds_id}/files/{row.scene}/{row.model_code}/images/{img_file.name}",
                "image_file": img_file.name,
                "objects": objects,
            })

        return {
            "code": 0,
            "data": {
                "type": "yolo_detection",
                "items": items,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
            },
        }

    # ── CSV 预览（流式读取，避免 OOM） ────────────────────────────────────────
    if row.format == "csv":
        csv_files = list(target_dir.rglob("*.csv"))
        if not csv_files:
            return {
                "code": 0,
                "data": {"type": "csv", "columns": [], "rows": [], "total_rows": 0, "page": page, "page_size": page_size, "total_pages": 0},
            }

        cf = csv_files[0]
        try:
            with open(cf, encoding="utf-8") as fh:
                reader = csv.reader(fh)
                columns = next(reader)  # 表头
                skip = (page - 1) * page_size
                rows = []
                row_count = 0
                for row in reader:
                    row_count += 1
                    if row_count > max_rows:
                        break
                    if row_count > skip and len(rows) < page_size:
                        rows.append(dict(zip(columns, row)))

                total_rows = row_count
                total_pages = max((total_rows + page_size - 1) // page_size, 1) if total_rows > 0 else 0

            return {
                "code": 0,
                "data": {
                    "type": "csv",
                    "columns": columns,
                    "rows": rows,
                    "total_rows": total_rows,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": total_pages,
                },
            }
        except Exception as e:
            return {"code": 0, "data": {"type": "csv", "columns": [], "rows": [], "error": str(e)}}

    # ── 图片预览（分页） ──────────────────────────────────────────────────────
    if row.format in {"jpg", "png", "jpeg", "gif", "webp", "bmp"}:
        all_images = sorted(
            [
                f
                for f in target_dir.rglob("*")
                if f.is_file() and f.suffix.lower() in ALLOWED_IMAGE_EXTS
            ]
        )
        total = min(len(all_images), max_rows)
        total_pages = max((total + page_size - 1) // page_size, 1)
        start = (page - 1) * page_size
        end = min(start + page_size, total)
        page_images = all_images[start:end]

        items = [
            {
                "image_url": f"/api/datasets/{ds_id}/files/{p.relative_to(Path(settings.data_dir) / 'datasets').as_posix()}",
                "image_file": p.name,
            }
            for p in page_images
        ]
        return {
            "code": 0,
            "data": {
                "type": "image",
                "items": items,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
            },
        }

    return {"code": 0, "data": {"type": "unsupported", "content": []}}


@router.get("/{ds_id}/yolo-preview", response_model=dict)
def yolo_preview(
    ds_id: int,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    row = db.get(Dataset, ds_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"数据集 {ds_id} 不存在")

    if row.dataset_type != "yolo_detection":
        raise HTTPException(status_code=400, detail="仅支持 YOLO 数据集")

    target_dir = _dataset_dir(row.scene, row.model_code or "")
    images_dir = target_dir / "images"
    labels_dir = target_dir / "labels"
    classes = json.loads(row.classes_json) if row.classes_json else []

    if not images_dir.exists():
        return {"code": 0, "data": {"items": [], "total": 0, "page": page, "page_size": size}}

    all_images = sorted(
        [f for f in images_dir.iterdir() if f.suffix.lower() in ALLOWED_IMAGE_EXTS]
    )
    total = len(all_images)
    start = (page - 1) * size
    end = start + size
    page_images = all_images[start:end]

    items = []
    for img_file in page_images:
        label_file = labels_dir / f"{img_file.stem}.txt"
        objects = []
        if label_file.exists():
            try:
                for line in label_file.read_text(encoding="utf-8").strip().splitlines():
                    parts = line.strip().split()
                    if len(parts) >= 5:
                        cid = int(parts[0])
                        cx, cy, w, h = float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])
                        cname = classes[cid] if 0 <= cid < len(classes) else str(cid)
                        objects.append(
                            YoloObject(
                                class_id=cid,
                                class_name=cname,
                                cx=cx,
                                cy=cy,
                                w=w,
                                h=h,
                            )
                        )
            except Exception:
                pass

        items.append(
            YoloPreviewItem(
                image_url=f"/api/datasets/{ds_id}/files/{row.scene}/{row.model_code}/images/{img_file.name}",
                image_file=img_file.name,
                objects=objects,
            )
        )

    return {
        "code": 0,
        "data": {
            "items": [it.model_dump() for it in items],
            "total": total,
            "page": page,
            "page_size": size,
        },
    }


@router.get("/{ds_id}/files/{file_path:path}")
def serve_file(ds_id: int, file_path: str, db: Session = Depends(get_db)):
    """静态文件访问：图片/视频等。"""
    row = db.get(Dataset, ds_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"数据集 {ds_id} 不存在")

    # 安全检查：文件路径必须在 datasets 目录下
    datasets_root = (Path(settings.data_dir) / "datasets").resolve()
    full_path = (datasets_root / file_path).resolve()
    if not str(full_path).startswith(str(datasets_root)):
        raise HTTPException(status_code=403, detail="禁止访问")

    if not full_path.exists() or not full_path.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")

    return FileResponse(full_path)


@router.get("/{ds_id}/stats", response_model=dict)
def dataset_stats(ds_id: int, db: Session = Depends(get_db)):
    row = db.get(Dataset, ds_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"数据集 {ds_id} 不存在")

    target_dir = _dataset_dir(row.scene, row.model_code or "")

    if row.dataset_type == "yolo_detection":
        # YOLO 统计：各类别标注框数量分布
        labels_dir = target_dir / "labels"
        class_counts: dict[str, int] = {}
        classes = json.loads(row.classes_json) if row.classes_json else []
        if labels_dir.exists():
            for lf in labels_dir.glob("*.txt"):
                try:
                    for line in lf.read_text(encoding="utf-8").strip().splitlines():
                        parts = line.strip().split()
                        if parts:
                            cid = int(parts[0])
                            cname = classes[cid] if 0 <= cid < len(classes) else str(cid)
                            class_counts[cname] = class_counts.get(cname, 0) + 1
                except Exception:
                    pass
        return {
            "code": 0,
            "data": {
                "type": "yolo_detection",
                "image_count": row.image_count,
                "label_count": row.label_count,
                "class_distribution": [
                    {"name": k, "count": v} for k, v in sorted(class_counts.items(), key=lambda x: -x[1])
                ],
            },
        }

    # CSV 统计
    if row.format == "csv":
        csv_files = list(target_dir.rglob("*.csv"))
        if not csv_files:
            return {"code": 0, "data": {"type": "csv", "columns": [], "missing_rates": {}, "total_rows": 0}}

        cf = csv_files[0]
        try:
            with open(cf, encoding="utf-8") as fh:
                reader = csv.reader(fh)
                rows = list(reader)
            columns = rows[0] if rows else []
            data_rows = rows[1:]
            total_rows = len(data_rows)
            missing_rates = {}
            if columns and data_rows:
                for ci, col in enumerate(columns):
                    missing = sum(1 for r in data_rows if ci >= len(r) or r[ci].strip() == "")
                    missing_rates[col] = round(missing / total_rows * 100, 2) if total_rows else 0
            return {
                "code": 0,
                "data": {
                    "type": "csv",
                    "columns": columns,
                    "total_rows": total_rows,
                    "missing_rates": missing_rates,
                },
            }
        except Exception as e:
            return {"code": 0, "data": {"type": "csv", "error": str(e)}}

    return {"code": 0, "data": {"type": "general", "file_count": row.file_count, "size_bytes": row.size_bytes}}