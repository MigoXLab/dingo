# RuleQuanliangFieldValidation Label 说明

## 实现位置

[`rule_quanliang.py`](../../dingo/model/rule/scibase/rule_quanliang.py)

## 标签数量统计

| 字段 | 标签数量 |
|---|---:|
| `metadata_type` | 5 |
| `doi` | 6 |
| `isbns` | 4 |
| `isbn13` | 4 |
| `title` | 36 |
| `abstract` | 45 |
| `language` | 4 |
| `author` | 10 |
| `contributors` | 4 |
| `locations` | 6 |
| `access_is_oa` | 7 |
| `access_oa_status` | 4 |
| `access_oa_url` | 4 |
| `access_license` | 4 |
| `publication_published_date` | 5 |
| `publication_published_year` | 3 |
| `publication_venue_issn` | 4 |
| `publication_venue_biblio_volume` | 4 |
| `publication_venue_biblio_issue` | 4 |
| `publication_venue_biblio_pages` | 6 |
| `publication_pages` | 3 |
| `publication_venue_name_unified` | 5 |
| `grade_class` | 4 |
| `grade` | 5 |
| `references` | 23 |
| `related_works` | 23 |
| `citations` | 23 |
| `supplementary_material` | 4 |
| `cited_by_api_url` | 4 |
| `access_xinghe_repository_sha256` | 4 |
| `access_xinghe_repository_origin_path` | 3 |
| `access_xinghe_repository_model_name` | 4 |
| `access_xinghe_repository_model_version` | 5 |
| **合计** | **276** |

## metadata_type

| Label 名 | 中文名称 | 标签含义 |
|---|---|---|
| `missing_field` | 字段缺失 | 检查输入对象中是否存在 `metadata_type` 字段。 |
| `wrong_type` | 字段类型错误 | 值的类型不是字符串时标记。 |
| `null` | 值为 null | 检查字段值是否为 `null`。 |
| `empty` | 值为空 | 若值为空，则标记。 |
| `unsupported_value` | 值不在限定范围内 | 值须属于 2 个限定值之一：`paper`、`ebook`。 |

## doi

| Label 名 | 中文名称 | 标签含义 |
|---|---|---|
| `missing_field` | 字段缺失 | 检查输入对象中是否存在 `doi` 字段。 |
| `wrong_type` | 字段类型错误 | 值的类型不是字符串时标记。 |
| `empty` | 值为空 | 若论文 DOI 为空，则标记。 |
| `not_lowercase` | 不是小写字母 | 若 DOI 不是小写，则标记。 |
| `format_invalid` | 格式不符合要求 | DOI 去除首尾空白后不符合 `10.<4～9 位数字>/<非空后缀>`；后缀不能含空白或竖线，DOI URL 也不符合。 |
| `error_prefix` | 前缀不符合要求 | 提取 DOI 的 `/` 前缀；命中 3 个测试前缀 `10.0000`、`10.0001`、`10.5555` 时标记。 |

## isbns

| Label 名 | 中文名称 | 标签含义 |
|---|---|---|
| `missing_field` | 字段缺失 | 检查输入对象中是否存在 `isbns` 字段。 |
| `wrong_type` | 字段类型错误 | 值不是字符串列表时标记。 |
| `empty` | 值为空 | 若电子书 ISBN 列表为空，则标记。 |
| `invalid_format` | 格式不符合要求 | 列表中至少一个值不是有效 ISBN-10 或 ISBN-13：ISBN-10 须为 9 位数字加数字/`X` 校验位；ISBN-13 须为 13 位数字、以 `978`/`979` 开头，并通过校验位计算。 |

## isbn13

| Label 名 | 中文名称 | 标签含义 |
|---|---|---|
| `missing_field` | 字段缺失 | 检查输入对象中是否存在 `isbn13` 字段。 |
| `wrong_type` | 字段类型错误 | 值的类型不是字符串时标记。 |
| `empty` | 值为空 | 若电子书 ISBN13 为空，则标记。 |
| `invalid_format` | 格式不符合要求 | 值不是有效 ISBN-13：须为 13 位数字、以 `978` 或 `979` 开头，并通过校验位计算。 |

## title

