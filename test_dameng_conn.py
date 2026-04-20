"""用项目关键链路测试达梦：
1) 创建连接（SchemaRAGBuilder/SchemaEngine）
2) 生成 schema 文件（generate_dictionary）
3) 执行 SQL（DatabaseService.execute_query）
"""

from __future__ import annotations

from pathlib import Path
import traceback

from config import DatabaseConfig, LoggerConfig
from service.database_service import DatabaseService
from service.schema_builder import SchemaRAGBuilder


def main():
    db_config = DatabaseConfig(
        type="dameng",
        host="host.docker.internal",
        port=5236,
        user="SYSDBA",
        password="SYSDBA",
        database="test",
    )
    logger_config = LoggerConfig(log_level="INFO")

    # 1) 创建连接 + 初始化 SchemaEngine
    builder = SchemaRAGBuilder(db_config=db_config, logger_config=logger_config)

    # 2) 生成 schema 内容并落盘（代码库入口方法）
    schema_text = builder.generate_dictionary()
    out_path = Path(f"{db_config.database}_schema.txt")
    out_path.write_text(schema_text or "", encoding="utf-8")
    print(f"✓ schema 已生成: {out_path} (chars={len(schema_text or '')})")
    if schema_text:
        head = "\n".join(schema_text.splitlines()[:2])
        print(f"schema 头两行:\n{head}")

    # 3) 执行 SQL（代码库入口方法）
    db_service = DatabaseService()
    results, columns = db_service.execute_query(
        db_type=db_config.type,
        host=db_config.host,
        port=db_config.port,
        user=db_config.user,
        password=db_config.password,
        dbname=db_config.database,
        query="select 1 as ok",
    )
    print(f"✓ SQL 执行成功: columns={columns}, first_row={results[0] if results else None}")

    builder.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"✗ 失败: {e}")
        traceback.print_exc()
