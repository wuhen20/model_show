"""清洗算子注册表。按 node_type 查找对应算子类。"""
from typing import Type

from .base import BaseOperator, CleanContext
from .source import SourceOperator
from .dedup import DedupOperator
from .nullfill import NullfillOperator
from .nullfill_short import NullfillShortOperator
from .nullfill_medium import NullfillMediumOperator
from .nullfill_long import NullfillLongOperator
from .outlier import OutlierOperator
from .dateformat import DateFormatOperator
from .str_replace import StrReplaceOperator

# 算子注册表：node_type → 算子类
OPERATOR_REGISTRY: dict[str, Type[BaseOperator]] = {
    "source": SourceOperator,
    "dedup": DedupOperator,
    "nullfill": NullfillOperator,
    "nullfill_short": NullfillShortOperator,
    "nullfill_medium": NullfillMediumOperator,
    "nullfill_long": NullfillLongOperator,
    "outlier": OutlierOperator,
    "dateformat": DateFormatOperator,
    "str2num": StrReplaceOperator,
}

__all__ = [
    "OPERATOR_REGISTRY",
    "BaseOperator",
    "CleanContext",
]