| Label 名 | 中文名称 | 标签含义 |
|---|---|---|
| `missing_field` | 字段缺失 | 检查输入对象中是否存在 `title` 字段。 |
| `wrong_type` | 字段类型错误 | 值的类型不是字符串时标记。 |
| `null` | 值为 null | 检查字段值是否为 `null`。 |
| `empty` | 值为空 | 若去除首尾空格后内容为空，则标记。 |
| `too_short` | 内容过短 | 若去除首尾空格后长度小于 5 个字符，则标记。 |
| `too_long` | 内容过长 | 若去除首尾空格后长度大于 1000 个字符，则标记。 |
| `html_tag.formatting` | 包含普通排版标签 | 包含普通行内排版标签，如 `<i>`、`<b>`、`<strong>`、`<em>`、`<u>`、`<scp>`、`<tt>`，包括闭合标签和带属性的标签。 |
| `html_tag.structure` | 包含结构或换行标签 | 包含结构、布局或换行标签，如 `<p>`、`<div>`、`<span>`、`<br>`，包括闭合标签和带属性的标签。 |
| `html_tag.link` | 包含链接标签 | 包含 `<a>`、`<ext-link>` 等链接标签，包括闭合标签、带属性的标签及对应命名空间形式。 |
| `html_tag.media` | 包含媒体标签 | 包含 `<img>`、`<graphic>`、`<inline-graphic>` 等图片或媒体节点，包括带属性的标签及对应命名空间形式。 |
| `html_tag.namespaced` | 包含命名空间标签 | 包含 `jats:`、`ns数字:`、`xhtml:` 等命名空间前缀的 XML/JATS 标签；MathML 标签优先归入 `html_tag.math`。 |
| `html_tag.xml_comment` | 包含 XML 注释 | 包含 XML/HTML 注释片段，如 `<!-- comment -->`。 |
| `html_tag.cdata` | 包含 CDATA 内容 | 包含 CDATA 区段，如 `<![CDATA[...]]>`。 |
| `html_tag.sub_sup` | 包含上下标标签 | 包含 `<sub>`、`<sup>` 上下标标签，包括闭合标签和带属性的标签。 |
| `html_tag.math` | 包含 MathML 或公式标签 | 包含 `<math>`、`<mml:math>`、`<mrow>`、`<mi>`、`<mn>`、`<mo>`、`<msub>`、`<msup>`、`<mfrac>`、`<msqrt>`、`<inline-formula>`、`<TEX>` 等公式容器或节点。 |
| `html_tag.incomplete` | HTML/XML 标签残缺 | 标签缺少 `<` 或 `>`、内容被截断，或 XML 注释、CDATA 等结构不完整时标记。 |
| `html_tag.mismatched` | HTML/XML 标签错配 | 开闭标签不匹配、只有单侧标签、标签交叉嵌套，或出现 `<math>...</tex>` 等结构错配时标记。 |
| `html_entity.named` | 包含命名 HTML 实体 | 包含 `&名称;` 形式的命名 HTML 实体，如 `&nbsp;`、`&amp;`。 |
| `html_entity.decimal` | 包含十进制 HTML 实体 | 包含 `&#数字;` 形式的十进制 HTML 实体，如 `&#160;`。 |
| `html_entity.hex` | 包含十六进制 HTML 实体 | 包含 `&#x十六进制;` 形式的 HTML 实体，如 `&#xA0;`。 |
| `markup_tag.formatting` | 包含方括号排版标记 | 包含 `[!i]`、`[!/i]`、`[!sub]`、`[!/sub]`、`[!sup]`、`[!/sup]`、`[!]` 等非标准方括号排版标记。 |
| `markup_tag.crawler` | 包含方括号爬虫标记 | 包含 `[○!R]`、`[○!上]`、`[○!下]` 等已确认的 `[○!...]` 形式爬虫残留。 |
| `special_char.replacement` | 包含 Unicode 替换字符 | 包含 Unicode 替换字符 `�`（U+FFFD）。 |
| `special_char.control` | 包含控制字符 | 包含 U+0000～U+0008、U+000B、U+000C、U+000E～U+001F 或 U+007F；TAB、换行和回车不在此标签范围内。 |
| `special_char.private_use_area` | 包含 Unicode 私用区字符 | 包含 Unicode 基本多文种平面私用区 U+E000～U+F8FF 中的字符。 |
| `invisible_char.zero_width_space` | 包含零宽空格 | 包含零宽空格 U+200B。 |
| `invisible_char.bom` | 包含 BOM 字符 | 字段内容中包含 U+FEFF；该字符位于文本内部时通常是残留的 BOM 或零宽不换行空格。 |
| `invisible_char.zwnj` | 包含零宽不连字符 | 包含 ZWNJ（U+200C）。 |
| `invisible_char.zwj` | 包含零宽连字符 | 包含 ZWJ（U+200D）。 |
| `invisible_char.bidi_control` | 包含双向控制符 | 包含 U+200E、U+200F、U+202A～U+202E、U+2066～U+2069 等双向文本控制字符。 |
| `space_char.nbsp` | 包含不换行空格 | 包含 NBSP（U+00A0）。 |
| `space_char.typographic` | 包含排版空格 | 包含 U+2000～U+200A、U+202F、U+205F、U+3000 等排版或全角空格。 |
| `likely_placeholder` | 疑似占位内容 | 标题去除首尾空白并忽略大小写后，等于预设占位值，如 `untitled`、`[no title]`、`unknown`、`n/a`、`null`、`tbd`、`-` 或 `.`。 |
| `encoding_error` | 编码错误 | 包含常见乱码模式，如 `�`、`锟斤拷`、`烫烫烫`、`屯屯屯`、以 `Ã`/`Â` 开头的双字节乱码、`â€™` 或 `ï»¿`。 |
| `likely_conference` | 疑似会议名称 | 标题以可选年份加 `IEEE` 开头，并包含 `proceedings`、`conference`、`symposium`、`workshop` 或 `congress`。 |
| `likely_identifier` | 疑似标识符或链接 | 整个标题仅由数字、DOI、DOI URL、HTTP(S)/`www` URL，或 `s3://`、`s3a://` 路径构成。 |

## abstract

