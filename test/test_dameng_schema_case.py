from types import SimpleNamespace
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.m_schema.schema_engine import SchemaEngine
from core.m_schema.sql_database import SQLDatabase
from config import DatabaseConfig, LoggerConfig
from service.database_service import DatabaseService
from service.schema_builder import SchemaRAGBuilder
from utils import normalize_dameng_schema_name, quote_dameng_identifier


def test_normalize_dameng_schema_name_uppercases_unquoted_identifier():
    """达梦未加引号的 schema 标识符按数据库规则统一转为大写。"""
    assert normalize_dameng_schema_name("supply_chain_security") == "SUPPLY_CHAIN_SECURITY"


def test_normalize_dameng_schema_name_preserves_quoted_identifier():
    """显式双引号包裹时保留大小写，用于大小写敏感 schema。"""
    assert normalize_dameng_schema_name('"Mixed_Case"') == "Mixed_Case"


def test_quote_dameng_identifier_escapes_embedded_quotes():
    """拼接 ALTER SESSION 里的 schema 标识符时必须转义双引号。"""
    assert quote_dameng_identifier('A"B') == '"A""B"'


def test_schema_builder_sets_normalized_dameng_current_schema(monkeypatch):
    """构建 schema 时达梦会话应切到规范化后的 schema。"""
    executed = []

    class FakeCursor:
        def execute(self, sql):
            executed.append(sql)

        def close(self):
            pass

    class FakeConnection:
        def cursor(self):
            return FakeCursor()

    fake_engine = SimpleNamespace(dialect=SimpleNamespace(name="dm"))

    monkeypatch.setattr("service.schema_builder.create_engine", lambda *args, **kwargs: fake_engine)

    def fake_listens_for(engine, name):
        def decorator(callback):
            callback(FakeConnection(), None)
            return callback

        return decorator

    monkeypatch.setattr("service.schema_builder.event.listens_for", fake_listens_for)
    monkeypatch.setattr(SchemaRAGBuilder, "_initialize_components", lambda self: None)

    SchemaRAGBuilder(
        DatabaseConfig(
            type="dameng",
            host="localhost",
            port=5236,
            user="SYSDBA",
            password="SYSDBA",
            database="supply_chain_security",
        ),
        LoggerConfig(),
    )

    assert executed == ['ALTER SESSION SET CURRENT_SCHEMA = "SUPPLY_CHAIN_SECURITY"']


def test_database_service_sets_normalized_dameng_current_schema(monkeypatch):
    """SQL 执行链路也应使用同样的达梦 schema 规范化逻辑。"""
    executed = []

    class FakeCursor:
        def execute(self, sql):
            executed.append(sql)

        def close(self):
            pass

    class FakeConnection:
        def cursor(self):
            return FakeCursor()

    fake_engine = SimpleNamespace()

    # DAMENG_AVAILABLE 在模块导入时就求值了，必须在 import 前 patch
    # 所以这里直接 patch _build_connection_uri，绕过 dameng 分支里对 DAMENG_AVAILABLE 的检查
    def fake_build_connection_uri(self, db_type, host, port, user, password, dbname):
        if db_type == "dameng":
            return "dm+dmPython://SYSDBA:SYSDBA@localhost:5236"
        return f"{db_type}://{user}:{password}@{host}:{port}/{dbname}"

    monkeypatch.setattr("service.database_service.DatabaseService._build_connection_uri", fake_build_connection_uri)
    monkeypatch.setattr("service.database_service.create_engine", lambda *args, **kwargs: fake_engine)

    def fake_listens_for(engine, name):
        def decorator(callback):
            callback(FakeConnection(), None)
            return callback

        return decorator

    monkeypatch.setattr("service.database_service.event.listens_for", fake_listens_for)

    service = DatabaseService()
    service._get_or_create_engine(
        db_type="dameng",
        host="localhost",
        port=5236,
        user="SYSDBA",
        password="SYSDBA",
        dbname="supply_chain_security",
    )

    assert executed == ['ALTER SESSION SET CURRENT_SCHEMA = "SUPPLY_CHAIN_SECURITY"']


def test_dameng_schema_engine_skips_has_table_probe(monkeypatch):
    """达梦初始化时应直接信任 get_table_names 结果，避免 has_table 兼容性问题。"""

    def fake_sql_database_init(
        self,
        engine,
        schema=None,
        metadata=None,
        ignore_tables=None,
        include_tables=None,
        sample_rows_in_table_info=3,
        indexes_in_table_info=False,
        custom_table_info=None,
        view_support=False,
        max_string_length=300,
    ):
        self._engine = engine
        self._schema = schema
        self._inspector = SimpleNamespace(
            has_table=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("has_table should not be called")),
            get_pk_constraint=lambda *args, **kwargs: {"constrained_columns": []},
            get_table_comment=lambda *args, **kwargs: {"text": ""},
            get_foreign_keys=lambda *args, **kwargs: [],
            get_columns=lambda *args, **kwargs: [{"name": "id", "type": "VARCHAR", "nullable": True}],
        )
        self._usable_tables = ["ac"]
        self._metadata = SimpleNamespace()

    monkeypatch.setattr(SQLDatabase, "__init__", fake_sql_database_init)

    engine = SimpleNamespace(dialect=SimpleNamespace(name="dm"))

    schema_engine = SchemaEngine(engine=engine, db_name="SUPPLY_CHAIN_SECURITY")

    assert schema_engine.mschema is not None


def test_schema_builder_surfaces_schema_engine_error(monkeypatch):
    """Schema 引擎初始化失败时应保留原始异常信息，便于 Dify 侧定位。"""
    monkeypatch.setattr("service.schema_builder.create_engine", lambda *args, **kwargs: SimpleNamespace(dialect=SimpleNamespace(name="dm")))
    monkeypatch.setattr("service.schema_builder.event.listens_for", lambda *args, **kwargs: (lambda callback: callback))
    monkeypatch.setattr("service.schema_builder.SchemaEngine", lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("dm inspector failed")))

    try:
        SchemaRAGBuilder(
            DatabaseConfig(
                type="dameng",
                host="localhost",
                port=5236,
                user="SYSDBA",
                password="SYSDBA",
                database="SUPPLY_CHAIN_SECURITY",
            ),
            LoggerConfig(),
        )
    except RuntimeError as exc:
        assert "dm inspector failed" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")


def test_dameng_db_name_preserves_schema_case(monkeypatch):
    """达梦 schema 名应保留用户输入大小写，避免部署后 owner 反射失败。"""
    captured = {}

    def fake_sql_database_init(
        self,
        engine,
        schema=None,
        metadata=None,
        ignore_tables=None,
        include_tables=None,
        sample_rows_in_table_info=3,
        indexes_in_table_info=False,
        custom_table_info=None,
        view_support=False,
        max_string_length=300,
    ):
        captured["schema"] = schema
        self._engine = engine
        self._inspector = SimpleNamespace()
        self._usable_tables = []

    monkeypatch.setattr(SQLDatabase, "__init__", fake_sql_database_init)

    engine = SimpleNamespace(dialect=SimpleNamespace(name="dm"))

    SchemaEngine(engine=engine, db_name="SUPPLY_CHAIN_SECURITY")

    assert captured["schema"] == "SUPPLY_CHAIN_SECURITY"
