# Rule Metrics

| Metric 名字 | Scope | **Required input** | 可配置字段（`dynamic_config`） | Description | Example |
|---|---|---|---|---|---|
| `Rule_TC609_0201_FormatCompliance` | 单条数据记录 | `field_schema` 中声明的字段 | <ul><li><code>field_schema</code>：字段名称与预期类型的映射</li><li><code>allow_extra</code>：是否允许记录包含 schema 之外的字段</li></ul> | 按 `field_schema` 检查记录是否包含指定字段，以及各字段的实际类型是否符合要求；还可检查未声明的额外字段。 | — |
| `Rule_TC609_0203_AnnotationCompliance` | 单条数据记录 | `annotation` | 无 | 检查标注信息的结构：`label` 必须是非空列表，`annotation_method` 和 `annotator` 必须是支持的枚举值或 `None`。 | — |
| `Rule_TC609_0204_StructuralCompleteness` | 单条数据记录 | `key_list` 中声明的字段 | <ul><li><code>key_list</code>：需要检查的字段</li><li><code>allow_none</code>：是否允许字段值为 <code>None</code></li><li><code>allow_empty</code>：是否允许空字符串、列表或字典</li></ul> | 检查 `key_list` 指定的字段是否缺失，以及字段值是否满足非空要求。 | — |
| `Rule_TC609_0205_ContentAuthenticity` | 单条数据记录 | `source`、`source_details` | 无 | 检查数据来源及来源详情是否为非空字符串；当 `source` 为“互联网”时，同时检查 `source_details` 是否为有效的 HTTP/HTTPS URL。 | — |
| `Rule_TC609_0208_ContentCleanliness` | 单条数据记录 | `data_content` | <ul><li><code>key_list</code>：水印关键词列表</li></ul> | 对 `data_content` 中的文本执行异常字符、异常 HTML、重复内容、空内容和水印检查。 | — |