| Label 名 | 中文名称 | 标签含义 |
|---|---|---|
| `missing_field` | 字段缺失 | 检查输入对象中是否存在 `abstract` 字段。 |
| `wrong_type` | 字段类型错误 | 值的类型不是字符串时标记。 |
| `null` | 值为 null | 检查字段值是否为 `null`。 |
| `empty` | 值为空 | 若去除首尾空格后内容为空，则标记。 |
| `too_short` | 内容过短 | 若去除首尾空格后长度小于 20 个字符，则标记。 |
| `too_long` | 内容过长 | 若去除首尾空格后长度大于 6000 个字符，则标记。 |
| `html_tag.formatting` | 包含普通排版标签 | 包含普通行内排版标签，如 `<i>`、`<b>`、`<strong>`、`<em>`、`<u>`、`<scp>`、`<tt>`，包括闭合标签和带属性的标签。 |
| `html_tag.structure` | 包含结构或布局标签 | 包含 `<p>`、`<br>`、`<div>`、`<span>`、`<h1>`～`<h6>`、`<pre>`、列表及表格等 HTML 结构标签。 |
| `html_tag.link` | 包含链接标签 | 包含 `<a>`、无命名空间的 `<ext-link>`、`<xref>` 等链接或交叉引用标签。 |
| `html_tag.media` | 包含媒体或不可展示节点 | 包含 `<img>`、`<inline-graphic>`、`<graphic>`、`<iframe>` 等媒体或不可直接展示的节点。 |
| `html_tag.jats` | 包含 JATS 标签 | 包含 `<jats:p>`、`<jats:title>`、`<jats:sec>`、`<jats:xref>` 等 `jats:` 前缀标签；此类标签统一归入本标签，不再重复归入结构、链接或其他命名空间标签。 |
| `html_tag.namespaced` | 包含其他命名空间标签 | 包含 `<jats1:...>`、`<ns0:...>`、`<ns3:...>`、`<xhtml:...>` 等其他 XML 命名空间标签；`jats:` 和 `mml:` 分别归入 JATS 与公式标签。 |
| `html_tag.xml_comment` | 包含 XML 注释 | 包含 XML/HTML 注释片段，如 `<!-- comment -->`。 |
| `html_tag.cdata` | 包含 CDATA 内容 | 包含 CDATA 区段，如 `<![CDATA[...]]>`。 |
| `html_tag.xml_declaration` | 包含 XML 声明 | 包含 `<?xml ...?>` 形式的 XML 声明。 |
| `html_tag.doctype` | 包含 DOCTYPE | 包含 `<!DOCTYPE ...>` 形式的 HTML/XML 文档类型声明。 |
| `html_tag.sub_sup` | 包含上下标标签 | 包含 `<sub>`、`<sup>` 上下标标签，包括闭合标签和带属性的标签。 |
| `html_tag.math` | 包含 MathML 或公式标签 | 包含 `<math>`、`<mml:math>`、MathML 子节点、`<inline-formula>`、`<disp-formula>`、`<TEX>` 等公式容器或节点。 |
| `html_tag.incomplete` | HTML/XML 标签残缺 | 标签缺少 `<` 或 `>`、内容被截断，或 XML 注释、CDATA 等结构不完整时标记。 |
| `html_tag.mismatched` | HTML/XML 标签错配 | 开闭标签不匹配、只有单侧标签、跨段或交叉嵌套，以及公式容器开闭标签不一致时标记。 |
| `html_entity.named` | 包含命名 HTML 实体 | 包含 `&名称;` 形式的命名 HTML 实体，如 `&nbsp;`、`&amp;`。 |
| `html_entity.decimal` | 包含十进制 HTML 实体 | 包含 `&#数字;` 形式的十进制 HTML 实体，如 `&#160;`。 |
| `html_entity.hex` | 包含十六进制 HTML 实体 | 包含 `&#x十六进制;` 形式的 HTML 实体，如 `&#xA0;`。 |
| `markup_tag.formatting` | 包含方括号排版标记 | 包含 `[!i]`、`[!/i]`、`[!sub]`、`[!/sub]`、`[!sup]`、`[!/sup]`、`[!]` 等非标准方括号排版标记。 |
| `markup_tag.crawler` | 包含方括号爬虫标记 | 包含 `[○!R]`、`[○!上]`、`[○!下]` 等已确认的 `[○!...]` 形式爬虫残留。 |
| `crawler_residue.etx` | 包含文本形式的 ETX | 包含 `<ETX>`、`<<ETX>>` 等可见的结束控制占位符；本标签不用于真正的 U+0003 控制字符。 |
| `crawler_residue.navigation` | 包含页面导航文本 | 包含 `<Previous page \| Next page>` 等已确认的分页或页面导航残留。 |
| `crawler_residue.template` | 包含页面模板文本 | 包含已确认的下载提示、页面栏目或其他站点模板文本。 |
| `special_char.replacement` | 包含 Unicode 替换字符 | 包含 Unicode 替换字符 `�`（U+FFFD）。 |
| `special_char.control` | 包含控制字符 | 包含 U+0000～U+0008、U+000B、U+000C、U+000E～U+001F 或 U+007F；TAB、换行和回车不在此标签范围内。 |
| `special_char.private_use_area` | 包含 Unicode 私用区字符 | 包含 Unicode 基本多文种平面私用区 U+E000～U+F8FF 中的字符。 |
| `invisible_char.zero_width_space` | 包含零宽空格 | 包含零宽空格 U+200B。 |
| `invisible_char.bom` | 包含 BOM 字符 | 字段内容中包含 U+FEFF；该字符位于文本内部时通常是残留的 BOM 或零宽不换行空格。 |
| `invisible_char.soft_hyphen` | 包含软连字符 | 包含软连字符 U+00AD。 |
| `invisible_char.zwnj` | 包含零宽不连字符 | 包含 ZWNJ（U+200C）。 |
| `invisible_char.zwj` | 包含零宽连字符 | 包含 ZWJ（U+200D）。 |
| `invisible_char.bidi_control` | 包含双向控制符 | 包含 U+200E、U+200F、U+202A～U+202E、U+2066～U+2069 等双向文本控制字符。 |
| `space_char.nbsp` | 包含不换行空格 | 包含 NBSP（U+00A0）。 |
| `space_char.typographic` | 包含排版空格 | 包含 U+2000～U+200A、U+202F、U+205F、U+3000 等排版或全角空格。 |
| `space_char.tab` | 包含 TAB | 包含 TAB（U+0009）字符。 |
| `space_char.excessive_line_break` | 换行过多 | LF、CR 或 CRLF 的数量、连续次数或文本占比超过配置阈值时标记；不因单个合法换行产生标签。 |
| `likely_placeholder` | 疑似占位内容 | 摘要去除首尾空白并忽略大小写后，等于 `n/a`、`none`、`null`、`unknown`、`-` 等，或匹配 `no abstract available`、`abstract not provided`、`unavailable` 等提示语。 |
| `encoding_error` | 编码错误 | 包含常见乱码模式，如 `�`、`锟斤拷`、`烫烫烫`、`屯屯屯`、以 `Ã`/`Â` 开头的双字节乱码、`â€™` 或 `ï»¿`。 |
| `same_title` | 内容与标题重复 | 摘要与字符串类型的非空标题去除首尾空白并忽略大小写后完全相同。 |
| `likely_identifier` | 疑似标识符或链接 | 整个摘要仅由数字、DOI、DOI URL、HTTP(S)/`www` URL，或 `s3://`、`s3a://` 路径构成。 |

