# Analysis Plan Schema

The analysis plan is the bridge between guided research discussion and env execution.

It is grouped by model module. Module-level fields are defined in `references/models/`.

It is not a flat copy of the 18 regression arguments.

## Minimum Shape

```json
{
  "data": {
    "input_path": "string",
    "profile_path": "string",
    "panel": {
      "entity_var": "string",
      "time_var": "string"
    }
  },
  "research": {
    "topic_summary": "string",
    "expected_direction": "positive"
  },
  "baseline": {
    "enabled": true,
    "outcomes": ["string"],
    "explanatory_vars": ["string"],
    "controls": {
      "always_include": ["string"],
      "search_pool": ["string"],
      "min_count": 0
    },
    "fixed_effects": {
      "entity": "string",
      "time": "string"
    },
    "vce_policy": {
      "summary_enumerate": ["ols", "robust", "cluster_entity", "cluster_entity_time"],
      "recommended_final": "cluster_entity"
    }
  },
  "robustness": {
    "enabled": false,
    "alternative_outcomes": [],
    "alternative_explanatory_vars": [],
    "lag_explanatory_vars": [],
    "log_y": false,
    "log_x": false,
    "sample_window": null
  },
  "mechanism": {
    "enabled": false,
    "variables": []
  },
  "moderation": {
    "enabled": false,
    "variables": []
  },
  "heterogeneity": {
    "enabled": false,
    "discrete_groups": [],
    "selected_values": {}
  },
  "iv": {
    "enabled": false,
    "instruments": [],
    "interpretation_policy": "exploratory"
  },
  "execution": {
    "env": "python",
    "selected_candidate": {
      "selection_id": "",
      "cv_idx": null,
      "vce_idx": null
    }
  }
}
```

## Compilation Rules

- The compiler emits the regression args consumed by env scripts.
- Module-specific regression args contributions are defined in `references/models/`.
