"""判定规则业务规则：同一检测项目可按不同评价标准各配一条规则。

规则按「检测项目 + 评价标准」唯一定位口径；限值改动只升版本、不覆盖旧版本，
保存后立刻把命中该口径的既有检测结果重新判一遍（结果服务里做，避免循环导入）。
"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "judge_rule"
REQUIRED_FIELDS = ["规则编号", "检测项目", "评价标准"]


class JudgeRuleService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        item: str | None = None,
        standard: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [
                row for row in rows
                if keyword in str(row.get("规则编号", ""))
                or keyword in str(row.get("检测项目", ""))
                or keyword in str(row.get("评价标准", ""))
            ]
        if item:
            rows = [row for row in rows if item == str(row.get("检测项目") or "").strip()]
        if standard:
            rows = [row for row in rows if standard == str(row.get("评价标准") or "").strip()]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def find_rule(self, item: str, standard: str, *, include_disabled: bool = False) -> dict[str, Any] | None:
        """按检测项目+评价标准定位当前生效口径；同一口径只保留一条启用规则。"""
        for row in store.rows(MODULE):
            if not include_disabled and row.get("状态") == "停用":
                continue
            if str(row.get("检测项目") or "").strip() == item and str(
                row.get("评价标准") or ""
            ).strip() == standard:
                return row
        return None

    def _duplicate(self, item: str, standard: str, exclude_id: int | None = None) -> dict[str, Any] | None:
        for row in store.rows(MODULE):
            if exclude_id is not None and int(row.get("id", 0)) == exclude_id:
                continue
            if str(row.get("检测项目") or "").strip() == item and str(
                row.get("评价标准") or ""
            ).strip() == standard:
                return row
        return None

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        from app.services.judgment import validate_rule

        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, [f"缺少必填字段：{name}" for name in missing]
        errors = validate_rule(values)
        if errors:
            return None, errors
        item = str(values.get("检测项目") or "").strip()
        standard = str(values.get("评价标准") or "").strip()
        if self._duplicate(item, standard):
            return None, [f"检测项目「{item}」在评价标准「{standard}」下已存在规则，请直接编辑原规则"]
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update(self._pick(values))
        entry["版本号"] = 1
        entry["状态"] = "启用"
        rows.append(entry)
        return entry, []

    def update_entry(self, entry_id: int, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        from app.services.judgment import validate_rule

        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, [f"判定规则 {entry_id} 不存在"]
        merged = {**entry, **self._pick(values)}
        errors = validate_rule(merged)
        if errors:
            return None, errors
        item = str(merged.get("检测项目") or "").strip()
        standard = str(merged.get("评价标准") or "").strip()
        dup = self._duplicate(item, standard, exclude_id=entry_id)
        if dup:
            return None, [f"检测项目「{item}」+评价标准「{standard}」已被规则 {dup.get('规则编号')} 占用"]
        # 限值口径变了才升版本，仅改备注/单位不升版
        limit_changed = any(
            str(merged.get(key) if merged.get(key) is not None else "")
            != str(entry.get(key) if entry.get(key) is not None else "")
            for key in ("上限值", "下限值")
        )
        old_version = int(entry.get("版本号", 1))
        entry.update(self._pick(merged))
        if limit_changed:
            entry["版本号"] = old_version + 1
        return entry, []

    def set_status(self, entry_id: int, enabled: bool) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"判定规则 {entry_id} 不存在"
        entry["状态"] = "启用" if enabled else "停用"
        return entry, f"规则已{entry['状态']}"

    @staticmethod
    def _pick(values: dict[str, Any]) -> dict[str, Any]:
        return {
            key: values.get(key)
            for key in ("规则编号", "检测项目", "评价标准", "标准编号", "上限值", "下限值", "单位", "备注")
            if key in values
        }
