"""检测结果业务规则：状态流转、字段校验与筛选口径都收在这里。

判定结论不再手填：登记或录入检测值时由判定引擎自动给出，
结论、说明与判定依据快照一并落到结果上，复核人看到的就是录入时那份依据。
"""
from __future__ import annotations

from typing import Any

from app.services.judgment import apply_judgment, has_measure, match_rule
from app.store import store

MODULE = "result"
RULE_MODULE = "judgerule"
REQUIRED_FIELDS = ["结果编号", "关联任务", "检测项目"]
ENTRY_FIELDS = ["检测值", "评价标准"]
STATUS_ORDER = ["待录入", "待复核", "已复核", "已退回"]
ACTION_RULES = {"录入结果": "待复核", "提交复核": "已复核", "退回修正": "待录入"}
NEGATIVE_ACTIONS = []


class ResultService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("结果编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["检测值"] = values.get("检测值")
        entry["评价标准"] = str(values.get("评价标准") or "").strip()
        entry["判定结论"] = ""
        entry["判定说明"] = ""
        entry["判定快照"] = None
        entry["判定历史"] = []
        entry["status"] = STATUS_ORDER[0]
        entry["结果状态"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        if has_measure(entry["检测值"]):
            self._judge(entry, reason="录入判定")
        else:
            entry["判定说明"] = "检测值未录入，录入后自动判定"
        rows.append(entry)
        return entry, []

    def run_action(self, entry_id: int, action: str, values: dict[str, Any] | None = None) -> tuple[dict[str, Any] | None, str]:
        values = values or {}
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"检测结果 {entry_id} 不存在或已归档"
        if action == "重新判定":
            self._judge(entry, reason="人工重新判定")
            conclusion = entry.get("判定结论") or "未生成结论"
            return entry, f"检测结果已重新判定：{conclusion}（{entry.get('判定说明', '')}）"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于检测结果可执行范围"
        if action == "录入结果":
            for field in ENTRY_FIELDS:
                if has_measure(values.get(field)):
                    entry[field] = values.get(field)
            if not has_measure(entry.get("检测值")):
                entry["判定结论"] = ""
                entry["判定说明"] = "检测值缺失，未生成判定结论"
                return None, "录入结果需要先填写检测值"
            self._judge(entry, reason="录入判定")
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry["结果状态"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS or entry.get("判定结论") == "不合格"
        return entry, f"检测结果已{action}"

    def _judge(self, entry: dict[str, Any], *, reason: str) -> None:
        rule = match_rule(store.rows(RULE_MODULE), entry.get("检测项目"), entry.get("评价标准"))
        apply_judgment(entry, rule, reason=reason)
