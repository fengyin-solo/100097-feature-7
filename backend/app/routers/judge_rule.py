"""判定规则接口：按「检测项目 + 评价标准」维护限值口径。

规则保存后自动重判命中该口径的既有检测结果，不需要人工逐条翻旧数据。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.judge_rule import JudgeRuleService
from app.services.result import ResultService

router = APIRouter(prefix="/api/judge-rule", tags=["判定规则"])

service = JudgeRuleService()
result_service = ResultService()

LIST_FIELDS = ["规则编号", "检测项目", "评价标准", "标准编号", "上限值", "下限值", "单位", "版本号", "状态"]


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按规则编号/检测项目/评价标准检索"),
    item: str | None = Query(default=None, description="按检测项目精确过滤"),
    standard: str | None = Query(default=None, description="按评价标准精确过滤"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """列出判定规则；支持按检测项目或评价标准区分同一项目的不同口径。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(keyword=keyword, item=item, standard=standard, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"判定规则 {entry_id} 不存在")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """新增一条判定规则，保存后立即重判同口径的既有结果。"""
    entry, errors = service.create_entry(payload.values)
    if errors:
        return ActionResult(ok=False, message="；".join(errors))
    stats = result_service.rejudge_all(rule=entry)
    message = (
        f"规则 {entry.get('规则编号')} 已启用（v{entry.get('版本号')}），"
        f"同口径 {stats['scanned']} 条结果已重判，结论变化 {stats['changed']} 条"
    )
    return ActionResult(ok=True, message=message, entry=entry)


@router.put("/{entry_id}", response_model=ActionResult)
def update_entry(entry_id: int, payload: EntryPayload) -> ActionResult:
    """修改规则限值：限值变化自动升版本，并把同口径既有结果全部重判一遍。"""
    before = service.get_entry(entry_id)
    if before is None:
        return ActionResult(ok=False, message=f"判定规则 {entry_id} 不存在")
    old_version = before.get("版本号")
    entry, errors = service.update_entry(entry_id, payload.values)
    if errors:
        return ActionResult(ok=False, message="；".join(errors))
    stats = result_service.rejudge_all(rule=entry)
    upgraded = entry.get("版本号") != old_version
    message = (
        f"规则已保存{'并升级到 v' + str(entry.get('版本号')) if upgraded else ''}，"
        f"同口径 {stats['scanned']} 条结果已重判：结论变化 {stats['changed']} 条，"
        f"{stats['reset_to_review']} 条已复核结果退回待复核"
    )
    return ActionResult(ok=True, message=message, entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """停用/启用规则；停用后同口径结果重判会落到“缺少匹配规则”，请谨慎操作。"""
    action = str(payload.values.get("action") or "").strip()
    if action not in ("停用", "启用"):
        return ActionResult(ok=False, message=f"动作「{action}」不属于判定规则可执行范围")
    entry, message = service.set_status(entry_id, enabled=action == "启用")
    if entry is None:
        return ActionResult(ok=False, message=message)
    stats = result_service.rejudge_all(rule=entry)
    if action == "停用":
        message += f"；同口径 {stats['scanned']} 条结果已重判，{stats['unjudged']} 条变为未判定"
    else:
        message += f"；同口径 {stats['scanned']} 条结果已重判，{stats['changed']} 条结论发生变化"
    return ActionResult(ok=True, message=message, entry=entry)
