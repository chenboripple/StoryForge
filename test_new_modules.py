#!/usr/bin/env python3
"""
测试新模块的语法和基本导入
"""

import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("=" * 60)
print("测试 1: 导入 extraction 模块")
print("=" * 60)
try:
    from stages.extraction.knowledge_extractor import KnowledgeExtractor
    print("✓ extraction.knowledge_extractor 导入成功")
    print(f"  - KnowledgeExtractor class: {KnowledgeExtractor}")
except Exception as e:
    print(f"✗ 导入失败: {e}")

print("\n" + "=" * 60)
print("测试 2: 导入 ip_generation 模块")
print("=" * 60)
try:
    from stages.ip_generation.ip_generator import IPGenerator
    print("✓ ip_generation.ip_generator 导入成功")
    print(f"  - IPGenerator class: {IPGenerator}")
except Exception as e:
    print(f"✗ 导入失败: {e}")

print("\n" + "=" * 60)
print("测试 3: 导入 outline 模块")
print("=" * 60)
try:
    from stages.outline.outline_generator import OutlineGenerator
    print("✓ outline.outline_generator 导入成功")
    print(f"  - OutlineGenerator class: {OutlineGenerator}")
except Exception as e:
    print(f"✗ 导入失败: {e}")

print("\n" + "=" * 60)
print("测试 4: 检查所有模块的 __init__.py")
print("=" * 60)
for module in ['extraction', 'ip_generation', 'outline']:
    init_path = project_root / 'stages' / module / '__init__.py'
    if init_path.exists():
        print(f"✓ stages/{module}/__init__.py 存在")
    else:
        print(f"✗ stages/{module}/__init__.py 不存在")

print("\n" + "=" * 60)
print("测试 5: 列出 stages 目录结构")
print("=" * 60)
stages_dir = project_root / 'stages'
if stages_dir.exists():
    for item in sorted(stages_dir.rglob('*.py')):
        rel_path = item.relative_to(project_root)
        print(f"  - {rel_path}")

print("\n" + "=" * 60)
print("所有测试完成!")
print("=" * 60)
