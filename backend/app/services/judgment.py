"""判定引擎：把「检测值 ↔ 检出限 / 评价标准」的比对口径固化成纯函数。

所有页面与服务都只能通过这里给出判定结论，检测员不再手填结论。
判定时返回的整份依据（规则编号/版本、参与比对的数值、结论、偏离范围）
会原样快照进检测结果，复核人看到的就是录入时冻结的那一份。
"""
from __future__ import annotations

import re
from typing import Any

# 未检出的规范写法及其等价输入
NOT_DETECTED_TOKEN = "未检出"
_NOT_DETECTED_ALIASES = {"", "nd", "n.d", "n.d.", "none", "null", "-", "--", "/"}

# 形如 "<0.05"、"＜0.05 mg/L"：低于检出限
_BELOW_RE = re.compile(r"^[<＜≤]\s*([0-9]+(?:\.[0-9]+)?)\s*([^\s,，;；()（）]*)")
# 从 "0.05 mg/L" 这类文本里取首个数字与首个单位片段（含科学计数法 2.3e-2）
_NUMBER_RE = re.compile(r"[-+]?[0-9]+(?:\.[0-9]+)?(?:[eE][-+]?[0-9]+)?")
# 整条检测值允许的形态：[<|＜|≤] 数字 [单位]，例如 0.05、0.05mg/L、<0.004 mg/L
_FULL_VALUE_RE = re.compile(
    r"^(?:[<＜≤]\s*)?[-+]?[0-9]+(?:\.[0-9]+)?(?:[eE][-+]?[0-9]+)?"
    r"(?:\s*[^\s0-9,，;；()（）<>＜＞=]*)?$"
)

CONCLUSION_QUALIFIED = "合格"
CONCLUSION_UNQUALIFIED = "不合格"
CONCLUSION_NOT_DETECTED = "合格（未检出）"


def format_number(value: float) -> str:
    """去掉浮点尾巴：0.0500000001 -> 0.05，超出精度时按 6 位有效小数截断。"""
    text = f"{value:.10f}".rstrip("0").rstrip(".")
    return text or "0"


def _split_value(raw: Any) -> tuple[float | None, str | None, str | None]:
    """把检测值拆成（数值, 单位, 归一原文）。拆不出数值时数值返回 None。"""
    if raw is None:
        return None, None, None
    text = str(raw).strip()
    if not text:
        return None, None, ""
    below = _BELOW_RE.match(text)
    if below:
        number = float(below.group(1))
        unit = below.group(2) or None
        return number, unit, f"<{format_number(number)}" + (f" {unit}" if unit else "")
    match = _NUMBER_RE.search(text)
    if match:
        number = float(match.group(0))
        rest = text[match.end():].strip(" \t")
        unit = rest or None
        return number, unit, format_number(number) + (f" {unit}" if unit else "")
    return None, None, text


def _parse_lod(raw: Any) -> tuple[float | None, str | None]:
    if raw is None or not str(raw).strip():
        return None, None
    text = str(raw).strip()
    below = _BELOW_RE.match(text)
    if below:
        return float(below.group(1)), below.group(2) or None
    match = _NUMBER_RE.search(text)
    if match:
        return float(match.group(0)), text[match.end():].strip() or None
    return None, None


def _limit_of(rule: dict[str, Any], key: str) -> float | None:
    raw = rule.get(key)
    if raw is None or not str(raw).strip():
        return None
    try:
        return float(str(raw).strip())
    except ValueError:
        return None


