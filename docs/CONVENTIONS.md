# Starlane Skills 命名公约

> 由 `AGENTS.md` 引用，是命名事实的唯一权威出处。本文件只描述命名标准（what），不含开发流程与动作指引（when/how）；后者属于 `AGENTS.md`。

## 原则

- 一个概念全项目只用一种拼写，跨 Python、Stata、JSON、section 标签、列 token 与文档保持一致。
- 变量与字段默认缩写，以 §5 词表为准，并在定义处注释全称。
- 一致性优先于个人偏好；与本公约冲突的旧命名一律向本公约看齐。
- 本公约完备自洽，不设例外。领域术语与库 API 的既定名（如 Stata `xtset` 的 `panelvar`、pyfixest 的 `vcov`）是规则的组成部分，在 §5 词表中直接规定，不作为对通则的豁免。

## 1. 文件与目录

| 对象 | 规则 | 示例 |
|---|---|---|
| 目录 / skill | kebab-case | `starlane-regression` |
| 库模块（被 import） | 按职责命名，snake_case：概念职责用名词，动作职责用动作名词短语 | `contracts.py`、`model_plan.py`、`plan_drift_check.py` |
| 可执行入口脚本 | 动词_对象（见 §2） | `run_stage.py`、`compile_plan.py` |
| Shell 脚本 | kebab-case，动词在前 | `clean-runtime.sh` |
| 产物文件 | 跨 env 同名同风格 | `final_result.docx`、`generated_regression.py` / `.do` |

- `envs/python/` 与 `envs/stata/` 的文件集应左右对称（同职责同名，仅扩展名不同）；无法对称时在 `docs/ARCHITECTURE.md` 说明。
- 定性以主要消费方式为准：主要被 import 的是库模块，附带 `main()` 调试入口不改变定性；祈使式"动词_对象"专属于可执行入口脚本，二者不混用。
- 库模块职责本身是动作时，用动作名词短语而非祈使式动词：`plan_drift_check.py` 而非 `verify_plan_drift.py`（参照 Django `validators.py`、pip `self_outdated_check.py` 的惯例）。

## 2. Stage 链路命名

流水线阶段（stage）以 `run_stage.py` 的子命令为准，当前为 `profile → compile → summary → final`。这四个词是 stage 的规范 token，在 CLI 子命令、`run.json` 的 `stage` 字段、日志与文档中统一拼写。

- stage 入口脚本命名为动词_对象，且必须原样包含所属 stage token，保证文档、命令与文件树可互查。例：`profile_data.py`、`compile_plan.py`、`build_summary.py` / `.do`、`generate_final_source.py`。
- 执行顺序不编码进文件名；顺序的唯一权威出处是 `run_stage.py` 的子命令注册。
- 每个 stage 入口的模块 docstring 必须声明输入与输出契约，格式如下：

```python
"""<stage> stage: <上游> → <下游>.

IN:  <输入物>   <说明>
OUT: <产物>     <说明>
"""
```

- 各 stage 的 IN→OUT 事实以其脚本 docstring 为唯一出处，不在本文件或其他文档复述；全局链路图见 `docs/ARCHITECTURE.md`。

## 3. 代码标识符（PEP 8）

| 类型 | 规则 | 示例 |
|---|---|---|
| 变量 / 函数 / 参数 / 模块 | snake_case | `build_model_plan`、`cv_idx` |
| 类 / dataclass | PascalCase | `RegressionSpec` |
| 模块级常量 | SCREAMING_SNAKE_CASE | `SUMMARY_FIXED_COLUMNS` |
| 私有成员 | 前导下划线 | `_extract_result` |

- 函数用动词开头，变量用名词。
- 变量、字段、参数默认缩写（§5）；函数与类可用较完整的词。
- 不遮蔽内置名，必要时加尾下划线（`vars_`）。
- 不用 `l`、`O`、`I` 作单字母名。

## 4. 修饰词与结构化 key

- 变换与变体修饰词一律前缀：`ln_x`、`alt_x`、`lag_x`、`std_x`；不用后缀式 `x_ln`。
- 结构化列名以 `__` 分隔字段，字段内用单 `_`。
- 列 token 的拼写必须等于其 section 标签。例：section `rob_alt_x` 对应列 `rob_alt_x__<y>__<var>`。

## 5. 缩写词表

变量、字段、参数默认缩写，贴合 Stata 长度限制（变量名 ≤ 32、global macro 名 ≤ 31）与计量惯例。下表是标识符拼写的权威规定，表内拼写即规范，优先于 §3 默认。约束：

1. 缩写必须登记于下表；一个概念对应一个缩写，全链路统一拼写。
2. 定义处（dataclass 字段、schema、Stata global 赋值）必须注释全称。
3. 未登记且非领域惯例的缩写，先补入本表或改用全称。

| 概念 | 缩写 | 说明 |
|---|---|---|
| control variables | `cv` | 控制变量；派生 `cv_fixed`、`cv_min_count`、`cv_idx` |
| variance estimator | `vce` / `vcov` | 库 API 参数名，按库原样：Stata `vce`、pyfixest `vcov` |
| instrumental variable | `iv` | |
| robustness | `rob` | 字段与 section 统一 `rob_*`（`rob_vars`、`rob_year_range`） |
| mediation | `med` | 字段 `meds`，section `med_*` |
| moderation | `mod` | 字段 `mods`，section `mod_*` |
| heterogeneity | `het` | `het_disc`、`het_disc_vals` |
| panel / time 变量 | `panelvar` / `timevar` | Stata `xtset` 术语，连写 |
| standard error / coefficient | `se` / `coef` | `coef_direction` |
| number of observations | `nobs` | |
| p 值 / R² | `p_value` / `r2` | |
| 前缀：对数 / 滞后 / 标准化 / 替换 / 交互 | `ln_` / `lag_` / `std_` / `alt_` / `inter_` | `ln_x`、`lag_x`、`std_x`、`alt_y`、`inter_x_mod` |
| index | `idx` | `cv_idx`、`vce_idx` |
| 数据输入路径 | `data_path` | 支持 dta/csv/xlsx |

## 6. 命名空间前缀

- 环境变量：`STARLANE_*`（大写），如 `STARLANE_EXPORT`、`STARLANE_TMP`。
- stdout 哨兵：`STARLANE_*:` 前缀。
- Stata global：`starlane_*`（小写）。

## 7. 跨语言与 Stata 长度约束

- 同一字段在 Python 与 Stata 使用同一名字，不维护两套拼写。
- Stata 硬限制：变量名 ≤ 32、global macro 名 ≤ 31；`starlane_` 前缀占 9 字符。
- 短名加前缀仍超限时，在 `stata_config.py` 的 `STATA_ARG_GLOBAL_NAMES` 登记更短别名，并同步 §5。
- 派生变量名须紧凑，例如用 `ln_{x}` 而非 `{x}_rob_ln_{x}`，避免拼入用户变量名后超长。
