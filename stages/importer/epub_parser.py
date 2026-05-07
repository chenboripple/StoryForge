"""
StoryForge - EPUB 解析器
"""
import re
import os
import tempfile
import zipfile
from xml.etree import ElementTree as ET

from .base_parser import BaseParser, ImportResult, ChapterImport


class EPUBParser(BaseParser):
    """
    解析 EPUB 电子书
    依赖：内置 zipfile + xml 解析（无额外依赖）
    """

    supported_extensions = {"epub"}

    # EPUB 常用的命名空间
    NS = {
        "dc": "http://purl.org/dc/elements/1.1/",
        "opf": "http://www.idpf.org/2007/opf",
        "ncx": "http://www.daisy.org/z3986/2005/ncx/",
    }

    def parse(self, filepath: str, **options) -> ImportResult:
        """解析 EPUB 文件"""
        errors = []
        warnings = []

        try:
            with zipfile.ZipFile(filepath, "r") as zf:
                # 读取容器文件找到 OPF
                opf_path = self._find_opf_path(zf)
                if not opf_path:
                    return ImportResult(
                        success=False,
                        errors=["无法找到 EPUB 内容描述文件 (OPF)"]
                    )

                # 读取 OPF 获取元数据和章节列表
                opf_content = zf.read(opf_path).decode("utf-8", errors="replace")
                opf_root = ET.fromstring(opf_content)

                metadata = self._extract_metadata(opf_root)
                spine = self._extract_spine(opf_root, opf_path)

                # 读取章节内容
                base_dir = os.path.dirname(opf_path) if "/" in opf_path else ""
                chapters = []
                total_words = 0
                chapter_num = 1

                for item_id, item_path, nav_label in spine:
                    full_path = f"{base_dir}/{item_path}" if base_dir else item_path
                    full_path = full_path.replace("//", "/")

                    try:
                        raw = zf.read(full_path).decode("utf-8", errors="replace")
                        text = self._strip_html_tags(raw)
                    except KeyError:
                        # 路径可能在 OEBPS/ 下
                        alt_path = f"OEBPS/{full_path}" if not full_path.startswith("OEBPS/") else full_path[6:]
                        try:
                            raw = zf.read(alt_path).decode("utf-8", errors="replace")
                            text = self._strip_html_tags(raw)
                        except KeyError:
                            warnings.append(f"找不到章节文件: {full_path}")
                            continue

                    if not text.strip():
                        continue

                    word_count = self._count_words(text)
                    total_words += word_count

                    # 使用导航标签作为标题
                    title = nav_label or f"第{chapter_num}章"

                    chapters.append(ChapterImport(
                        chapter_num=chapter_num,
                        title=title,
                        content=text,
                        word_count=word_count,
                        metadata={"source_id": item_id, "source_path": item_path}
                    ))
                    chapter_num += 1

                if not chapters:
                    return ImportResult(
                        success=False,
                        errors=["EPUB 中未能提取到任何有效章节"]
                    )

                title = metadata.get("title", self._detect_title(chapters[0].content if chapters else ""))

                return ImportResult(
                    success=True,
                    novel_title=title,
                    author=metadata.get("author", ""),
                    genre=metadata.get("genre", ""),
                    total_chapters=len(chapters),
                    total_word_count=total_words,
                    chapters=chapters,
                    raw_text="\n\n".join(ch.content for ch in chapters),
                    metadata=metadata,
                    errors=errors,
                    warnings=warnings
                )

        except zipfile.BadZipFile:
            return ImportResult(success=False, errors=["不是有效的 EPUB/ZIP 文件"])
        except Exception as e:
            return ImportResult(success=False, errors=[f"EPUB 解析失败: {str(e)}"])

    def _find_opf_path(self, zf: zipfile.ZipFile) -> str:
        """通过 container.xml 找到 OPF 文件路径"""
        try:
            container = zf.read("META-INF/container.xml").decode("utf-8")
            root = ET.fromstring(container)
            for elem in root.iter():
                if "rootfile" in elem.tag:
                    return elem.get("full-path", "")
        except (KeyError, ET.ParseError):
            pass
        # 备选：搜索 OPF 文件
        for name in zf.namelist():
            if name.endswith(".opf"):
                return name
        return ""

    def _extract_metadata(self, opf_root: ET.Element) -> dict:
        """从 OPF 提取元数据"""
        metadata = {}
        metadata_elem = opf_root.find(".//opf:metadata", self.NS)
        if metadata_elem is None:
            metadata_elem = opf_root.find(".//{http://www.idpf.org/2007/opf}metadata")
        if metadata_elem is None:
            metadata_elem = opf_root.find(".//metadata")

        if metadata_elem is not None:
            for child in metadata_elem:
                tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                text = child.text.strip() if child.text else ""
                if not text:
                    continue
                if tag in ("title",):
                    metadata["title"] = text
                elif tag in ("creator", "author"):
                    metadata["author"] = text
                elif tag in ("description",):
                    metadata["description"] = text
                elif tag in ("subject",):
                    metadata["genre"] = text

        return metadata

    def _extract_spine(self, opf_root: ET.Element, opf_path: str) -> list:
        """
        提取章节顺序列表
        返回: [(item_id, href, nav_label), ...]
        """
        # 获取 manifest 中所有 item
        manifest = {}
        manifest_elem = opf_root.find(".//opf:manifest", self.NS)
        if manifest_elem is None:
            manifest_elem = opf_root.find(".//{http://www.idpf.org/2007/opf}manifest")
        if manifest_elem is None:
            manifest_elem = opf_root.find(".//manifest")

        if manifest_elem is not None:
            for item in manifest_elem:
                item_id = item.get("id", "")
                href = item.get("href", "")
                media_type = item.get("media-type", "")
                if media_type in ("application/xhtml+xml", "text/html", "application/xml"):
                    manifest[item_id] = href

        # 按 spine 顺序排列
        spine = []
        spine_elem = opf_root.find(".//opf:spine", self.NS)
        if spine_elem is None:
            spine_elem = opf_root.find(".//{http://www.idpf.org/2007/opf}spine")
        if spine_elem is None:
            spine_elem = opf_root.find(".//spine")

        if spine_elem is not None:
            for itemref in spine_elem:
                item_id = itemref.get("idref", "")
                if item_id in manifest:
                    spine.append((item_id, manifest[item_id], ""))

        # 如果没有 spine，按 manifest 顺序
        if not spine:
            for item_id, href in manifest.items():
                spine.append((item_id, href, ""))

        return spine

    def _strip_html_tags(self, html: str) -> str:
        """去除 HTML/XHTML 标签"""
        # 移除 script/style
        html = re.sub(r"<script[\s\S]*?</script>", "", html, flags=re.IGNORECASE)
        html = re.sub(r"<style[\s\S]*?</style>", "", html, flags=re.IGNORECASE)
        # 移除标签
        html = re.sub(r"<[^>]+>", "", html)
        # 解码实体
        html = html.replace("&nbsp;", " ")
        html = html.replace("&amp;", "&")
        html = html.replace("&lt;", "<")
        html = html.replace("&gt;", ">")
        html = html.replace("&quot;", "'")
        # 规范化空白
        html = re.sub(r"\n\s*\n+", "\n\n", html)
        return html.strip()
