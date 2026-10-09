"""Evaluate one sample using the guobiao data-time-range rule."""

from dingo.config.input_args import EvaluatorRuleArgs
from dingo.io import Data
from dingo.model.rule.guobiao.rule_tc609_quality import Rule_TC609_0303_DataTimeRange


def main():
    data = Data(
        data_id="guobiao-time-range-example",
        dt="2025-03-01 10:30:00",
        content="示例数据",
    )

    Rule_TC609_0303_DataTimeRange.dynamic_config = EvaluatorRuleArgs(
        dt_start="2025-01-01",
        dt_end="2025-12-31 23:59:59",
    )
    result = Rule_TC609_0303_DataTimeRange.eval(data)
    print(result)


if __name__ == "__main__":
    main()
