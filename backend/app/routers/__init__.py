"""业务模块路由汇总。

这里统一按别名导入再暴露 ROUTERS：模块名有可能和内置名撞车（某个业务模块就叫 dict、list
这种名字时），按名字直接 import 会把内置类型覆盖掉，函数注解在运行时求值就会报
'module' object is not subscriptable。
"""
from __future__ import annotations

from app.routers import sample as router_sample
from app.routers import contract as router_contract
from app.routers import task as router_task
from app.routers import method as router_method
from app.routers import instrument as router_instrument
from app.routers import standard as router_standard
from app.routers import result as router_result
from app.routers import judge_rule as router_judge_rule
from app.routers import report as router_report
from app.routers import boundary as router_boundary
from app.routers import abnormal as router_abnormal
from app.routers import envmonitor as router_envmonitor
from app.routers import blind as router_blind
from app.routers import ability as router_ability
from app.routers import intermediate as router_intermediate
from app.routers import audit as router_audit
from app.routers import certification as router_certification
from app.routers import quality as router_quality
from app.routers import reagent2 as router_reagent2
from app.routers import waste as router_waste
from app.routers import opinion as router_opinion

ROUTERS = [router_sample, router_contract, router_task, router_method, router_instrument, router_standard, router_result, router_judge_rule, router_report, router_boundary, router_abnormal, router_envmonitor, router_blind, router_ability, router_intermediate, router_audit, router_certification, router_quality, router_reagent2, router_waste, router_opinion]
