"""
StoryForge - 导出器

职责：
1. 支持导出为 Word/PDF/EPUB/Markdown 格式
2. 支持按章节/卷/全书导出
3. 支持自定义模板
4. 支持生成目录和元数据
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
import os
import json
from datetime import datetime


class ExportFormat(Enum):
    """导出格式"""
    MARKDOWN = "markdown"
    WORD = "word"
    PDF = "pdf"
    EPUB = "epub"
    TXT = "txt"
    HTML = "html"


class ExportScope(Enum):
    """导出范围"""
    CHAPTER = "chapter"      # 单章
    VOLUME = "volume"        # 单卷
    FULL = "full"            # 全书


@dataclass
class ExportTemplate:
    """导出模板"""
    name: str
    format: ExportFormat
    header: str = ""           # 页眉模板
    footer: str = ""           # 页脚模板
    chapter_template: str = ""  # 章节模板
    toc_template: str = ""      # 目录模板
    css_style: str = ""         # CSS 样式（HTML/PDF 用）
    metadata: Dict[str, Any] = field(default_factory=dict)


class NovelExporter:
    """
    小说导出器

    使用示例：
    ```python
    from core.export import NovelExporter, ExportFormat, ExportScope
    
    exporter = NovelExporter(output_dir="./exports")
    
    # 导出全书为 Markdown
    exporter.export(
        novel_data=novel_data,
        format=ExportFormat.MARKDOWN,
        scope=ExportScope.FULL,
        output_name="我的小说"
    )
    
    # 导出单卷为 EPUB
    exporter.export(
        novel_data=novel_data,
        format=ExportFormat.EPUB,
        scope=ExportScope.VOLUME,
        volume_id=1,
        output_name="第一卷"
    )
    ```
    """

    # 默认模板
    DEFAULT_TEMPLATES: Dict[ExportFormat, ExportTemplate] = {
        ExportFormat.MARKDOWN: ExportTemplate(
            name="default_markdown",
            format=ExportFormat.MARKDOWN,
            chapter_template="""# 第{chapter_id}章 {chapter_title}

{chapter_content}

---

""",
            toc_template="""# {novel_title}

{novel_description}

## 目录

{toc_entries}

---

""",
            metadata={
                "file_extension": ".md",
                "mime_type": "text/markdown"
            }
        ),
        ExportFormat.TXT: ExportTemplate(
            name="default_txt",
            format=ExportFormat.TXT,
            chapter_template="""第{chapter_id}章 {chapter_title}

{chapter_content}

{'='*50}

""",
            toc_template="""{novel_title}

{novel_description}

目录

{toc_entries}

{'='*50}

""",
            metadata={
                "file_extension": ".txt",
                "mime_type": "text/plain"
            }
        ),
        ExportFormat.HTML: ExportTemplate(
            name="default_html",
            format=ExportFormat.HTML,
            header="""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{novel_title}</title>
    <style>
        {css_style}
    </style>
</head>
<body>
    <div class="container">
""",
            footer="""
    </div>
</body>
</html>
""",
            chapter_template="""        <div class="chapter" id="chapter-{chapter_id}">
            <h1>第{chapter_id}章 {chapter_title}</h1>
            <div class="content">
{chapter_content}
            </div>
        </div>
""",
            toc_template="""        <div class="toc">
            <h1>{novel_title}</h1>
            <p class="description">{novel_description}</p>
            <h2>目录</h2>
            <ul>
{toc_entries}
            </ul>
        </div>
""",
            css_style="""
        body {
            font-family: "Noto Serif CJK SC", "Source Han Serif SC", serif;
            line-height: 1.8;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
        }
        .chapter {
            margin-bottom: 40px;
        }
        h1 {
            font-size: 1.8em;
            margin-bottom: 20px;
            border-bottom: 2px solid #333;
            padding-bottom: 10px;
        }
        .content {
            text-align: justify;
            text-indent: 2em;
        }
        .toc {
            margin-bottom: 40px;
        }
        .toc ul {
            list-style: none;
            padding: 0;
        }
        .toc li {
            padding: 5px 0;
            border-bottom: 1px dotted #ccc;
        }
        .toc a {
            text-decoration: none;
            color: #333;
        }
        .toc a:hover {
            color: #666;
        }
