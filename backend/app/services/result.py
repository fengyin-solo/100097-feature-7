"""检测结果业务规则：状态流转、字段校验、自动判定与筛选口径都收在这里。

判定结论不允许手填：每次录入/修改检测值或对应规则变更，都调用判定引擎生成
判定快照（结论+依据+规则版本）冻结在结果上；复核人读到的依据与录入时一致。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.services.judgment import (
    CONCLUSION_QUALIFIED,
    CONCLUSION_UNQUALIFIED,
    judge,
)
from app.store import store

MODULE = "result"
REQUIRED_FIELDS = ["结果编号", "关联任务", "检测项目"]
JUDGE_FIELDS = ["检测项目", "评价标准", "检测值", "检出限"]
EDITABLE_FIELDS = ["关联任务", "检测项目", "评价标准", "检测值", "检出限"]
STATUS_ORDER = ["待录入", "待复核", "已复核", "已退回"]
ACTION_RULES = {"录入结果": "待复核", "提交复核": "已复核", "退回修正": "待录入"}
JUDGED_CONCLUSIONS = {CONCLUSION_QUALIFIED, CONCLUSION_UNQUALIFIED, "合格（未检出）"}


class ResultService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        conclusion: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("结果编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        if conclusion:
            if conclusion == "未判定":
                rows = [row for row in rows if not (row.get("judge_snapshot") or {}).get("结论")]
            else:
                rows = [row for row in rows if (row.get("judge_snapshot") or {}).get("结论") == conclusion]
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
        entry: dict[str, Any] = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry.update({field: values.get(field) for field in EDITABLE_FIELDS if field in values})
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        self.rejudge_one(entry)
        return entry, []

    def update_entry(self, entry_id: int, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        """录入/修正检测数据：只改检测口径相关字段，改完立即按当前规则重新判定。"""
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"检测结果 {entry_id} 不存在或已归档"
        for field in EDITABLE_FIELDS:
            if field in values:
                entry[field] = values.get(field)
        if not str(entry.get("结果编号") or "").strip():
            return None, "结果编号不能为空"
        self.rejudge_one(entry)
        # 已复核结果被改动，原结论依据已经失效，必须退回重新走复核
        if entry.get("status") == "已复核":
            entry["status"] = "待复核"
            entry["pending"] = True
        return entry, "检测数据已更新并按当前规则重新判定"

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"检测结果 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于检测结果可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        if action == "提交复核":
            snapshot = entry.get("judge_snapshot") or {}
            if snapshot.get("结论") not in JUDGED_CONCLUSIONS:
                reason = snapshot.get("失败原因") or "检测数据尚未形成合格/不合格判定"
                return None, f"无法提交复核：{reason}"
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = (entry.get("judge_snapshot") or {}).get("结论") == "不合格"
        return entry, f"检测结果已{action}"

    # ------------------------------------------------------------------
    # 判定与重判
    # ------------------------------------------------------------------
    def _rule_for(self, entry: dict[str, Any]) -> dict[str, Any] | None:
        from app.services.judge_rule import JudgeRuleService

        item = str(entry.get("检测项目") or "").strip()
        standard = str(entry.get("评价标准") or "").strip()
        return JudgeRuleService().find_rule(item, standard)

    def rejudge_one(self, entry: dict[str, Any]) -> dict[str, Any]:
        """对单条结果执行一次判定，把结论与整份依据冻结进 judge_snapshot。"""
        previous = entry.get("judge_snapshot") or {}
        snapshot = judge({field: entry.get(field) for field in JUDGE_FIELDS}, self._rule_for(entry))
        snapshot["判定时间"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry["judge_snapshot"] = snapshot
        # 列表展示字段直接取冻结快照，杜绝有人手工改「判定结论」列
        entry["判定结论"] = snapshot.get("结论") or "未判定"
        entry["判定说明"] = snapshot.get("判定说明")
        entry["abnormal"] = snapshot.get("结论") == "不合格"
        return snapshot

    def rejudge_all(self, *, rule: dict[str, Any] | None = None) -> dict[str, Any]:
        """规则改动后重判既有结果。

        rule 给定时只重判命中该「检测项目+评价标准」的结果；不给则全量重判。
        结论发生变化的已复核结果退回待复核，复核人必须按新依据重新确认；
        结论不变的保留复核状态（依据里的规则版本会随快照更新）。
        """
        stats = {"scanned": 0, "changed": 0, "unjudged": 0, "reset_to_review": 0}
        for entry in store.rows(MODULE):
            if rule is not None:
                if str(entry.get("检测项目") or "").strip() != str(rule.get("检测项目") or "").strip():
                    continue
                if str(entry.get("评价标准") or "").strip() != str(rule.get("评价标准") or "").strip():
                    continue
            stats["scanned"] += 1
            old_conclusion = (entry.get("judge_snapshot") or {}).get("结论")
            old_reviewed = entry.get("status") == "已复核"
            snapshot = self.rejudge_one(entry)
            if snapshot.get("结论") != old_conclusion:
                stats["changed"] += 1
            if not snapshot.get("结论"):
                stats["unjudged"] += 1
            if old_reviewed and snapshot.get("结论") != old_conclusion:
                entry["status"] = "待复核"
                entry["pending"] = True
                stats["reset_to_review"] += 1
        return stats
