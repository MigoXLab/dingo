# Artimuse 图像质量评估规则

## 概述

在介绍规则之前，先简要说明 ArtiMuse：

ArtiMuse 是一个面向图像美学质量评估（Image Aesthetics Assessment, IAA）的在线模型/服务，能够输出整体美学分数并提供细粒度、可解释的评估信息，适用于作品筛选、内容推荐等场景。论文：[ArtiMuse: Fine-Grained Image Aesthetics Assessment with Joint Scoring and Expert-Level Understanding](https://arxiv.org/abs/2507.14533)。

RuleImageArtimuse 基于 ArtiMuse 在线服务对输入图片进行美学质量评估。规则会创建评估任务并轮询状态，取得总体分数及服务端返回的细粒度信息；随后与阈值比较，给出 Good/Bad 判定，并在结果中回传完整的可解释信息。

本文档的测试图片均由 Google Gemini 2.5 Flash Image（社区常称 “nano‑banana”）按提示词生成，后经人工筛选整理并托管在 OpenXLab；完整清单见 [test/data/artimuse/test_artimuse_nano_banana.jsonl](../test/data/artimuse/test_artimuse_nano_banana.jsonl)。我们将这批样例汇总为迷你集合 nano_banana，覆盖人像、室内、产品、电商、插画等多种风格，便于快速复现。

在仓库根目录运行 `python examples/artimuse/artimuse.py`（[examples/artimuse/artimuse.py](../examples/artimuse/artimuse.py)）可完成评估；如设置 `output_path`，将在该目录生成带时间戳与短 ID 的子目录，包含 `summary.json` 与逐条明细。可用 `python -m dingo.run.vsl --input <输出目录>` 打开可视化页面。

我们的判定是基于 `data.score_overall` 与阈值 `threshold`的，如果低于阈值那么就是 BadImage，否则为 GoodImage；服务端 `data` 原样写入 `reason[0]` 便于溯源。并且，结合 nano_banana 的样例，低分多见于贴纸或合成画面写实性不足、Logo/文字遮挡主体、风格迁移过强导致色彩与细节失真、截图噪声多而缺乏摄影要素、纯 Logo 缺少摄影主体、以及过度后期造成的不自然等情况；应尽量突出主体、控制曝光与清晰度、减少压缩与过重滤镜、移除干扰元素，并保持整体风格一致。



## 规则配置

- **规则名称**: `QUALITY_BAD_IMG_ARTIMUSE`
- **阈值配置**: 范围 0 - 10，默认阈值为 6 分（可配置）
- **API 端点**: `https://artimuse.intern-ai.org.cn/`

## 核心方法

### `eval(cls, input_data: Data) -> ModelRes`

这是规则的主要评估方法，接收包含图像 URL 的 `Data` 对象，返回评估结果。

#### 参数
- `input_data`: 包含图像 URL 的 Data 对象
  - `data_id`: 数据标识符
  - `content`: 图像的网络 URL（本规则仅读取该字段）

#### 处理流程

1. **创建评估任务**
   - 向 ArtiMuse 接口 POST `{refer_path}/api/v1/task/create_task`
   - 请求体包含图片地址，内部固定 `style=1`

2. **获取任务状态**
   - 先等待 5 秒
   - 之后每 5 秒 POST `{refer_path}/api/v1/task/status` 查询一次，直到 `phase == "Succeeded"`
   - 代码未设置请求超时，也未限制最大轮询次数

3. **返回评估结果**
   - 读取 `score_overall` 与阈值比较，低于阈值判定为 `BadImage`，否则为 `GoodImage`
   - 将服务端返回的 `data` 以字符串化 JSON 放入 `reason`

#### 返回值

返回 `ModelRes` 对象，包含以下属性：

- `error_status`: 布尔值，表示图像质量是否不合格（低于阈值）
- `type`: 评估结果类型（"Artimuse_Succeeded" 或 "Artimuse_Fail"）
- `name`: 评估结果名称（"BadImage" 或 "GoodImage" 或 "Exception"）
- `reason`: 包含详细评估信息或异常信息的数组（字符串化 JSON）

## 异常处理

当评估过程中发生异常时，返回的 `ModelRes` 对象将包含：

- `error_status`: `False`
- `type`: `"Artimuse_Fail"`
- `name`: `"Exception"`
- `reason`: 包含异常信息的数组

## 使用示例

```python
# 创建测试数据
data = Data(
    data_id='1',
    content="https://example.com/image.jpg"
)

# 执行评估
res = RuleImageArtimuse.eval(data)

# 输出结果
print(res)
```

## 依赖项

- `requests`: 用于发送 HTTP 请求
- `time`: 用于控制请求间隔
- `json`: 用于处理返回的 JSON 数据

## 注意事项

1. 确保提供的图像 URL 可公开访问（避免鉴权、重定向或短链失效）
2. 首次查询前等待 5 秒，之后每 5 秒轮询一次；总耗时取决于服务端完成时间
3. 阈值与接口端点可通过 `dynamic_config` 调整：`threshold` 与 `refer_path`

## 错误排查

如果评估失败，可能的原因包括：

1. 网络连接问题
2. ArtiMuse 服务不可用
3. 图像 URL 不可访问
4. 服务端长时间无响应或不可达

建议在使用前确保网络环境稳定，并验证图像 URL 的有效性。