""",
            metadata={
                "file_extension": ".html",
                "mime_type": "text/html"
            }
        )
    }

    def __init__(self, output_dir: str = "./exports"):
        self.output_dir = output_dir
        self.templates: Dict[ExportFormat, ExportTemplate] = {}
        
        # 加载默认模板
        for fmt, template in self.DEFAULT_TEMPLATES.items():
            self.templates[fmt] = template
        
        # 确保目录存在
        os.makedirs(output_dir, exist_ok=True)
    
    def export(
        self,
        novel_data: Dict[str, Any],
        format: ExportFormat,
        scope: ExportScope = ExportScope.FULL,
        output_name: Optional[str] = None,
        volume_id: Optional[int] = None,
        chapter_id: Optional[int] = None,
        template: Optional[ExportTemplate] = None,
        include_toc: bool = True,
        include_metadata: bool = True
    ) -> str:
        """
        导出小说

        Args:
            novel_data: 小说数据
                {
                    "title": "小说标题",
                    "author": "作者",
                    "description": "简介",
                    "chapters": {
                        1: {"title": "章标题", "content": "内容"},
                        ...
                    },
                    "volumes": {
                        1: {"name": "卷名", "chapters": [1, 2, 3]},
                        ...
                    }
                }
            format: 导出格式
            scope: 导出范围
            output_name: 输出文件名（不含扩展名）
            volume_id: 卷 ID（scope=VOLUME 时）
            chapter_id: 章节 ID（scope=CHAPTER 时）
            template: 自定义模板
            include_toc: 是否包含目录
            include_metadata: 是否包含元数据

        Returns:
            str: 输出文件路径
        """
        # 获取模板
        tmpl = template or self.templates.get(format)
        if not tmpl:
            raise ValueError(f"不支持的导出格式: {format.value}")
        
        # 确定输出文件名
        if not output_name:
            output_name = novel_data.get("title", "未命名小说")
            if scope == ExportScope.VOLUME and volume_id:
                output_name += f"_第{volume_id}卷"
            elif scope == ExportScope.CHAPTER and chapter_id:
                output_name += f"_第{chapter_id}章"
        
        # 清理文件名
        output_name = self._sanitize_filename(output_name)
        output_path = os.path.join(
            self.output_dir,
            f"{output_name}{tmpl.metadata.get('file_extension', '.txt')}"
        )
        
        # 收集要导出的章节
        chapters_to_export = self._collect_chapters(
            novel_data, scope, volume_id, chapter_id
        )
        
        # 生成内容
        content = self._generate_content(
            novel_data=novel_data,
            chapters=chapters_to_export,
            template=tmpl,
            format=format,
            include_toc=include_toc,
            include_metadata=include_metadata
        )
        
        # 写入文件
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"✅ 导出完成: {output_path}")
        return output_path
    
    def export_batch(
        self,
        novel_data: Dict[str, Any],
        formats: List[ExportFormat],
        scope: ExportScope = ExportScope.FULL,
        output_name: Optional[str] = None
    ) -> List[str]:
        """
        批量导出多种格式

        Args:
            novel_data: 小说数据
            formats: 导出格式列表
            scope: 导出范围
            output_name: 输出文件名

        Returns:
            List[str]: 输出文件路径列表
        """
        output_paths = []
        for fmt in formats:
            try:
                path = self.export(
                    novel_data=novel_data,
                    format=fmt,
                    scope=scope,
                    output_name=output_name
                )
                output_paths.append(path)
            except Exception as e:
                print(f"❌ 导出 {fmt.value} 失败: {e}")
        
        return output_paths
    
    def register_template(self, template: ExportTemplate):
        """注册自定义模板"""
        self.templates[template.format] = template
        print(f"✅ 已注册模板: {template.name} ({template.format.value})")
    
    def _collect_chapters(
        self,
        novel_data: Dict,
        scope: ExportScope,
        volume_id: Optional[int],
        chapter_id: Optional[int]
    ) -> Dict[int, Dict]:
        """收集要导出的章节"""
        all_chapters = novel_data.get("chapters", {})
        
        if scope == ExportScope.FULL:
            return all_chapters
        
        elif scope == ExportScope.VOLUME:
            if volume_id is None:
                raise ValueError("导出卷时需要指定 volume_id")
            
            volumes = novel_data.get("volumes", {})
            volume = volumes.get(volume_id)
            if not volume:
                raise ValueError(f"找不到卷 {volume_id}")
            
            chapter_ids = volume.get("chapters", [])
            return {
                ch_id: all_chapters[ch_id]
                for ch_id in chapter_ids
                if ch_id in all_chapters
            }
        
        elif scope == ExportScope.CHAPTER:
            if chapter_id is None:
                raise ValueError("导出章节时需要指定 chapter_id")
            
            if chapter_id not in all_chapters:
                raise ValueError(f"找不到章节 {chapter_id}")
            
            return {chapter_id: all_chapters[chapter_id]}
        
        return {}
    
    def _generate_content(
        self,
        novel_data: Dict,
        chapters: Dict[int, Dict],
        template: ExportTemplate,
        format: ExportFormat,
        include_toc: bool,
        include_metadata: bool
    ) -> str:
        """生成导出内容"""
        parts = []
        
        # 头部
        if template.header:
            header = template.header.format(
                novel_title=novel_data.get("title", "未命名"),
                css_style=template.css_style
            )
            parts.append(header)
        
        # 目录
        if include_toc and template.toc_template:
            toc_entries = self._generate_toc_entries(chapters, format)
            toc = template.toc_template.format(
                novel_title=novel_data.get("title", "未命名"),
                novel_description=novel_data.get("description", ""),
                toc_entries=toc_entries
            )
            parts.append(toc)
        
        # 元数据
        if include_metadata:
            metadata = self._generate_metadata(novel_data)
            parts.append(metadata)
        
        # 章节内容
        for chapter_id in sorted(chapters.keys()):
            chapter = chapters[chapter_id]
            chapter_content = self._format_chapter_content(
                chapter.get("content", ""),
                format
            )
            
            chapter_text = template.chapter_template.format(
                chapter_id=chapter_id,
                chapter_title=chapter.get("title", f"第{chapter_id}章"),
                chapter_content=chapter_content
            )
            parts.append(chapter_text)
        
        # 尾部
        if template.footer:
            parts.append(template.footer)
        
        return "\n".join(parts)
    
    def _generate_toc_entries(self, chapters: Dict[int, Dict], format: ExportFormat) -> str:
        """生成目录条目"""
        entries = []
        
        for chapter_id in sorted(chapters.keys()):
            chapter = chapters[chapter_id]
            title = chapter.get("title", f"第{chapter_id}章")
            
            if format == ExportFormat.HTML:
                entries.append(
                    f'                <li><a href="#chapter-{chapter_id}">'
                    f'第{chapter_id}章 {title}</a></li>'
                )
            elif format == ExportFormat.MARKDOWN:
                entries.append(f"- [第{chapter_id}章 {title}](#第{chapter_id}章-{title})")
            else:
                entries.append(f"第{chapter_id}章 {title}")
        
        return "\n".join(entries)
    
    def _generate_metadata(self, novel_data: Dict) -> str:
        """生成元数据"""
        metadata_parts = []
        
        if "author" in novel_data:
            metadata_parts.append(f"作者: {novel_data['author']}")
        
        if "genre" in novel_data:
            metadata_parts.append(f"类型: {novel_data['genre']}")
        
        if "word_count" in novel_data:
            metadata_parts.append(f"字数: {novel_data['word_count']}")
        
        if "created_at" in novel_data:
            metadata_parts.append(f"创建时间: {novel_data['created_at']}")
        
        if metadata_parts:
            return "\n".join(metadata_parts) + "\n\n---\n\n"
        
        return ""
    
    def _format_chapter_content(self, content: str, format: ExportFormat) -> str:
        """格式化章节内容"""
        if format == ExportFormat.HTML:
            # 简单转义 HTML
            content = content.replace("&", "&amp;")
            content = content.replace("<", "&lt;")
            content = content.replace(">", "&gt;")
            
            # 将段落包装在 <p> 标签中
            paragraphs = content.split("\n\n")
            formatted = []
            for para in paragraphs:
                para = para.strip()
                if para:
                    formatted.append(f"                <p>{para}</p>")
            
            return "\n".join(formatted)
        
        elif format == ExportFormat.MARKDOWN:
            # Markdown 不需要特殊处理
            return content
        
        elif format == ExportFormat.TXT:
            # 纯文本不需要特殊处理
            return content
        
        return content
    
    def _sanitize_filename(self, name: str) -> str:
        """清理文件名"""
        # 替换非法字符
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            name = name.replace(char, '_')
        
        # 移除首尾空格
        name = name.strip()
        
        # 限制长度
        if len(name) > 100:
            name = name[:100]
        
        return name


# ========== 便捷函数 ==========

def export_novel(
    novel_data: Dict[str, Any],
    output_dir: str = "./exports",
    formats: Optional[List[ExportFormat]] = None
) -> List[str]:
    """
    便捷函数：导出小说

    Args:
        novel_data: 小说数据
        output_dir: 输出目录
        formats: 导出格式（默认全部）

    Returns:
        List[str]: 输出文件路径列表
    """
    if formats is None:
        formats = [ExportFormat.MARKDOWN, ExportFormat.HTML, ExportFormat.TXT]
    
    exporter = NovelExporter(output_dir=output_dir)
    return exporter.export_batch(
        novel_data=novel_data,
        formats=formats,
        scope=ExportScope.FULL
    )
