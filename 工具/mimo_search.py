# -*- coding: utf-8 -*-
"""
小米MiMo联网搜索工具 —— 实时搜索最新信息

用法:
    python mimo_search.py "胜宏科技 今天为什么涨"
    python mimo_search.py "天孚通信 主力资金 最新"
    python mimo_search.py "康宁 玻璃桥 光模块" --limit 3

环境变量:
    MIMO_API_KEY: 小米MiMo API Key（必须，或在 工具/.env 中配置）

数据源: 小米MiMo联网服务插件（OpenAI兼容协议）
"""
import os
import sys
import argparse
from pathlib import Path
from openai import OpenAI


def load_env():
    """从工具目录下的 .env 文件加载环境变量"""
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip().strip("'\"")
                    if key and value and key not in os.environ:
                        os.environ[key] = value


def get_client():
    """获取MiMo客户端"""
    load_env()  # 先从 .env 文件加载
    api_key = os.environ.get("MIMO_API_KEY")
    base_url = os.environ.get("MIMO_BASE_URL", "https://api.xiaomimimo.com/v1")
    if not api_key:
        print("错误: 未设置 MIMO_API_KEY 环境变量")
        print("请设置: export MIMO_API_KEY='你的key'")
        print("或在 工具/.env 文件中配置")
        sys.exit(1)

    return OpenAI(
        api_key=api_key,
        base_url=base_url
    )


def search(query, max_keyword=3, force_search=True, limit=1):
    """调用MiMo联网搜索"""
    client = get_client()

    completion = client.chat.completions.create(
        model="mimo-v2.5-pro",
        messages=[
            {
                "role": "system",
                "content": "你是小米MiMo，一个AI助手。今天是2026年6月30日。请根据搜索结果回答问题。"
            },
            {
                "role": "user",
                "content": query
            }
        ],
        tools=[
            {
                "type": "web_search",
                "max_keyword": max_keyword,
                "force_search": force_search,
                "limit": limit
            }
        ],
        temperature=0.7,
        max_completion_tokens=1024
    )

    return completion


def format_result(completion):
    """格式化输出结果"""
    choice = completion.choices[0]
    message = choice.message

    # 输出回答内容
    print("=" * 60)
    print("回答:")
    print("=" * 60)
    print(message.content)

    # 输出引用来源
    if hasattr(message, 'annotations') and message.annotations:
        print("\n" + "=" * 60)
        print("引用来源:")
        print("=" * 60)
        for i, ann in enumerate(message.annotations, 1):
            if ann.type == "url_citation":
                print(f"\n[{i}] {ann.title}")
                print(f"    链接: {ann.url}")
                if hasattr(ann, 'summary') and ann.summary:
                    # 截取前100字
                    summary = ann.summary[:100] + "..." if len(ann.summary) > 100 else ann.summary
                    print(f"    摘要: {summary}")

    # 输出使用统计
    if hasattr(completion, 'usage') and completion.usage:
        usage = completion.usage
        if hasattr(usage, 'web_search_usage'):
            ws = usage.web_search_usage
            # 兼容dict和对象两种格式
            if isinstance(ws, dict):
                print(f"\n搜索统计: {ws.get('tool_usage', 0)}次搜索, {ws.get('page_usage', 0)}个页面")
            else:
                print(f"\n搜索统计: {ws.tool_usage}次搜索, {ws.page_usage}个页面")


def main():
    parser = argparse.ArgumentParser(description="小米MiMo联网搜索工具")
    parser.add_argument("query", help="搜索关键词")
    parser.add_argument("--max-keyword", type=int, default=3, help="最大关键词数(默认3)")
    parser.add_argument("--limit", type=int, default=1, help="返回结果数量(默认1)")
    parser.add_argument("--no-force", action="store_true", help="不强制搜索")

    args = parser.parse_args()

    completion = search(
        query=args.query,
        max_keyword=args.max_keyword,
        force_search=not args.no_force,
        limit=args.limit
    )

    format_result(completion)


if __name__ == "__main__":
    main()
