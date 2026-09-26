"""判定引擎：检测值与检出限、评价标准的比对口径全部固化在这一处。

检测员只录入检测值，结论由这里统一给出，避免同一份检测值不同人判出不同结论：
- 检测值缺失或不是有效数值时不生成结论，并在说明里写清原因；
- 检测值低于检出限（或录成「<检出限」「未检出」「ND」）统一按未检出处理；
- 超出评价标准限量时判不合格，并给出具体偏离范围（超出量与偏离百分比）。
判定的同时把所用规则版本、限值与检测值快照写到结果上，
复核人看到的就是录入时那份依据，不随后续规则改动而悄悄变化。
"""
from __future__ import annotations

import math
from datetime import datetime
from typing import Any

CONCLUSION_PASS = "合格"
CONCLUSION_FAIL = "不合格"
CONCLUSION_ND = "未检出"

# 录入时常见的未检出写法，统一归一到「未检出」结论
NOT_DETECTED_WORDS = {"未检出", "未检测出", "nd", "n.d.", "not detected"}


def parse_number(raw: Any) -> float | None:
    """把录入内容解析成有限数值；空值、非数值、无穷大都返回 None。"""
    if raw is None or isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        value = float(raw)
    else:
        text = str(raw).strip()
        if not text:
            return None
        try:
            value = float(text)
        except ValueError:
            return None
    return value if math.isfinite(value) else None


def has_measure(raw: Any) -> bool:
    """检测值是否已录入；数值 0 也是有效录入，只有空内容算缺失。"""
    return raw is not None and str(raw).strip() != ""


def parse_measure(raw: Any) -> tuple[float | None, bool, str | None]:
    """解析检测值，返回 (数值, 是否未检出标记, 无法解析的原因)。

    「<0.05」「未检出」「ND」视为未检出标记；其余非数值内容视为格式不对。
    """
    if not has_measure(raw):
        return None, False, "检测值缺失，未生成判定结论"
    text = str(raw).strip()
    if text.lower() in NOT_DETECTED_WORDS:
        return None, True, None
    if text.startswith(("<", "＜")):
        number = parse_number(text[1:])
        if number is None:
            return None, False, f"检测值「{text}」不是有效数值，未生成判定结论"
        return number, True, None
    number = parse_number(raw)
    if number is None:
        return None, False, f"检测值「{text}」不是有效数值，未生成判定结论"
    return number, False, None


def _fmt(value: float | None) -> str:
    """数值展示去掉多余的零，0.50 显示为 0.5。"""
    if value is None:
        return "—"
    return f"{value:g}"


def judge_value(rule: dict[str, Any], raw_value: Any) -> dict[str, Any]:
    """按规则对检测值给出结论；每个分支要么给结论，要么给无法判定的原因。"""
    number, below_mark, error = parse_measure(raw_value)
    if error:
        return {"结论": None, "说明": error}
    unit = str(rule.get("单位") or "")
    det_limit = parse_number(rule.get("检出限"))
    limit = parse_number(rule.get("限量值"))
    if below_mark:
        return {"结论": CONCLUSION_ND, "说明": f"检测值低于检出限{_fmt(det_limit)}{unit}，按未检出处理"}
    assert number is not None  # error 与 below_mark 都排除后，数值必然存在
    if det_limit is not None and number < det_limit:
        return {
            "结论": CONCLUSION_ND,
            "说明": f"检测值{_fmt(number)}{unit}低于检出限{_fmt(det_limit)}{unit}，按未检出处理",
        }
    if limit is None:
        return {"结论": None, "说明": "判定规则缺少有效限量值，未生成判定结论"}
    if number <= limit:
        return {"结论": CONCLUSION_PASS, "说明": f"检测值{_fmt(number)}{unit}未超出限量{_fmt(limit)}{unit}"}
    over = number - limit
    deviation = f"超出限量{_fmt(over)}{unit}"
    if limit > 0:
        deviation += f"（偏离{round(over / limit * 100, 2):g}%）"
    return {"结论": CONCLUSION_FAIL, "说明": f"检测值{_fmt(number)}{unit}{deviation}"}


def build_snapshot(rule: dict[str, Any], raw_value: Any, conclusion: str, note: str) -> dict[str, Any]:
    """生成判定依据快照：判定那一刻用到的规则版本、限值与检测值原样留存。"""
    return {
        "规则编号": rule.get("规则编号"),
        "规则版本": rule.get("版本号"),
        "检测项目": rule.get("检测项目"),
        "评价标准": rule.get("评价标准"),
        "检出限": rule.get("检出限"),
        "限量值": rule.get("限量值"),
        "单位": rule.get("单位"),
        "检测值": raw_value,
        "判定结论": conclusion,
        "判定说明": note,
        "判定人": "系统自动",
        "判定时间": datetime.now().isoformat(timespec="seconds"),
    }


def match_rule(rules: list[dict[str, Any]], item: Any, standard: Any) -> dict[str, Any] | None:
    """同一检测项目可能对应多份评价标准，必须项目与标准同时命中才适用；取现行有效中版本最新的。"""
    item_text = str(item or "").strip()
    standard_text = str(standard or "").strip()
    if not item_text or not standard_text:
        return None
    candidates = [
        rule
        for rule in rules
        if str(rule.get("检测项目") or "").strip() == item_text
        and str(rule.get("评价标准") or "").strip() == standard_text
        and rule.get("规则状态") == "现行有效"
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda rule: int(rule.get("版本号") or 0))


def apply_judgment(row: dict[str, Any], rule: dict[str, Any] | None, *, reason: str) -> dict[str, Any]:
    """把判定结论与依据快照写到结果行上；旧快照移入判定历史，重判过程可追溯。"""
    previous = row.get("判定快照")
    if previous:
        history = list(row.get("判定历史") or [])
        history.append({**previous, "作废原因": reason})
        row["判定历史"] = history
    if rule is None:
        row["判定结论"] = ""
        row["判定说明"] = "未找到同时匹配检测项目与评价标准的现行判定规则，未生成结论"
        row["判定快照"] = None
        return row
    outcome = judge_value(rule, row.get("检测值"))
    conclusion = outcome["结论"] or ""
    note = outcome["说明"]
    row["判定结论"] = conclusion
    row["判定说明"] = note
    row["判定快照"] = build_snapshot(rule, row.get("检测值"), conclusion, note)
    return row


def rejudge_results(result_rows: list[dict[str, Any]], rule: dict[str, Any], *, reason: str) -> int:
    """规则改动后，把命中该规则口径（检测项目+评价标准）的既有结果全部重判一遍。"""
    item_text = str(rule.get("检测项目") or "").strip()
    standard_text = str(rule.get("评价标准") or "").strip()
    count = 0
    for row in result_rows:
        if str(row.get("检测项目") or "").strip() != item_text:
            continue
        if str(row.get("评价标准") or "").strip() != standard_text:
            continue
        apply_judgment(row, rule, reason=reason)
        count += 1
    return count
