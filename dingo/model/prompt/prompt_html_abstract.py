from dingo.model.model import Model
from dingo.model.prompt.base import BasePrompt


@Model.prompt_register("Html_Abstract", [])
class PromptHtmlAbstract(BasePrompt):
    content = """
你是一位经验丰富的前端工程师，擅长分析 HTML 代码和 Markdown 文本。现在我会提供三段内容：

1. **原始网页的 HTML 代码**：这是网页的完整 HTML 结构。
2. **工具1提取的 Markdown 文本**：这是从 HTML 中提取的、适合大语言模型训练的 Markdown 格式文本。
2. **工具2提取的 Markdown 文本**：这是从 HTML 中提取的、适合大语言模型训练的 Markdown 格式文本。

你的任务：
1. **对比分析**：将两个工具提取出来的 Markdown 文本分别与 HTML 代码做对比。严格按以下模块类型检查提取效果：
   - `code`：代码块（`<pre>`/`<code>` 标签）
   - `math`：数学公式（LaTeX/MathML/AsciiMath 等）
   - `table`：表格（`<table>` 标签）
   - `image`：图片（`<img>` 标签）
   - `list`：有序/无序列表（`<ul>`/`<ol>` 标签）
   - `title`：标题（`<h1>`-`<h6>` 标签）
   - `paragraph`：段落文本（`<p>`/`<div>` 等文本容器）
   - `other`：其他（非以上标签）

2. **评分规则**：评价两个抽取工具的抽取质量，判断哪个工具抽取效果更好。
   - **抽取完整性**：检查 Markdown 文本是否完整抽取了 HTML 中的关键内容（如代码块、表格、图片、列表等）。
   - **格式准确性**：检查 Markdown 文本的格式是否正确（如代码块缩进、表格对齐、图片链接等）。
   - **语义连贯性**：检查 Markdown 文本是否保持了 HTML 内容的语义连贯性（如段落逻辑、标题层次等）。

3. **问题反馈**：严格按上述 8 类模块定位问题，若无问题则返回空列表。

4. **返回结果**：以 JSON 格式返回，包含3个字段：score、name、reason。
   - `score`：如果工具1抽取效果更好，score取值为1。如果工具2抽取效果更好，score取值为2。如果工具1和工具2抽取效果基本相同，score取值为0。
   - `name`：必须从 8 类模块中选择，且选择抽取效果较差工具的最严重、最具代表性的问题模块。
   - `reason`：判断依据，即问题模块为什么差，以及差在哪里。
例如：
```json
{{
  "score": 1,
  "name": "code",
  "reason": "工具2代码块缩进丢失"
}}
```

**注意事项**：
1. 禁止使用预定义模块以外的分类。
2. 重点关注结构化内容（代码、表格、公式、图片等）的转换质量。
3. 段落分析需检查文本连贯性和语义完整性。

### 原始网页的 HTML 代码如下：

```html
{}
```

### 工具1提取的 Markdown 文本如下：

```md
{}
```

### 工具2提取的 Markdown 文本如下：

```md
{}
```


返回结果只有一个 JSON，不要有其他任何解释说明以及分析的信息！
"""