## language

| Label 名 | 中文名称 | 标签含义 |
|---|---|---|
| `missing_field` | 字段缺失 | 检查输入对象中是否存在 `language` 字段。 |
| `wrong_type` | 字段类型错误 | 值的类型不是字符串时标记。 |
| `null` | 值为 null | 检查字段值是否为 `null`。 |
| `unsupported_value` | 值不在限定范围内 | 值须属于 ISO 639 映射表中的 8038 个语言代码之一，例如 `zh`、`en`、`fr`、`de`。 |

## author

| Label 名 | 中文名称 | 标签含义 |
|---|---|---|
| `missing_field` | 字段缺失 | 检查输入对象中是否存在 `author` 字段。 |
| `wrong_type` | 字段类型错误 | 检查值是否为作者对象列表，并逐项检查对象属性类型。 |
| `null` | 值为 null | 检查字段值是否为 `null`。 |
| `empty` | 值为空 | 若作者列表为空，则标记。 |
| `invalid_keys` | key 不符合要求 | 若作者对象字段不符合要求，则标记。 |
| `empty_name` | 名称为空 | 若至少一个作者姓名去除首尾空格后为空，则标记。 |
| `duplicated_name` | 名称重复 | 非空作者名经去除首尾空白、连续空白折叠为一个空格并执行 Unicode 不区分大小写归一化后出现重复。 |
| `multiple_names` | 单项疑似包含多个作者名 | 单个 `author[].name` 命中多人名信号，如末尾 `et al.`/“等”、连接词 `and`/“和”/“与”/“及”/顿号、分号或竖线、`Alice&Bob`、中西文逗号分隔的两个人名、多个逗号，或多个中文姓名由空白分隔。该规则以高召回方式生成候选。 |
| `invalid_separator` | 包含非法分隔符 | 作者名包含竖线、英文/中文分号，或连续两个英文/中文逗号，如 `Alice; Bob`、`张三，，李四`。 |
| `invalid_orcid` | ORCID 不合法 | 非空 ORCID 不符合 `https://orcid.org/0000-0000-0000-000X` 形式，或未通过 MOD 11-2 校验位计算；空字符串允许。 |

## contributors

| Label 名 | 中文名称 | 标签含义 |
|---|---|---|
| `missing_field` | 字段缺失 | 检查输入对象中是否存在 `contributors` 字段。 |
| `wrong_type` | 字段类型错误 | 值不是字符串列表时标记。 |
| `null` | 值为 null | 检查字段值是否为 `null`。 |
| `invalid_separator` | 包含非法分隔符 | 若姓名包含非法分隔符，则标记。 |

## locations

| Label 名 | 中文名称 | 标签含义 |
|---|---|---|
| `missing_field` | 字段缺失 | 检查输入对象中是否存在 `locations` 字段。 |
| `wrong_type` | 字段类型错误 | 检查值是否为列表，并逐项检查列表项类型。 |
| `null` | 值为 null | 检查字段值是否为 `null`。 |
| `missing_key` | key 缺失 | 若位置对象缺少必需字段，则标记。 |
| `invalid_value` | 值不合法 | 逐项检查位置对象：`type` 共 4 个限定值，`license` 共 27 个限定值，`is_oa` 共 3 个限定值；例如 `type=download`、`license=cc-by`、`is_oa=true`。 |
| `invalid_url` | URL 不合法 | 若URL 格式错误，则标记。 |

## access_is_oa

| Label 名 | 中文名称 | 标签含义 |
|---|---|---|
| `missing_field` | 字段缺失 | 检查输入对象中是否存在 `access_is_oa` 字段。 |
| `wrong_type` | 字段类型错误 | 值的类型不是字符串时标记。 |
| `empty` | 值为空 | 若论文开放获取标记为空，则标记。 |
| `unsupported_value` | 值不在限定范围内 | 值须属于 3 个限定值之一：`true`、`false`、`unknown`。 |
| `oa_status_mismatch` | OA 状态不一致 | `true` 时状态须为 `diamond`、`gold`、`green`、`hybrid` 或 `bronze`；`false` 时须为 `closed`；`unknown` 时须为空。 |
| `oa_url_mismatch` | OA URL 不一致 | `true` 时须至少包含一个有效 OA URL；`false` 或 `unknown` 时须为空数组。 |
| `license_mismatch` | 许可证不一致 | `false` 或 `unknown` 时 `access_license` 须为空；`true` 时允许为空或使用受支持的许可证值。 |

