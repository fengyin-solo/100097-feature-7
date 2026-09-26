"""判定规则业务规则：规则的新增、修订、停用与重判都收在这里。

规则按「检测项目+评价标准」区分判定口径；修订不改原记录，而是停用旧版本、
生成新版本，并立即把命中该口径的既有检测结果重判一遍，旧依据进判定历史。
"""
from __future__ import annotations

from typing import Any

from app.services.judgment import parse_number, rejudge_results
from app.store import store

MODULE = "judgerule"
RESULT_MODULE = "result"
REQUIRED_FIELDS = ["检测项目", "评价标准", "检出限", "限量值"]
NUMERIC_FIELDS = ["检出限", "限量值"]
STATUS_ACTIVE = "现行有效"
STATUS_RETIRED = "已停用"


class JudgeRuleService:
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
            rows = [
                row
                for row in rows
                if keyword in str(row.get("规则编号", ""))
                or keyword in str(row.get("检测项目", ""))
                or keyword in str(row.get("评价标准", ""))
            ]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        errors = self._validate(values, required=True)
        if errors:
            return None, errors
        rows = store.rows(MODULE)
        entry = {
            "id": max((int(row.get("id", 0)) for row in rows), default=0) + 1,
            "规则编号": self._next_code(rows),
            "检测项目": str(values["检测项目"]).strip(),
            "评价标准": str(values["评价标准"]).strip(),
            "检出限": parse_number(values["检出限"]),
            "限量值": parse_number(values["限量值"]),
            "单位": str(values.get("单位") or "").strip(),
            "版本号": 1,
            "规则状态": STATUS_ACTIVE,
            "status": STATUS_ACTIVE,
            "pending": True,
            "abnormal": False,
        }
        rows.append(entry)
        return entry, []

    def revise_entry(self, entry_id: int, changes: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str], int]:
        """修订规则：旧版本停用、新版本生效，并返回重判的既有结果条数。"""
        rule = store.find(MODULE, entry_id)
        if rule is None:
            return None, [f"判定规则 {entry_id} 不存在或已归档"], 0
        if rule.get("规则状态") != STATUS_ACTIVE:
            return None, ["只有现行有效的规则可以修订"], 0
        updates = {
            field: changes[field]
            for field in NUMERIC_FIELDS + ["单位"]
            if str(changes.get(field) or "").strip()
        }
        if not updates:
            return None, ["修订规则至少要调整检出限、限量值或单位中的一项"], 0
        errors = self._validate(updates, required=False)
        if errors:
            return None, errors, 0
        rows = store.rows(MODULE)
        new_rule = {
            "id": max((int(row.get("id", 0)) for row in rows), default=0) + 1,
            "规则编号": rule["规则编号"],
            "检测项目": rule["检测项目"],
            "评价标准": rule["评价标准"],
            "检出限": parse_number(updates.get("检出限", rule.get("检出限"))),
            "限量值": parse_number(updates.get("限量值", rule.get("限量值"))),
            "单位": str(updates.get("单位", rule.get("单位") or "")).strip(),
            "版本号": int(rule.get("版本号") or 1) + 1,
            "规则状态": STATUS_ACTIVE,
            "status": STATUS_ACTIVE,
            "pending": True,
            "abnormal": False,
        }
        rule["规则状态"] = STATUS_RETIRED
        rule["status"] = STATUS_RETIRED
        rule["pending"] = False
        rows.append(new_rule)
        rejudged = rejudge_results(store.rows(RESULT_MODULE), new_rule, reason=f"规则修订为v{new_rule['版本号']}")
        return new_rule, [], rejudged

    def run_action(self, entry_id: int, action: str, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        if action == "修订规则":
            entry, errors, rejudged = self.revise_entry(entry_id, values)
            if entry is None:
                return None, "；".join(errors)
            return entry, f"规则已修订为v{entry['版本号']}，{rejudged}条既有检测结果已按新口径重判"
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"判定规则 {entry_id} 不存在或已归档"
        if action == "重判结果":
            if entry.get("规则状态") != STATUS_ACTIVE:
                return None, "已停用的规则不能用于重判，请先确认现行版本"
            count = rejudge_results(store.rows(RESULT_MODULE), entry, reason="人工触发重判")
            return entry, f"已按规则{entry['规则编号']}v{entry['版本号']}重判{count}条检测结果"
        if action == "停用规则":
            entry["规则状态"] = STATUS_RETIRED
            entry["status"] = STATUS_RETIRED
            entry["pending"] = False
            return entry, "判定规则已停用，既有结果的判定依据快照不受影响"
        return None, f"动作「{action}」不属于判定规则可执行范围"

    def _validate(self, values: dict[str, Any], *, required: bool) -> list[str]:
        errors: list[str] = []
        if required:
            missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
            if missing:
                errors.append(f"缺少必填字段：{'、'.join(missing)}")
        for field in NUMERIC_FIELDS:
            raw = values.get(field)
            if str(raw or "").strip() and parse_number(raw) is None:
                errors.append(f"{field}「{raw}」不是有效数值")
        return errors

    def _next_code(self, rows: list[dict[str, Any]]) -> str:
        serial = 0
        for row in rows:
            code = str(row.get("规则编号", ""))
            if code.startswith("RULE-"):
                serial = max(serial, int(code.split("-", 1)[1]))
        return f"RULE-{serial + 1:04d}"
