"""
提取数据库 schema 并保存到文件
"""
import sys
import os
import json

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine
from core.m_schema.schema_engine import SchemaEngine


def clear_examples(mschema):
    """清除所有表的示例数据，缩短执行时间"""
    for table_name, table_info in mschema.tables.items():
        if "fields" in table_info:
            for field_name, field_info in table_info["fields"].items():
                if "examples" in field_info:
                    field_info["examples"] = []
        if "examples" in table_info:
            table_info["examples"] = []


def extract_schema(db_config_path: str, output_path: str, skip_examples: bool = False):
    """从配置文件读取数据库连接信息，提取 schema 并保存"""

    # 读取配置
    with open(db_config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)

    # 构建连接字符串
    db_type = config.get('type', 'mysql')
    host = config.get('host', 'localhost')
    port = config.get('port', 3306)
    user = config.get('user', 'root')
    password = config.get('password', '')
    database = config.get('database', '')

    if db_type == 'mysql':
        connection_string = f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}?charset=utf8mb4"
    elif db_type == 'postgresql':
        connection_string = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}"
    elif db_type == 'mssql':
        connection_string = f"mssql+pymssql://{user}:{password}@{host}:{port}/{database}"
    else:
        raise ValueError(f"不支持的数据库类型: {db_type}")

    print(f"正在连接数据库: {host}:{port}/{database}")

    # 创建引擎并提取 schema
    engine = create_engine(
        connection_string,
        pool_pre_ping=True,
        pool_recycle=3600
    )

    try:
        schema_engine = SchemaEngine(
            engine=engine,
            db_name=database
        )

        # 如果指定跳过示例数据，清除所有示例
        if skip_examples:
            print("跳过示例数据查询...")
            clear_examples(schema_engine.mschema)

        # 生成 schema 文本
        schema_content = schema_engine.mschema.to_mschema(
            example_num=0 if skip_examples else 3,
            show_type_detail=False
        )

        # 保存到文件
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(schema_content)

        print(f"✓ Schema 已保存到: {output_path}")
        print(f"✓ 共包含 {len(schema_engine.mschema.tables)} 个表")

        # 打印表列表
        print("\n表列表:")
        for table_name in schema_engine.mschema.tables.keys():
            print(f"  - {table_name}")

    finally:
        engine.dispose()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='提取数据库 schema')
    parser.add_argument('--config', '-c',
                        default='db_config.json',
                        help='数据库配置文件路径')
    parser.add_argument('--output', '-o',
                        default='schema.txt',
                        help='输出文件路径')
    parser.add_argument('--no-examples',
                        action='store_true',
                        help='跳过示例数据查询，可大幅缩短执行时间')

    args = parser.parse_args()

    extract_schema(args.config, args.output, args.no_examples)