## access_oa_status

| Label 名 | 中文名称 | 标签含义 |
|---|---|---|
| `missing_field` | 字段缺失 | 检查输入对象中是否存在 `access_oa_status` 字段。 |
| `wrong_type` | 字段类型错误 | 值的类型不是字符串时标记。 |
| `null` | 值为 null | 检查字段值是否为 `null`。 |
| `unsupported_value` | 值不在限定范围内 | 值须属于 7 个限定值之一，例如 `diamond`、`gold`、`green`、`closed`，也允许空字符串。 |

## access_oa_url

| Label 名 | 中文名称 | 标签含义 |
|---|---|---|
| `missing_field` | 字段缺失 | 检查输入对象中是否存在 `access_oa_url` 字段。 |
| `wrong_type` | 字段类型错误 | 值不是字符串列表时标记。 |
| `null` | 值为 null | 检查字段值是否为 `null`。 |
| `invalid_url` | URL 不合法 | 若列表中存在无效 URL，则标记。 |

## access_license

| Label 名 | 中文名称 | 标签含义 |
|---|---|---|
| `missing_field` | 字段缺失 | 检查输入对象中是否存在 `access_license` 字段。 |
| `wrong_type` | 字段类型错误 | 值的类型不是字符串时标记。 |
| `null` | 值为 null | 检查字段值是否为 `null`。 |
| `unsupported_value` | 值不在限定范围内 | 值须属于 27 个限定值之一，例如 `cc-by`、`cc0`、`mit`、`public-domain`，也允许空字符串。 |

## publication_published_date

| Label 名 | 中文名称 | 标签含义 |
|---|---|---|
| `missing_field` | 字段缺失 | 检查输入对象中是否存在 `publication_published_date` 字段。 |
| `wrong_type` | 字段类型错误 | 值的类型不是字符串时标记。 |
| `null` | 值为 null | 检查字段值是否为 `null`。 |
| `invalid_format` | 格式不符合要求 | 若不符合 YYYY-MM-DD 格式，则标记。 |
| `invalid_date` | 日期不合法 | 若不是有效日历日期，则标记。 |

## publication_published_year

| Label 名 | 中文名称 | 标签含义 |
|---|---|---|
| `missing_field` | 字段缺失 | 检查输入对象中是否存在 `publication_published_year` 字段。 |
| `wrong_type` | 字段类型错误 | 值的类型不是整数时标记。 |
| `out_of_range` | 数值超出有效范围 | 若年份超出有效范围，则标记。 |

## publication_venue_issn

| Label 名 | 中文名称 | 标签含义 |
|---|---|---|
| `missing_field` | 字段缺失 | 检查输入对象中是否存在 `publication_venue_issn` 字段。 |
| `wrong_type` | 字段类型错误 | 值不是字符串列表时标记。 |
| `null` | 值为 null | 检查字段值是否为 `null`。 |
| `invalid_format` | 格式不符合要求 | 若ISSN 格式或校验位错误，则标记。 |

## publication_venue_biblio_volume

| Label 名 | 中文名称 | 标签含义 |
|---|---|---|
| `missing_field` | 字段缺失 | 检查输入对象中是否存在 `publication_venue_biblio_volume` 字段。 |
| `wrong_type` | 字段类型错误 | 值的类型不是字符串时标记。 |
| `null` | 值为 null | 检查字段值是否为 `null`。 |
| `invalid_format` | 格式不符合要求 | 若值不能转换为整数，则标记。 |

## publication_venue_biblio_issue

| Label 名 | 中文名称 | 标签含义 |
|---|---|---|
| `missing_field` | 字段缺失 | 检查输入对象中是否存在 `publication_venue_biblio_issue` 字段。 |
| `wrong_type` | 字段类型错误 | 值的类型不是字符串时标记。 |
| `null` | 值为 null | 检查字段值是否为 `null`。 |
| `invalid_format` | 格式不符合要求 | 若值不能转换为整数，则标记。 |

## publication_venue_biblio_pages

| Label 名 | 中文名称 | 标签含义 |
|---|---|---|
| `missing_field` | 字段缺失 | 检查输入对象中是否存在 `publication_venue_biblio_pages` 字段。 |
| `wrong_type` | 字段类型错误 | 值的类型不是字符串时标记。 |
| `null` | 值为 null | 检查字段值是否为 `null`。 |
| `invalid_format` | 格式不符合要求 | 若不符合 `<起始页>-<结束页>` 格式，则标记。 |
| `out_of_range` | 数值超出有效范围 | 若页码不是正数，则标记。 |
| `page_order` | 页码顺序错误 | 若起始页大于结束页，则标记。 |

## publication_pages

| Label 名 | 中文名称 | 标签含义 |
|---|---|---|
| `missing_field` | 字段缺失 | 检查输入对象中是否存在 `publication_pages` 字段。 |
| `wrong_type` | 字段类型错误 | 值的类型不是整数时标记。 |
| `out_of_range` | 数值超出有效范围 | 若页数不大于 0，则标记。 |

## publication_venue_name_unified

