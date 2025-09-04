# Artimuse 图像质量评估规则

## 概述

RuleImageArtimuse 基于 ArtiMuse 服务，面向 AIGC 与创意生产的质量把关与可解释诊断。不同于只给分数或只给文本的方案，ArtiMuse 同时给出整体分与专家级细粒度理解。细粒度理解涵盖八个维度：构图设计、视觉元素、技术执行、想象创意、主题传达、情感反应、整体完形、综合评价。这样既能完成量化筛选，也能给出可直接落地的改进依据。

在我们的本地评估样例20250903_203109_deb630bc 中，整体得分为 75 分，Good 与 Bad 的比例约为七比三。维度解释显示技术执行、构图与视觉元素较为稳健，而想象创意往往是主要扣分来源。这与论文提出的联合评分和专家级理解目标一致：不仅判断好坏，更揭示原因，使结果可以反哺提示词、光线与叙事设置，形成生成、评估与再生成的闭环。

本规则默认阈值为 6 分，可根据业务目标微调。文字输出支持专业风格与批评性风格。推荐先使用专业风格做稳定评估与归因，再针对薄弱维度进行定向增强，从而持续提升整体美学质量。

## 规则配置

- 规则名称：`QUALITY_BAD_IMG_ARTIMUSE`
- 阈值配置：范围 0 到 10，默认 6 点，建议在 5.8 到 6.5 区间微调
- API 端点：`https://artimuse.intern-ai.org.cn/`
- 风格参数：`style=1` 表示专业风格，推荐使用；`style=2` 表示批评性风格
- 超时与轮询：创建任务超时 30 秒；最多轮询 5 次，每次间隔 2 秒；以上均可通过 dynamic_config 覆盖

## 核心方法

### `eval(cls, input_data: Data) -> ModelRes`

该方法对单张公网可访问的图像 URL 发起评估任务，通过轮询获取整体分与八维解释，并与阈值比较后返回统一结构的结果。

#### 参数
- `input_data: Data`
  - `data_id`：样本唯一标识
  - `content`：图像的公网 URL，必须可直接访问
- 可选动态配置 `dynamic_config`
  - `threshold`：浮点数，默认 6.0
  - `style`：整数，1 表示专业风格，2 表示批评性风格
  - `create_timeout_sec`：整数，默认 30
  - `poll_max_tries`：整数，默认 5
  - `poll_interval_sec`：浮点数，默认 2.0

#### 处理流程

1. 创建评估任务：向 ArtiMuse 发送包含 URL 与 style 的请求，创建阶段超时 30 秒
2. 轮询任务状态：先等待 2 秒，再按固定间隔轮询，最多 5 次；状态为 `Succeeded` 时获取结果
3. 结果判定与封装：读取 `score_overall`，按阈值判断 Good 或 Bad；同时携带八维解释与子分，封装为 `ModelRes` 返回

#### 返回值

返回 `ModelRes`，关键字段如下：

- `error_status`：布尔值，True 表示不合格低于阈值，False 表示合格达到阈值
- `type`：`Artimuse_Succeeded` 或 `Artimuse_Fail`
- `name`：`BadImage`、`GoodImage` 或 `Exception`
- `reason`：列表，通常只含一条，内含以下信息
  - `id`：任务或样本标识
  - `phase`：`Succeeded`
  - `image_url`：原图地址
  - `aspects`：八个维度的中文名、解释文本与子分
    - `composition_design`
    - `visual_elements`
    - `technical_execution`
    - `originality_creativity`
    - `theme_communication`
    - `emotional_impact`
    - `overall_gestalt`
    - `comprehensive_evaluation`
  - `score_overall`：整体分，范围 0 到 10
  - `style`：整数，1 或 2

常见消费方式：用 `score_overall` 与阈值做通过或拦截；同时抽取 `aspects` 的文字解释，尤其原创性、主题与情感，用于下一轮提示词与风格改写。

## 异常处理

创建或轮询出现异常、超时或始终未达 `Succeeded` 时，返回：
- `error_status`：`False`，不直接拉闸，交由上层策略决定
- `type`：`Artimuse_Fail`
- `name`：`Exception`
- `reason`：包含异常信息的文本

建议在上层对 `Artimuse_Fail` 或 `Exception` 做重试或旁路，例如切换备用评估，或标记为待人工复核。

## 使用示例

```python
# 创建测试数据
data = Data(
    data_id="1",
    content="https://example.com/image.jpg"  # 必须可公网访问
)

# 可选：动态配置，覆盖默认值
# dynamic_config = {
#     "threshold": 6.0,
#     "style": 1,                 # 1 表示专业风格，2 表示批评性风格
#     "create_timeout_sec": 30,
#     "poll_max_tries": 5,
#     "poll_interval_sec": 2.0
# }

# 执行评估
res = RuleImageArtimuse.eval(data)

# 输出结果
print(res)
```

## 依赖项

- `requests`：HTTP 请求
- `time`：轮询与等待
- `json`：解析服务返回
- 如需批量可视化和浏览，可使用 `dingo/run/vsl.py` 提供的可视化流程

## 注意事项

1. 图像 URL 必须可公网访问，避免鉴权、重定向或短期失效
2. 批量任务建议在上层做并发限流与重试回退，避免触发服务端限流
3. 风格选择方面：style 为 1 的专业风格更适合流水线质控与对外呈现，style 为 2 的批评性风格适合内部严苛评审
4. 阈值经验方面：当前样例中 6.0 能稳定区分弱创意与可用作品，更强调原创与叙事时可上调到 6.5，更宽松时可下调到 5.8 到 6.0
5. 解释的二次利用建议：将 `aspects` 的文字反馈用于提示词与风格改写，重点强化原创性、主题传达与情感反应，同时保持镜头语言、光线与材质一致，避免超现实元素缺乏粘合而拉低整体完形与情感分
6. 可视化与复核：使用 `dingo/run/vsl.py` 浏览评估目录，快速定位低分样本与薄弱维度

## 错误排查

1. 创建任务失败或立即异常：检查 URL 可达性、是否重定向或受限、服务端点是否可用
2. 长时间没有 `Succeeded`：增大轮询次数或间隔，上层增加重试或旁路
3. 分数异常或解释缺失：检查分辨率与格式、跨域与访问权限，必要时更换图源重试
4. 集群限流或不稳定：在上层增加指数退避、熔断与降级策略，批量任务分批提交
