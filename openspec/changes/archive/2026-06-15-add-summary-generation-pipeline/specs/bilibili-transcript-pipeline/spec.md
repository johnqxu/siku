## MODIFIED Requirements

### Requirement: Bilibili transcript pipeline 入口
系统 SHALL 为 `bilibili_video` 来源提供 Bilibili 视频到规范文本的处理 pipeline，并在规范文本生成后由当前 Python 确定性 pipeline 继续执行领域分类和中文总结。

#### Scenario: Bilibili 视频进入 transcript pipeline
- **WHEN** `km ingest` 请求通过本地状态层和 URL 路由，且路由结果为 `bilibili_video`
- **THEN** 系统执行 Bilibili transcript pipeline，而不是返回 `NOT_IMPLEMENTED`

#### Scenario: transcript 成功后进入领域分类
- **WHEN** Bilibili transcript pipeline 产出规范文本
- **THEN** 系统继续执行领域分类 pipeline

#### Scenario: 领域分类成功后进入中文总结
- **WHEN** Bilibili transcript pipeline 和领域分类 pipeline 均成功
- **THEN** 系统继续执行中文总结 pipeline，并在成功时返回 `summary_ready`

#### Scenario: pipeline 不执行更后续知识处理
- **WHEN** Bilibili transcript pipeline、领域分类 pipeline 和中文总结 pipeline 均成功
- **THEN** 系统 MUST NOT 执行 Obsidian 写入、SQLite `processed` 记录写入或 Deep Agents 端到端编排
