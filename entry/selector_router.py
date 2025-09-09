from typing import Literal

Signal = Literal["NEED_USER", "FINISHED", "ERROR", "NEXT_STEP", "CONTINUE"]


def selector(last_speaker: str | None, last_signal: Signal | None, plan, state) -> str:
    # 非严格示例：根据 plan.route_hint / state.phase / last_signal 决定下一位
    if last_signal == "NEED_USER":
        return "UserProxy"
    if last_signal in ("ERROR",):
        return "Planner"
    if plan and plan.route_hint == "magone":
        return "MagOne"
    if plan and plan.route_hint == "swarm":
        return "BizSwarm"
    # 默认交给 Planner 决定
    return "Planner"
