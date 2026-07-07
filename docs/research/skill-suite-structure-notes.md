# Skill Suite 目录结构调研笔记

## 结论

Starlane Skills 第一版采用单 skill 内聚结构，正式 skill 只放一个：

```text
skills/
└── starlane-regression/
    ├── references/
    └── scripts/
```

暂不引入 `user/`、`empirical/`、`in-progress/`、`deprecated/` 等分类层，也暂不拆 `starlane-design`、`starlane-runner`、`starlane-interpretation`。

理由：当前第一版只要跑通一个深、窄、边界清楚的 regression delivery workflow。过早拆多个 skill 或 `_shared` 会让入口、共享契约和责任边界变复杂。先把 `starlane-regression` 讲完整，等第二个稳定 skill 出现并产生真实重复后再抽共享规范。

## 参考项目

### mattpocock/skills

`mattpocock/skills` 使用分组结构：

```text
skills/
├── engineering/
├── productivity/
├── misc/
├── in-progress/
└── deprecated/
```

优点：

- 适合几十个 skill 的长期维护。
- 能区分工程、生产力、杂项、实验中、已弃用等状态。
- 方便维护用户入口 skill 和模型自动调用 skill 的关系。
- 适合配合 router、changeset、docs 镜像、ADR 等治理机制。

缺点：

- 初期偏重。
- 分类稳定前容易反复移动目录。
- 用户查找和安装路径更深。

它的关键经验不是“目录一定要分组”，而是治理纪律：

- 行为变化用小 PR。
- 新增、改名、删除 skill 后同步 README、docs、router。
- 实验中和已弃用 skill 不混入正式区。
- 共享规则放到单一事实来源，避免重复。

### nature-skills

`nature-skills` 更接近平展结构：

```text
skills/
├── _shared/
├── nature-...
├── nature-...
└── nature-...
```

优点：

- 打开即懂。
- 每个顶层 skill 目录就是一个清晰安装单元。
- 适合主题明确的垂直 skill suite。
- 适合早期快速迭代。

缺点：

- skill 数量变多后会拥挤。
- 很难仅靠目录表达入口、内部能力、实验状态、弃用状态。
- 后续跨领域扩展时需要再分组。

它的关键经验是：

- 用统一前缀维持识别度。
- 当多个 skill 真的复用同一规范时，可以保留 `_shared` 管理共享规范。
- 不在早期引入过深目录。

## 对 Starlane 的取舍

Starlane 第一版应学习 nature-skills 的目录形态，学习 mattpocock/skills 的维护纪律。

当前正式结构：

```text
starlane-skills/
├── README.md
├── docs/
│   └── research/
├── scripts/
│   └── stata-code-examples/
└── skills/
    └── starlane-regression/
        ├── references/
        └── scripts/
```

具体职责：

- `skills/starlane-regression/`：唯一正式 skill，处理 regression delivery workflow。
- `skills/starlane-regression/references/`：保存该 skill 的输入输出契约、实证 section schema、支持方法、工作流契约、伦理边界、模型选择和排错说明。
- `skills/starlane-regression/scripts/`：保存 agent workflow 可调用的后端脚本。
- `scripts/stata-code-examples/`：保存给人看的 Stata 展示示例，不属于任何 skill workflow。
- `docs/research/`：保存调研、设计取舍和未来演进笔记。

第一版不加：

- `skills/starlane/`
- `skills/starlane-design/`
- `skills/starlane-runner/`
- `skills/starlane-interpretation/`
- `skills/user/`
- `skills/empirical/`
- `skills/in-progress/`
- `skills/deprecated/`

这些目录等 skill 数量、领域范围、发布状态真的复杂后再引入。

## 命名规则

当前采用分层命名规则：

人类可读的项目资产使用 kebab-case：

- 目录名使用 kebab-case。
- Markdown 文件使用 kebab-case。
- Skill 名使用 `starlane-*`。

机器接口和代码资产使用 snake_case：

- Python、Stata 等可执行脚本使用 snake_case。
- 生成的 CSV、临时文件和机器读取产物使用 snake_case。
- CSV 字段、参数名、变量名使用 snake_case。

例外：

- `README.md` 和 `SKILL.md` 使用生态约定的大写文件名。

目录职责：

- 当前正式规范放在 `skills/starlane-regression/references/`。
- Skill 内运行脚本放在 `skills/<skill-name>/scripts/`。
- 根目录 `scripts/` 只放非 workflow 的展示、辅助或维护资产；具体目录必须自带 README 声明用途。

## 演进条件

当出现以下情况时，再考虑升级到分组结构：

- 顶层正式 skill 超过 8 个。
- 出现实证分析之外的稳定领域，如文献综述、论文写作、科研绘图。
- 有多个实验中 skill 需要隔离。
- 有弃用 skill 仍需保留兼容。
- 用户入口和内部能力的关系需要更强的目录表达。

升级后的可能结构：

```text
skills/
├── _shared/
├── empirical/
├── writing/
├── literature/
├── in-progress/
└── deprecated/
```
