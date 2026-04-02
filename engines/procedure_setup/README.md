# Procedure Setup Engine

负责在正式推演前准备程序上下文。

当前目录用于承载：

- 庭前准备相关逻辑
- hearing order 等程序性生成
- 进入 `simulation_run` 前需要先确定的程序配置

它的职责是“把程序状态准备好”，不是直接生成案件结论。