| Label 名 | 中文名称 | 标签含义 |
|---|---|---|
| `missing_field` | 字段缺失 | 检查输入对象中是否存在 `publication_venue_name_unified` 字段。 |
| `wrong_type` | 字段类型错误 | 检查当前字段及其依赖字段的类型是否符合要求。 |
| `null` | 值为 null | 检查字段值是否为 `null`。 |
| `missing_dependency` | 缺少依赖字段 | 若缺少期刊原始名称，无法校验，则标记。 |
| `mismatch` | 值与预期不一致 | 若与预期统一名称不一致，则标记。 |

## grade_class

| Label 名 | 中文名称 | 标签含义 |
|---|---|---|
| `missing_field` | 字段缺失 | 检查输入对象中是否存在 `grade_class` 字段。 |
| `wrong_type` | 字段类型错误 | 值的类型不是字符串时标记。 |
| `null` | 值为 null | 检查字段值是否为 `null`。 |
| `unsupported_value` | 值不在限定范围内 | 值须属于 5 个限定值之一：`k12`、`higher-edu`、`vocational-edu`、`other` 或空字符串。 |

## grade

| Label 名 | 中文名称 | 标签含义 |
|---|---|---|
| `missing_field` | 字段缺失 | 检查输入对象中是否存在 `grade` 字段。 |
| `wrong_type` | 字段类型错误 | 检查当前字段与 `grade_class` 是否均为字符串。 |
| `null` | 值为 null | 检查字段值是否为 `null`。 |
| `unsupported_value` | 值不在限定范围内 | 值须属于 4 个限定值之一：`小学`、`初中`、`高中` 或空字符串。 |
| `grade_mismatch` | 年级与教育类型不匹配 | 若非 K12 类型设置了年级，则标记。 |

## references

| Label 名 | 中文名称 | 标签含义 |
|---|---|---|
| `missing_field` | 字段缺失 | 检查输入对象中是否存在 `references` 字段。 |
| `wrong_type` | 字段类型错误 | 检查值是否为列表，并逐项检查列表项类型。 |
| `null` | 值为 null | 检查字段值是否为 `null`。 |
| `empty` | 值为空 | 若`id_type` 或非 DOI 标识符为空，则标记。 |
| `invalid_keys` | key 不符合要求 | 若列表项字段不符合要求，则标记。 |
| `title_null` | 标题为 null | 检查列表项中的 `title` 是否为 `null`。 |
| `title_wrong_type` | 标题类型错误 | 列表项中的 `title` 不是字符串时标记。 |
| `title_html_tag_layout` | 标题包含 HTML 排版标签 | 列表项的 `title` 包含 HTML 排版标签，如 `<i>`、`<b>`、`<p>`、`<br>`、`<sup>`、`<sub>`、`<em>`、`<strong>`、`<span>`、`<div>`、`<u>`、`<scp>`、`<tt>`。 |
| `title_html_tag_math` | 标题包含 MathML 标签 | 列表项的 `title` 包含 MathML 标签，如 `<math>`、`<mrow>`、`<mi>`、`<mn>`、`<mo>`、`<msub>`、`<mfrac>`、`<msqrt>` 等，也匹配 `mml:` 前缀。 |
| `title_html_tag_xml_comment` | 标题包含 XML 注释 | 列表项的 `title` 包含 XML/HTML 注释片段，如 `<!-- comment -->`。 |
| `title_html_tag_cdata` | 标题包含 CDATA 内容 | 列表项的 `title` 包含 CDATA 区段，如 `<![CDATA[...]]>`。 |
| `title_html_entity_named` | 标题包含命名 HTML 实体 | 列表项的 `title` 包含 `&名称;` 形式的命名 HTML 实体，如 `&nbsp;`、`&amp;`。 |
| `title_html_entity_decimal` | 标题包含十进制 HTML 实体 | 列表项的 `title` 包含 `&#数字;` 形式的十进制 HTML 实体，如 `&#160;`。 |
| `title_html_entity_hex` | 标题包含十六进制 HTML 实体 | 列表项的 `title` 包含 `&#x十六进制;` 形式的 HTML 实体，如 `&#xA0;`。 |
| `title_special_char_invisible` | 标题包含不可见字符 | 列表项的 `title` 包含 U+2000～U+200F、U+202F、U+205F、U+3000、U+FEFF、U+00A0 或 U+2060～U+206F 中的字符。 |
| `title_special_char_replacement` | 标题包含 Unicode 替换字符 | 列表项的 `title` 包含 Unicode 替换字符 `�`（U+FFFD）。 |
| `title_special_char_control` | 标题包含控制字符 | 列表项的 `title` 包含 U+0000～U+0008、U+000B、U+000C、U+000E～U+001F 或 U+007F；TAB、换行和回车除外。 |
| `title_special_char_markup` | 标题包含方括号排版标记 | 列表项的 `title` 包含 `[!i]`、`[!/i]`、`[!sub]`、`[!/sup]`、`[!]`、`[○!R]`、`[○!上]`、`[○!下]` 等标记。 |
| `id_empty` | 标识符为空 | 若DOI 为空，则标记。 |
| `id_wrong_type` | 标识符类型错误 | 当标识符类型为 DOI 时，标识符值不是字符串则标记。 |
| `id_not_lowercase` | 标识符字母大小写不符合要求 | 若DOI 不是小写，则标记。 |
| `id_format_invalid` | 标识符格式不符合要求 | 若DOI 格式错误，则标记。 |
| `id_error_prefix` | 标识符前缀不符合要求 | 当标识符类型为 DOI 时，检查前缀是否命中 3 个测试前缀：`10.0000`、`10.0001`、`10.5555`。 |

## related_works

