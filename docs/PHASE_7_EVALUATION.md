# 阶段 7：评估

## 目标

评估客服回复的相关性和可信度：

- **Faithfulness**：回复中的结论是否被检索上下文支撑。
- **Hallucination Rate**：回复中无依据内容的比例。
- **Context Precision / Recall**：检索结果是否返回了合适上下文。
- **Answer Relevance**：回复是否真正回答用户问题。

---

## 设计决策

评估模块通过 `ragas_eval.py` 和 `deepeval_eval.py` 适配真实评估框架：

- 如果配置了 API key，可以调用 RAGAS / DeepEval。
- 如果没有 API key，则使用本地文本相似度、关键词召回和上下文覆盖率等简化指标。
- 评估依赖放在 `requirements/eval.txt`，不进入默认运行时依赖。

---

## 代码参考

- 统一评估入口：`src/evaluation/framework.py`
- RAGAS 适配器：`src/evaluation/ragas_eval.py`
- DeepEval 适配器：`src/evaluation/deepeval_eval.py`
- 评估脚本：`scripts/run_eval.py`

---

## 验证步骤

```bash
python scripts/run_eval.py
```

检查输出表格和 `evaluation/reports/` 中生成的 JSON 报告。
