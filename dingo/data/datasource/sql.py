from typing import Any, Dict, Generator, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from dingo.config import InputArgs
from dingo.data.datasource.base import DataSource


@DataSource.register()
class SqlDataSource(DataSource):
    def __init__(
        self,
        input_args: InputArgs = None,
        config_name: Optional[str] = None,
    ):
        """Create a `SqlDataSource` instance.
        Args:
            input_args: A `InputArgs` instance to load the dataset from.
            config_name: Optional configuration name.
        """
        self.engine = self._get_engine(input_args.dataset.sql_config)
        self.sql_query = input_args.input_path
        self.config_name = config_name
        super().__init__(input_args=input_args)

    @staticmethod
    def _get_engine(sql_config) -> Engine:
        """创建SQLAlchemy引擎"""
        if not sql_config.dialect or not sql_config.database:
            raise RuntimeError(
                "SQL connection parameters (dialect, database) "
                "must be set when using SQL datasource."
            )

        # 构建数据库连接URL
        # SQLite 格式: sqlite:///path/to/database.db
        # 其他数据库格式: dialect+driver://username:password@host:port/database
        if sql_config.dialect.lower() == "sqlite":
            driver_part = f"+{sql_config.driver}" if sql_config.driver else ""
            connection_url = f"{sql_config.dialect}{driver_part}:///{sql_config.database}"
        else:
            # 对于非 SQLite 数据库，需要用户名、密码和主机
            if not sql_config.username or not sql_config.host:
                raise RuntimeError(
                    f"For {sql_config.dialect}, username and host must be set."
                )

            driver_part = f"+{sql_config.driver}" if sql_config.driver else ""
            port_part = f":{sql_config.port}" if sql_config.port else ""
            password_part = f":{sql_config.password}" if sql_config.password else ""

            connection_url = (
                f"{sql_config.dialect}{driver_part}://"
                f"{sql_config.username}{password_part}@"
                f"{sql_config.host}{port_part}/{sql_config.database}"
            )

        # 添加连接参数（如 ?charset=utf8mb4）
        if sql_config.connect_args:
            # 确保参数以 ? 开头
            args_part = sql_config.connect_args if sql_config.connect_args.startswith('?') else f"?{sql_config.connect_args}"
            connection_url = f"{connection_url}{args_part}"

        engine = create_engine(connection_url)
        return engine

    @staticmethod
    def get_source_type() -> str:
        return "sql"

    def load(self, **kwargs) -> Generator[Dict[str, Any], None, None]:
        """使用服务器游标方式流式加载SQL查询结果。

        Args:
            kwargs: Additional keyword arguments used for loading the dataset.

        Returns:
            A generator that yields rows as dictionaries.
        """
        return self._load()

    def _load(self) -> Generator[Dict[str, Any], None, None]:
        """使用stream_results方式流式读取数据库"""
        with self.engine.connect() as conn:
            # 使用stream_results=True启用服务器端游标
            result = conn.execution_options(stream_results=True).execute(
                text(self.sql_query)
            )

            # 直接迭代结果，SQLAlchemy自动处理分页
            for row in result:
                # 将Row对象转换为字典
                yield dict(row._mapping)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sql_query": self.sql_query,
            "config_name": self.config_name,
        }

    def __del__(self):
        """清理资源"""
        if hasattr(self, 'engine'):
            self.engine.dispose()
