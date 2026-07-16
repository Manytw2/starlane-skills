# Starlane Regression Red SkillHub 上传包

这是 `starlane-regression` 的 Red SkillHub 上传包。

## 包范围

由于 Red SkillHub 当前会按文件格式过滤上传内容，本包不是完整的本地可运行版 skill。

本包包含：

- `SKILL.md`
- `references/`

本包不包含完整工作流所需的本地执行文件：

- `scripts/`
- `pyproject.toml`
- `uv.lock`
- Stata `.do` 文件
- 本地运行产物

使用本包时，Agent 可以读取工作流说明、引导模型设定、解释支持的回归模块，并帮助分析研究选择。它不能被视为完整的本地执行包，不能直接完成完整的本地回归运行链路。

## 完整安装方式

如需安装完整可运行版 skill，请使用源码仓库：

https://github.com/Manytw2/starlane-skills

完整仓库包含本地执行所需的工作流脚本、Python 项目文件、锁文件和 Stata 相关文件。
