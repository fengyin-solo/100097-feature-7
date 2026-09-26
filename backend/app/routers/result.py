"""检测结果接口：维护检测结果，覆盖录入结果、提交复核、退回修正、重新判定等动作。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.result import ResultService

router = APIRouter(prefix="/api/result", tags=["检测结果"])

service = ResultService()

LIST_FIELDS = ["结果编号", "关联任务", "检测项目", "检测值", "评价标准", "判定结论", "判定说明", "结果状态"]
STATUSES = ["待录入", "待复核", "已复核", "已退回"]


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按结果编号检索"),
    status: str | None = Query(default=None, description="待录入、待复核、已复核、已退回"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按结果编号与状态过滤检测结果列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(keyword=keyword, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出检测结果清单：返回当前过滤条件下的全量数据。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "result", "total": total, "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条检测结果明细（含判定依据快照与判定历史）；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"检测结果 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条检测结果，缺字段时说明原因而不是静默丢弃；带检测值时自动给出判定结论。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    conclusion = (entry or {}).get("判定结论")
    message = "检测结果已登记" if not conclusion else f"检测结果已登记，自动判定：{conclusion}"
    return ActionResult(ok=True, message=message, entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条检测结果执行录入结果、提交复核、退回修正、重新判定；不允许的动作会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action, payload.values)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
