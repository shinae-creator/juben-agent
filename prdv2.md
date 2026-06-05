# 📄 产品需求文档 (PRD)：AI 短剧剧本全自动生成流水线 (精品 20 集可视化编剧看板版)

## 1. 全景架构
本项目旨在为专业编剧打造一个无需配置环境、无需接触终端命令行的网页端精品短剧生产台。
* **后端核心：** 声明式 Agent 矩阵（爆款策划 Agent -> 20集精炼分集架构师与评价 Agent -> 酒馆对白驱动引擎）。
* **前端展示：** 基于 Python `Streamlit` 框架快速渲染的 Web 页面。通过 `st.session_state` 保证编剧在网页上操作、微调时，数据绝对不丢失。

## 2. 核心编剧控场工作流 (Human-in-the-Loop)
为了让兼职编剧以最低的工作量绝对控场，系统在网页端设置两个核心卡点：
1. **卡点一（主线审定）：** AI 凭空构思出全剧宏观大纲后，在网页端文本域呈现，编剧可直接修改，点击确认。
2. **卡点二（20集黄金挂钩点与多维度量化评估审定）✨【体量修正】：** * AI 将故事精准切成 **20 集** 的极简卡点清单（严控节奏，杜绝百集短剧的注水拉扯）。
   * **每个卡点附带 4 个维度的量化评分（0-10分）**：`冲突烈度`、`爽感爆发度`、`悬念钩子度`、`情感共鸣度`。
   * 网页端以可视化进度条或数字标签形式展现。编剧只需快速下滑扫描这 20 集的数据大盘，针对评分较低的集数（如悬念不够、节奏平淡）进行就地文字微调，确认后放行。
3. **全放行阶段：** 编剧点击最终生成，系统在后台异步并发调用 LLM 输出对白，前端网页以打字机流式（Streaming）动态刷新剧本。

## 3. 前端界面布局（可视化剧本大盘）
* **左侧：** 题材输入、大纲审定区、20集卡点快速审定微调列表（带 4 维指标彩色条）。
* **右侧：** 剧本画布（流式打字机刷新、一键下载为 Word 兼容格式）。

## 4. 技术栈
* 前端 UI 与交互：`Streamlit` (全 Python 驱动的 Web 页面渲染)
* LLM 路由胶水：`LiteLLM` (支持流式传输 `stream=True`)
* 数据结构存储与校验：`Pydantic v2`（严格约束卡点文本与 4 维评估数据的 JSON Schema）。

## 5. 核心数据模型校验定义 (Pydantic Schema)
```python
from pydantic import BaseModel, Field
from typing import List

class EpisodeCard(BaseModel):
    episode_num: int = Field(..., description="集数 (1-20)")
    title: str = Field(..., description="本集暂定标题")
    summary: str = Field(..., description="本集核心剧情概要，要求节奏极度紧凑")
    cliffhanger: str = Field(..., description="本集结尾的悬念留白/强力钩子")
    
    # 多维度评价模型
    conflict_intensity: int = Field(..., ge=0, le=10, description="冲突烈度评分 0-10")
    pleasure_index: int = Field(..., ge=0, le=10, description="爽感爆发度评分 0-10")
    hook_strength: int = Field(..., ge=0, le=10, description="悬念钩子度评分 0-10")
    emotional_resonance: int = Field(..., ge=0, le=10, description="情感共鸣度评分 0-10")