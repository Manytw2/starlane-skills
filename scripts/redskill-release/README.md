# Starlane Skills Red SkillHub 上传包

这是包含 `starlane-regression` 与 `starlane-data-cleaner` 的 Starlane Skills
聚合上传包。顶层入口会根据用户请求，将回归分析或数据清洗任务路由到相应的
子 skill。

## 包范围

由于 Red SkillHub 当前会按文件格式过滤上传内容，本包不是完整的本地可运行版 skill。

本包包含：

- `SKILL.md`
- `README.md`
- `skills/starlane-regression/` 的 `SKILL.md`、设计说明和 `references/`
- `skills/starlane-data-cleaner/` 的 `SKILL.md`、设计说明和 `references/`

本包不包含完整工作流所需的本地执行文件：

- `scripts/`
- `pyproject.toml`
- `uv.lock`
- Stata `.do` 文件
- 本地运行产物

使用本包时，Agent 可以读取相应工作流说明、引导回归模型设定或数据清洗计划，
并解释支持范围与研究选择。它不能被视为完整的本地执行包，不能直接完成完整的
本地回归或清洗运行链路。

## 完整安装方式

如需安装完整可运行版 skill，请使用源码仓库：

https://github.com/Manytw2/starlane-skills

完整仓库包含两个 skill 的本地执行所需工作流脚本、Python 项目文件、锁文件和
Stata 相关文件。