| Label 名 | 中文名称 | 标签含义 |
|---|---|---|
| `missing_field` | 字段缺失 | 检查输入对象中是否存在 `related_works` 字段。 |
| `wrong_type` | 字段类型错误 | 检查值是否为列表，并逐项检查列表项类型。 |
| `null` | 值为 null | 检查字段值是否为 `null`。 |
| `empty` | 值为空 | 若`id_type` 或非 DOI 标识符为空，则标记。 |
| `invalid_keys` | key 不符合要求 | 若列表项字段不符合要求，则标记。 |
| `title_null` | 标题为 null | 检查列表项中的 `title` 是否为 `null`。 |
| `title_wrong_type` | 标题类型错误 | 列表项中的 `title` 不是字符串时标记。 |
| `title_html_tag_layout` | 标题包含 HTML 排版标签 | 列表项的 `title` 包含 HTML 排版标签，如 `<i>`、`<b>`、`<p>`、`<br>`、`<sup>`、`<sub>`、`<em>`、`<strong>`、`<span>`、`<div>`、`<u>`、`<scp>`、`<tt>`。 |
| `title_html_tag_math` | 标题包含 MathML 标签 | 列表项的 `title` 包含 MathML 标签，如 `<math>`、`<mrow>`、`<mi>`、`<mn>`、`<mo>`、`<msub>`、`<mfrac>`、`<msqrt>` 等，也匹配 `mml:` 前缀。 |
| `title_html_tag_xml_comment` | 标题包含 XML 注释 | 列表项的 `title` 包含 XML/HTML 注释片段，如 `<!-- comment -->`。 |
| `title_html_tag_cdata` | 标题包含 CDATA 内容 | 列表项的 `title` 包含 CDATA 区段，如 `<![CDATA[...]]>`。 |
| `title_html_entity_named` | 标题包含命名 HTML 实体 | 列表项的 `title` 包含 `&名称;` 形式的命名 HTML 实体，如 `&nbsp;`、`&amp;`。 |
| `title_html_entity_decimal` | 标题包含十进制 HTML 实体 | 列表项的 `title` 包含 `&#数字;` 形式的十进制 HTML 实体，如 `&#160;`。 |
| `title_html_entity_hex` | 标题包含十六进制 HTML 实体 | 列表项的 `title` 包含 `&#x十六进制;` 形式的 HTML 实体，如 `&#xA0;`。 |
| `title_special_char_invisible` | 标题包含不可见字符 | 列表项的 `title` 包含 U+2000～U+200F、U+202F、U+205F、U+3000、U+FEFF、U+00A0 或 U+2060～U+206F 中的字符。 |
| `title_special_char_replacement` | 标题包含 Unicode 替换字符 | 列表项的 `title` 包含 Unicode 替换字符 `�`（U+FFFD）。 |
| `title_special_char_control` | 标题包含控制字符 | 列表项的 `title` 包含 U+0000～U+0008、U+000B、U+000C、U+000E～U+001F 或 U+007F；TAB、换行和回车除外。 |
| `title_special_char_markup` | 标题包含方括号排版标记 | 列表项的 `title` 包含 `[!i]`、`[!/i]`、`[!sub]`、`[!/sup]`、`[!]`、`[○!R]`、`[○!上]`、`[○!下]` 等标记。 |
| `id_empty` | 标识符为空 | 若DOI 为空，则标记。 |
| `id_wrong_type` | 标识符类型错误 | 当标识符类型为 DOI 时，标识符值不是字符串则标记。 |
| `id_not_lowercase` | 标识符字母大小写不符合要求 | 若DOI 不是小写，则标记。 |
| `id_format_invalid` | 标识符格式不符合要求 | 若DOI 格式错误，则标记。 |
| `id_error_prefix` | 标识符前缀不符合要求 | 当标识符类型为 DOI 时，检查前缀是否命中 3 个测试前缀：`10.0000`、`10.0001`、`10.5555`。 |

## citations

