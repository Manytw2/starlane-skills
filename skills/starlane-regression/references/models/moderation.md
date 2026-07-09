# Module: Moderation

## Purpose

调节效应用来讨论核心解释变量的影响在什么条件下更强或更弱。

## When To Recommend

Recommend moderation when the data contain plausible condition variables, such as:

- ownership type
- overseas exposure
- media attention
- regional or institutional context
- firm characteristics that change the relationship strength

## Confirmation Wording

Use:

```text
调节效应里，... 可能影响 Attention 和绿色创新之间关系的强弱。我们可以把它作为调节变量。
```

Do not say:

```text
mods 是 ...
```

## Analysis Plan

Write confirmed values into:

- `moderation.enabled`
- `moderation.variables`

## Section Schema

Moderation tests interactions with continuous moderators.

| Block | Formula | Column | Records | Order |
| --- | --- | --- | --- | --- |
| Interaction | `y ~ std(x) * std(mod) + cv_selected` | `mod__{mod}__{y}__{x}` | interaction coefficient | `mod -> y -> x` |

Count:

```text
n_mods * n_y * n_x
```

## Regression Args

| Analysis plan field | Regression arg |
| --- | --- |
| `moderation.variables` | `mods` |

## Boundaries

Do not mix moderation with mechanism wording.

Moderation answers "when or for whom is the relationship stronger", not "through what path".
