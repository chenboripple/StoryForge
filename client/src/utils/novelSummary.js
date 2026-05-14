/**
 * 从 concept 中提取简洁的摘要信息
 * concept 可能是：
 * 1. Markdown 格式的大纲（如 # 《标题》大纲）
 * 2. JSON 格式（如 {"title": "xxx", "meta": {...}}）
 * 3. 纯文本描述
 */
export function extractSummary(concept, maxLength = 80) {
  if (!concept || typeof concept !== 'string') {
    return '暂无描述';
  }

  let text = concept.trim();

  // 尝试解析 JSON
  if (text.startsWith('{')) {
    try {
      const json = JSON.parse(text);
      // 优先取 meta.description 或 meta.type
      if (json.meta) {
        if (json.meta.description) return truncate(json.meta.description, maxLength);
        if (json.meta.type) return truncate(json.meta.type, maxLength);
        if (json.meta.style) return truncate(json.meta.style, maxLength);
      }
      if (json.description) return truncate(json.description, maxLength);
      if (json.summary) return truncate(json.summary, maxLength);
      // 兜底：取 title
      if (json.title) return truncate(json.title, maxLength);
    } catch (e) {
      // 不是合法 JSON，继续按文本处理
    }
  }

  // 去掉 Markdown 标记
  text = text
    .replace(/^#+\s*/gm, '')           // 去掉标题标记 #
    .replace(/\*\*|__/g, '')           // 去掉粗体
    .replace(/\*|_/g, '')              // 去掉斜体
    .replace(/`{1,3}[^`]*`{1,3}/g, '') // 去掉代码块
    .replace(/\[([^\]]*)\]\([^)]*\)/g, '$1') // 去掉链接，保留文字
    .replace(/!\[([^\]]*)\]\([^)]*\)/g, '')  // 去掉图片
    .replace(/\|/g, ' ')               // 表格竖线变空格
    .replace(/-{3,}/g, '')             // 去掉分割线
    .replace(/\n/g, ' ')               // 换行变空格
    .replace(/\s+/g, ' ')              // 多个空格合并
    .trim();

  // 去掉常见的 Markdown 标题前缀（如 "《标题》大纲"）
  text = text.replace(/^《[^》]+》\s*(大纲|总纲|简介|介绍)\s*/i, '');

  return truncate(text, maxLength);
}

function truncate(text, maxLength) {
  if (text.length <= maxLength) return text;
  return text.substring(0, maxLength) + '...';
}

/**
 * 从 concept 中提取字数信息
 */
export function extractWordCount(concept) {
  if (!concept || typeof concept !== 'string') return null;

  // 尝试从 JSON 中提取
  if (concept.trim().startsWith('{')) {
    try {
      const json = JSON.parse(concept);
      if (json.meta?.total_words) return formatWordCount(json.meta.total_words);
      if (json.meta?.word_count) return formatWordCount(json.meta.word_count);
    } catch (e) {
      // ignore
    }
  }

  // 从文本中提取 "xxx万字" 或 "xxx字"
  const match = concept.match(/(\d+(?:\.\d+)?)\s*万?\s*字/);
  if (match) {
    const num = parseFloat(match[1]);
    if (match[0].includes('万')) {
      return formatWordCount(num * 10000);
    }
    return formatWordCount(num);
  }

  return null;
}

function formatWordCount(num) {
  if (num >= 10000) {
    return `${(num / 10000).toFixed(1)}万字`;
  }
  return `${num}字`;
}
