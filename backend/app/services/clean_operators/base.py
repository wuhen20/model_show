"""清洗算子基类与上下文定义"""
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class CleanContext:
    """清洗管道执行上下文，在算子之间传递状态。"""
    task: dict
    task_no: str
    log_id: Optional[int]
    nodes: list  # 已按画布连线顺序排好的节点列表
    df: Any = None  # pandas.DataFrame，由 source 算子初始化
    columns: list = field(default_factory=list)  # 列名列表，由 source 算子填充
    col_lower_map: dict = field(default_factory=dict)  # 小写列名 → 原始列名
    total_count: int = 0
    removed_count: int = 0
    append_log: Optional[Callable[[int, str], None]] = None

    _logger: logging.Logger = field(
        default_factory=lambda: logging.getLogger("app.clean"),
        repr=False,
    )

    def log(self, message: str) -> None:
        """追加清洗日志，同时写入数据库日志和系统日志"""
        self._logger.info(f"[{self.task_no}] {message}")
        if self.log_id is not None and self.append_log is not None:
            self.append_log(self.log_id, message)


class BaseOperator(ABC):
    """算子基类。子类需设置 node_type 并实现 execute。"""
    node_type: str = ""

    @abstractmethod
    def execute(self, ctx: CleanContext, node: dict, config: dict) -> None:
        """执行算子逻辑，直接修改 ctx.df / ctx.total_count / ctx.removed_count，
        通过 ctx.log() 写日志。"""
        raise NotImplementedError
