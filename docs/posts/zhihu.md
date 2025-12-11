# 文案一
[Dingo：面向AI时代的全方位数据质量评估工具](https://zhuanlan.zhihu.com/p/1892338512306602995)
# 文案二
[Dingo MCP来了！在Cursor中轻松玩转AI数据评估，效率翻倍！](https://zhuanlan.zhihu.com/p/1910428406631359769)
# 文案三
# 🚀 Dingo 1.9.0 重磅发布：基于RAG的幻觉数据质量评估新标杆


## 📢 重大更新预告

经过团队数日的精心打磨，**Dingo 1.9.0** 正式发布！这次更新不仅仅是版本号的跃升，更是对**RAG**（检索增强生成）时代数据质量评估需求的深度回应。

**🌟 项目地址**：https://github.com/MigoXLab/dingo

## 🎯 三大核心突破

### 1️⃣ 基于RAG检索的幻觉检测 🔍

- **智能检索增强**：结合知识库检索，不再依赖静态规则
- **上下文感知**：动态理解文档语境，精准识别事实性错误
- **多模态支持**：文本、图像、表格全方位幻觉检测
- **实时验证**：支持在线API调用，确保信息时效性

```python
# 新的RAG幻觉检测使用示例
from dingo.model.rag import RAGHallucinationDetector

detector = RAGHallucinationDetector(
    knowledge_base="your_vector_db",
    retrieval_method="dense_passage"
)

result = detector.evaluate(
    query="爱因斯坦何时获得诺贝尔奖？",
    answer="爱因斯坦在1969年获得诺贝尔奖",
    retrieved_context=["爱因斯坦1921年获得诺贝尔物理学奖..."]
)
# 输出：{"hallucination_score": 0.95, "evidence": "时间错误"}
```

### 2️⃣ 配置系统深度重构 ⚙️
**让复杂配置变得简单优雅！**

- **层级化配置**：支持项目级、用户级、系统级配置继承
- **智能校验**：配置项自动验证，错误提示更友好
- **热重载**：配置修改即时生效，无需重启
- **模板化**：预置常用场景配置模板

```python
# 新的配置文件结构
input_data = {
    "executor": {
        "eval_group": "rag",  # 使用RAG评估组
    },
    "evaluator": {
        "rule_config": {
            "RuleHallucinationHHEM": {
                "threshold": 0.5  # 幻觉检测阈值
            }
        },
        "llm_config": {
            "LLMTextQualityPromptBase": {
                "model": "gpt-4o",
                "key": "YOUR_API_KEY",
                "api_url": "https://api.openai.com/v1/chat/completions"
            }
        }
    }
}
```

### 3️⃣ DeepWiki文档问答系统 📚
**让文档"活"起来，智能问答触手可及！**

- **深度理解**：基于最新的文档理解模型
- **多语言支持**：中文、英文文档无缝切换
- **上下文记忆**：支持多轮对话，理解问答历史
- **可视化导航**：智能文档结构解析和导航

**🌟 体验地址**: https://deepwiki.com/MigoXLab/dingo


## 💡 实际应用场景

### 场景一：RAG系统质量监控
```python
# 实时基于RAG监控回答质量（使用本地HHEM）
def monitor_rag_response(question, generated_answer, retrieved_docs):
    data = Data(
        data_id=f"rag_{timestamp}",
        prompt=question,
        content=generated_answer,
        context=retrieved_docs
    )

    result = RuleHallucinationHHEM.eval(data)  # 本地、快速、免费

    if result.error_status:
        logger.warning(f"检测到幻觉: {result.reason[0]}")
        # 触发人工审核或回答重生成
```

### 场景二：企业级RAG部署
```python
# 完整的企业级RAG系统（集成检索+生成+幻觉检测）
class RAGWithHallucinationDetection:
    def __init__(self, retriever, llm, hallucination_detector):
        self.retriever = retriever
        self.llm = llm
        self.detector = hallucination_detector
        # 预加载HHEM模型以提高性能
        self.detector.load_model()

    def generate_answer(self, question):
        # 1. 检索相关文档
        retrieved_docs = self.retriever.search(question, top_k=3)

        # 2. 生成回答
        context = "\n".join(retrieved_docs)
        generated_answer = self.llm.generate(f"基于以下文档回答问题:\n{context}\n\n问题: {question}")

        # 3. 幻觉检测
        data = Data(prompt=question, content=generated_answer, context=retrieved_docs)
        result = self.detector.eval(data)

        # 4. 根据检测结果返回
        if result.error_status:
            return {"answer": None, "warning": "检测到潜在幻觉，请人工审核"}
        else:
            return {"answer": generated_answer, "confidence": "high"}
```


## 📊 下载与使用

```bash
# 立即体验最新版本
pip install dingo-python==1.9.0

# 或从源码安装最新功能
git clone https://github.com/MigoXLab/dingo.git
cd dingo && git checkout v1.9.0
pip install -e .
```

## 🤝 参与贡献

Dingo的成长离不开社区的支持！欢迎：

- 🐛 **Bug反馈**：[GitHub Issues](https://github.com/MigoXLab/dingo/issues)
- 💡 **功能建议**：[讨论区](https://github.com/MigoXLab/dingo/discussions)
- 📝 **文档完善**：[贡献指南](https://github.com/MigoXLab/dingo/blob/main/CONTRIBUTING.md)
- ⭐ **点赞支持**：[GitHub Star](https://github.com/MigoXLab/dingo)



#数据质量 #RAG #人工智能 #开源项目 #机器学习 #大模型