def judge(entry: dict[str, Any], rule: dict[str, Any] | None) -> dict[str, Any]:
    """按固化口径对一条检测结果做判定，返回可直接落库的判定快照。

    返回字段固定：结论 / 判定说明 / 失败原因 / 判定依据 / 规则版本 / 参与比对值。
    检测值缺失或格式不对时不产生合格/不合格结论，只给失败原因。
    """
    item = str(entry.get("检测项目") or "").strip()
    standard_name = str(entry.get("评价标准") or "").strip()
    raw_value = entry.get("检测值")
    raw_lod = entry.get("检出限")

    snapshot: dict[str, Any] = {
        "检测项目": item,
        "评价标准": standard_name,
        "检测值原文": None if raw_value is None else str(raw_value),
        "检出限原文": None if raw_lod is None else str(raw_lod),
        "结论": None,
        "判定说明": None,
        "失败原因": None,
        "偏离范围": None,
        "判定依据": None,
        "规则编号": None,
        "规则版本": None,
        "限值": None,
        "参与比对数值": None,
        "比对检出限": None,
    }

    value_text = "" if raw_value is None else str(raw_value).strip()
    if not value_text:
        snapshot["失败原因"] = "检测值缺失，无法生成判定结论，请补录检测值后重新判定"
        snapshot["判定说明"] = "未判定：检测值为空"
        return snapshot

    is_nd = value_text == NOT_DETECTED_TOKEN or value_text.lower() in _NOT_DETECTED_ALIASES
    below_match = _BELOW_RE.match(value_text)

    value, value_unit, normalized = _split_value(value_text)
    if not is_nd and not _FULL_VALUE_RE.match(value_text):
        snapshot["失败原因"] = (
            f"检测值「{value_text}」格式不正确，应为数值（可带单位）、“未检出/ND”或"
            "“＜检出限”写法，未生成判定结论"
        )
        snapshot["判定说明"] = "未判定：检测值格式错误"
        return snapshot
    if not is_nd and value is None:
        snapshot["失败原因"] = f"检测值「{value_text}」格式不正确，未能解析出数值，未生成判定结论"
        snapshot["判定说明"] = "未判定：检测值格式错误"
        return snapshot

    lod, lod_unit = _parse_lod(raw_lod)
    if lod is None:
        snapshot["失败原因"] = "检出限缺失或格式不正确，无法判定是否低于检出限，未生成判定结论"
        snapshot["判定说明"] = "未判定：缺少可用检出限"
        return snapshot

    if rule is None:
        snapshot["失败原因"] = (
            f"检测项目「{item}」在评价标准「{standard_name or '未填写'}」下没有配置判定规则，"
            "请先在判定规则中登记限值"
        )
        snapshot["判定说明"] = "未判定：缺少匹配的判定规则"
        return snapshot

    snapshot["规则编号"] = rule.get("规则编号")
    snapshot["规则版本"] = rule.get("版本号")
    rule_unit = str(rule.get("单位") or "").strip() or None
    upper = _limit_of(rule, "上限值")
    lower = _limit_of(rule, "下限值")
    limit_text_parts = []
    if lower is not None:
        limit_text_parts.append(f"下限 {format_number(lower)}")
    if upper is not None:
        limit_text_parts.append(f"上限 {format_number(upper)}")
    snapshot["限值"] = "；".join(limit_text_parts) or None
    if rule_unit:
        snapshot["限值"] = (snapshot["限值"] + f" {rule_unit}") if snapshot["限值"] else rule_unit

    warnings: list[str] = []
    units = {u for u in (value_unit, lod_unit, rule_unit) if u}
    if len(units) > 1:
        warnings.append(
            f"单位不一致（检测值单位 {value_unit or '无'} / 检出限单位 {lod_unit or '无'} / "
            f"评价标准单位 {rule_unit or '无'}），按数值直接比对，请核实"
        )

    compared_lod = " ".join(part for part in (format_number(lod), lod_unit) if part)
    snapshot["比对检出限"] = compared_lod

    # 检测值低于检出限：统一按未检出处理（“未检出/ND/<LOD”写法同样走这里）
    if is_nd or (below_match is not None) or value < lod:
        if is_nd and below_match is None:
            normalized = NOT_DETECTED_TOKEN
        snapshot["结论"] = CONCLUSION_NOT_DETECTED
        snapshot["参与比对数值"] = NOT_DETECTED_TOKEN
        detail = f"检测值 {normalized or NOT_DETECTED_TOKEN} 低于检出限 {compared_lod}，按未检出处理"
        if lod > (upper if upper is not None else lod):
            warnings.append("检出限高于评价标准上限，建议核实方法检出限或限值配置")
        snapshot["判定依据"] = "；".join(
            [f"规则 {rule.get('规则编号')}（{rule.get('评价标准')} v{rule.get('版本号')}）", detail]
        )
        snapshot["判定说明"] = "；".join([detail, *warnings]) if warnings else detail
        return snapshot

    snapshot["参与比对数值"] = format_number(value) + (f" {value_unit}" if value_unit else "")

    # 检出值与评价标准限值比对，给出具体偏离范围
    deviations: list[str] = []
    unqualified = False
    if upper is not None and value > upper:
        unqualified = True
        over = value - upper
        percent = over / upper * 100 if upper else 0
        deviations.append(
            f"超上限 {format_number(over)}{rule_unit or value_unit or ''}"
            f"（实测 {snapshot['参与比对数值']}，限值 {format_number(upper)}"
            f"{rule_unit or ''}，偏高 {format_number(round(percent, 2))}%）"
        )
    if lower is not None and value < lower:
        unqualified = True
        under = lower - value
        percent = under / lower * 100 if lower else 0
        deviations.append(
            f"低于下限 {format_number(under)}{rule_unit or value_unit or ''}"
            f"（实测 {snapshot['参与比对数值']}，限值 {format_number(lower)}"
            f"{rule_unit or ''}，偏低 {format_number(round(percent, 2))}%）"
        )

    basis = (
        f"规则 {rule.get('规则编号')}（{rule.get('评价标准')} v{rule.get('版本号')}，"
        f"{snapshot['限值']}）；检测值不低于检出限 {compared_lod}，按实测值 {snapshot['参与比对数值']} 与限值比对"
    )
    snapshot["判定依据"] = basis
    if unqualified:
        snapshot["结论"] = CONCLUSION_UNQUALIFIED
        snapshot["偏离范围"] = "；".join(deviations)
        snapshot["判定说明"] = "；".join([*deviations, *warnings]) if warnings else "；".join(deviations)
    else:
        snapshot["结论"] = CONCLUSION_QUALIFIED
        within = []
        if lower is not None:
            within.append(f"不低于下限 {format_number(lower)}")
        if upper is not None:
            within.append(f"不高于上限 {format_number(upper)}")
        detail = "实测值" + ("、".join(within) if within else "满足规则要求")
        snapshot["判定说明"] = "；".join([detail, *warnings]) if warnings else detail
    return snapshot


def validate_rule(rule: dict[str, Any]) -> list[str]:
    """规则保存前自检：同一检测项目+评价标准靠它保证限值可用。"""
    errors: list[str] = []
    if not str(rule.get("检测项目") or "").strip():
        errors.append("检测项目不能为空")
    if not str(rule.get("评价标准") or "").strip():
        errors.append("评价标准不能为空")
    upper = rule.get("上限值")
    lower = rule.get("下限值")
    upper_num = lower_num = None
    try:
        if upper not in (None, ""):
            upper_num = float(str(upper).strip())
    except ValueError:
        errors.append("上限值必须是数值")
    try:
        if lower not in (None, ""):
            lower_num = float(str(lower).strip())
    except ValueError:
        errors.append("下限值必须是数值")
    if upper_num is None and lower_num is None:
        errors.append("上限值、下限值至少填写一项")
    if upper_num is not None and lower_num is not None and upper_num < lower_num:
        errors.append("上限值不能小于下限值")
    return errors