| Label 名 | 中文名称 | 标签含义 |
|---|---|---|
| `missing_field` | 字段缺失 | 检查输入对象中是否存在 `citations` 字段。 |
| `wrong_type` | 字段类型错误 | 检查值是否为列表，并逐项检查列表项类型。 |
| `null` | 值为 null | 检查字段值是否为 `null`。 |
| `empty` | 值为空 | 若`id_type` 或非 DOI 标识符为空，则标记。 |
| `invalid_keys` | key 不符合要求 | 若列表项字段不符合要求，则标记。 |
| `title_null` | 标题为 null | 检查列表项中的 `title` 是否为 `null`。 |
| `title_wrong_type` | 标题类型错误 | 列表项中的 `title` 不是字符串时标记。 |
| `title_html_tag_layout` | 标题包含 HTML 排版标签 | 列表项的 `title` 包含 HTML 排版标签，如 `<i>`、`<b>`、`<p>`、`<br>`、`<sup>`、`<sub>`、`<em>`、`<strong>`、`<span>`、`<div>`、`<u>`、`<scp>`、`<tt>`。 |
| `title_html_tag_math` | 标题包含 MathML 标签 | 列表项的 `title` 包含 MathML 标签，如 `<math>`、`<mrow>`、`<mi>`、`<mn>`、`<mo>`、`<msub>`、`<mfrac>`、`<msqrt>` 等，也匹配 `mml:` 前缀。 |
| `title_html_tag_xml_comment` | 标题包含 XML 注释 | 列表项的 `title` 包含 XML/HTML 注释片段，如 `<!-- comment -->`。 |
| `title_html_tag_cdata` | 标题包含 CDATA 内容 | 列表项的 `title` 包含 CDATA 区段，如 `<![CDATA[...]]>`。 |
| `title_html_entity_named` | 标题包含命名 HTML 实体 | 列表项的 `title` 包含 `&名称;` 形式的命名 HTML 实体，如 `&nbsp;`、`&amp;`。 |
| `title_html_entity_decimal` | 标题包含十进制 HTML 实体 | 列表项的 `title` 包含 `&#数字;` 形式的十进制 HTML 实体，如 `&#160;`。 |
| `title_html_entity_hex` | 标题包含十六进制 HTML 实体 | 列表项的 `title` 包含 `&#x十六进制;` 形式的 HTML 实体，如 `&#xA0;`。 |
| `title_special_char_invisible` | 标题包含不可见字符 | 列表项的 `title` 包含 U+2000～U+200F、U+202F、U+205F、U+3000、U+FEFF、U+00A0 或 U+2060～U+206F 中的字符。 |
| `title_special_char_replacement` | 标题包含 Unicode 替换字符 | 列表项的 `title` 包含 Unicode 替换字符 `�`（U+FFFD）。 |
| `title_special_char_control` | 标题包含控制字符 | 列表项的 `title` 包含 U+0000～U+0008、U+000B、U+000C、U+000E～U+001F 或 U+007F；TAB、换行和回车除外。 |
| `title_special_char_markup` | 标题包含方括号排版标记 | 列表项的 `title` 包含 `[!i]`、`[!/i]`、`[!sub]`、`[!/sup]`、`[!]`、`[○!R]`、`[○!上]`、`[○!下]` 等标记。 |
| `id_empty` | 标识符为空 | 若DOI 为空，则标记。 |
| `id_wrong_type` | 标识符类型错误 | 当标识符类型为 DOI 时，标识符值不是字符串则标记。 |
| `id_not_lowercase` | 标识符字母大小写不符合要求 | 若DOI 不是小写，则标记。 |
| `id_format_invalid` | 标识符格式不符合要求 | 若DOI 格式错误，则标记。 |
| `id_error_prefix` | 标识符前缀不符合要求 | 当标识符类型为 DOI 时，检查前缀是否命中 3 个测试前缀：`10.0000`、`10.0001`、`10.5555`。 |

## supplementary_material

| Label 名 | 中文名称 | 标签含义 |
|---|---|---|
| `missing_field` | 字段缺失 | 检查输入对象中是否存在 `supplementary_material` 字段。 |
| `wrong_type` | 字段类型错误 | 检查值是否为列表，并逐项检查列表项及其属性类型。 |
| `null` | 值为 null | 检查字段值是否为 `null`。 |
| `invalid_keys` | key 不符合要求 | 若列表项字段不符合要求，则标记。 |

## cited_by_api_url

| Label 名 | 中文名称 | 标签含义 |
|---|---|---|
| `missing_field` | 字段缺失 | 检查输入对象中是否存在 `cited_by_api_url` 字段。 |
| `wrong_type` | 字段类型错误 | 值的类型不是字符串时标记。 |
| `null` | 值为 null | 检查字段值是否为 `null`。 |
| `invalid_url` | URL 不合法 | 若URL 格式错误，则标记。 |

## access_xinghe_repository_sha256

| Label 名 | 中文名称 | 标签含义 |
|---|---|---|
| `missing_field` | 字段缺失 | 检查输入对象中是否存在 `access_xinghe_repository_sha256` 字段。 |
| `wrong_type` | 字段类型错误 | 检查当前字段的类型，并检查相关全文状态标记的类型。 |
| `null` | 值为 null | 检查字段值是否为 `null`。 |
| `required` | 必填值为空 | `access_xinghe_repository_has_fulltext=true` 时，SHA256 是空字符串或空列表；当前实现不校验十六进制长度或摘要格式。 |

## access_xinghe_repository_origin_path

| Label 名 | 中文名称 | 标签含义 |
|---|---|---|
| `missing_field` | 字段缺失 | 检查输入对象中是否存在 `access_xinghe_repository_origin_path` 字段。 |
| `wrong_type` | 字段类型错误 | 检查当前字段的类型，并检查相关全文状态标记的类型。 |
| `required` | 必填值为空 | 若存在全文时原始路径不能为空，则标记。 |

## access_xinghe_repository_model_name

| Label 名 | 中文名称 | 标签含义 |
|---|---|---|
| `missing_field` | 字段缺失 | 检查输入对象中是否存在 `access_xinghe_repository_model_name` 字段。 |
| `wrong_type` | 字段类型错误 | 值的类型不是字符串时标记。 |
| `required` | 必填值为空 | 若处理成功时模型名称不能为空，则标记。 |
| `unsupported_value` | 值不在限定范围内 | 值须属于 2 个限定值之一：`mineru`、`llm-web-kit`。 |

## access_xinghe_repository_model_version

| Label 名 | 中文名称 | 标签含义 |
|---|---|---|
| `missing_field` | 字段缺失 | 检查输入对象中是否存在 `access_xinghe_repository_model_version` 字段。 |
| `wrong_type` | 字段类型错误 | 值的类型不是字符串时标记。 |
| `required` | 必填值为空 | 若当前条件下模型版本不能为空，则标记。 |
| `unsupported_value` | 值不在限定范围内 | 值须属于 4 个限定值之一：`1.3.1`、`2`、`2.5`、`4.1.1`。 |
| `model_mismatch` | 模型版本与模型名称不匹配 | `mineru` 只允许 `1.3.1`、`2`、`2.5`，`llm-web-kit` 只允许 `4.1.1`。 |
