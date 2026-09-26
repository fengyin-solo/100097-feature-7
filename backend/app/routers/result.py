"""检测结果接口：维护检测结果，覆盖录入结果、提交复核、退回修正等动作。

判定结论由后端按固化规则自动生成，接口不接收手填结论。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.result import ResultService

router = APIRouter(prefix="/api/result", tags=["检测结果"])

service = ResultService()

LIST_FIELDS = ["结果编号", "关联任务", "检测项目", "检测值", "检出限", "评价标准", "判定结论", "结果状态"]
STATUSES = ["待录入", "待复核", "已复核", "已退回"]
CONCLUSIONS = ["合格", "不合格", "合格（未检出）", "未判定"]


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按结果编号检索"),
    status: str | None = Query(default=None, description="待录入、待复核、已复核、已退回"),
    conclusion: str | None = Query(default=None, description="合格、不合格、合格（未检出）、未判定"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按结果编号、状态与判定结论过滤检测结果列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(keyword=keyword, status=status, conclusion=conclusion, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出检测结果清单：返回当前全量数据，含每条结果冻结的判定依据。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "result", "total": total, "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条检测结果明细（含判定快照）；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"检测结果 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条检测结果，缺字段时说明原因而不是静默丢弃；登记后立即自动判定。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    snapshot = entry.get("judge_snapshot") or {}
    message = "检测结果已登记"
    if not snapshot.get("结论"):
        message += f"，但未生成判定结论：{snapshot.get('失败原因')}"
    return ActionResult(ok=True, message=message, entry=entry)


@router.put("/{entry_id}", response_model=ActionResult)
def update_entry(entry_id: int, payload: EntryPayload) -> ActionResult:
    """录入/修正检测值等数据：保存后立即按当前规则重新判定并冻结依据。"""
    entry, message = service.update_entry(entry_id, payload.values)
    if entry is None:
        return ActionResult(ok=False, message=message)
    snapshot = entry.get("judge_snapshot") or {}
    if not snapshot.get("结论"):
        message += f"；未生成判定结论：{snapshot.get('失败原因')}"
    return ActionResult(ok=True, message=message, entry=entry)


@router.post("/{entry_id}/rejudge", response_model=ActionResult)
def rejudge_entry(entry_id: int) -> ActionResult:
    """按当前规则对单条结果重新判定（检测员改完数据后的手动入口）。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        return ActionResult(ok=False, message=f"检测结果 {entry_id} 不存在或已归档")
    snapshot = service.rejudge_one(entry)
    if snapshot.get("结论"):
        return ActionResult(ok=True, message=f"重新判定完成：{snapshot['结论']}", entry=entry)
    return ActionResult(ok=False, message=f"未生成判定结论：{snapshot.get('失败原因')}", entry=entry)


@router.post("/rejudge/all", response_model=ActionResult)
def rejudge_all() -> ActionResult:
    """规则批量调整后对全部既有结果重判一遍，结论变化的已复核结果退回待复核。"""
    stats = service.rejudge_all()
    message = (
        f"重判完成：共扫描 {stats['scanned']} 条，结论变化 {stats['changed']} 条，"
        f"未判定 {stats['unjudged']} 条，{stats['reset_to_review']} 条已复核结果退回待复核"
    )
    return ActionResult(ok=True, message=message)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条检测结果执行录入结果、提交复核、退回修正；不允许的动作会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
