version 17.0
clear all
set more off

/*
Regression Summary - Exhaustive cv x vce run, scoring, combination summary table. No Word export.

Exhaustive dimensions:
  1. cv_subset: from all CVs, select subsets (fixed vars required, min_count constraint)
  2. vce_type: ols, robust, cluster1, cluster2

Pruning: Skip robustness/IV/mediation/moderation unless at least one baseline-cv has p<0.1 AND correct coef direction (per coef_direction).

Performance (oneclick-inspired): No data reload per iteration; rob vars created once; cv subsets in memory; quietly + no est store.

Selection: rows expose cv_idx and vce_idx directly. Pass those values to scripts/envs/stata/generate_final_source.py.

Config: set starlane_* globals before running this file. The workflow runner
generates a stata_summary_config.do file for this purpose.

Config globals:
  starlane_input_dta
  starlane_y
  starlane_x
  starlane_cv
  starlane_cv_fixed
  starlane_cv_min_count
  starlane_panelvar
  starlane_timevar
  starlane_meds
  starlane_mods
  starlane_heterogeneity_discrete
  starlane_het_disc_vals
  starlane_rob_vars
  starlane_y_ln
  starlane_x_ln
  starlane_rob_year_range
  starlane_iv
  starlane_coef_direction
  starlane_cv_idx_start
  starlane_cv_idx_end
  starlane_probe_only
  starlane_csv_timestamp

Paths default to .starlane/ and .starlane/tmp unless $STARLANE_EXPORT and $STARLANE_TMP are set.

Output:
  - combination_summary.csv: in $STARLANE_EXPORT or .starlane/
  - Coef cells: {value}{stars} e.g. 0.114***; column names use __ as segment separator
  - selection_id: plain cv_idx_vce_idx; pass cv_idx and vce_idx to scripts/envs/stata/generate_final_source.py
  - Intermediates (.score_*.dta, part CSV, .n_valid.txt) under $STARLANE_TMP or .starlane/tmp.
*/

local input_arg "$starlane_input_dta"
local y_arg "$starlane_y"
local x_arg "$starlane_x"
local cv_arg "$starlane_cv"
local cv_fixed_arg "$starlane_cv_fixed"
local cv_min_count_arg "$starlane_cv_min_count"
local panelvar_arg "$starlane_panelvar"
local timevar_arg "$starlane_timevar"
local meds_arg "$starlane_meds"
local mods_arg "$starlane_mods"
local het_disc_arg "$starlane_heterogeneity_discrete"
local het_disc_vals_arg "$starlane_het_disc_vals"
local rob_vars_arg "$starlane_rob_vars"
local y_ln_arg "$starlane_y_ln"
local x_ln_arg "$starlane_x_ln"
local rob_year_range_arg "$starlane_rob_year_range"
local iv_arg "$starlane_iv"
local coef_direction_arg "$starlane_coef_direction"
local cv_idx_start_arg "$starlane_cv_idx_start"
local cv_idx_end_arg "$starlane_cv_idx_end"
local probe_only_arg "$starlane_probe_only"
local csv_timestamp_arg "$starlane_csv_timestamp"

// Validate required parameters
if "`input_arg'" == "" | "`y_arg'" == "" | "`x_arg'" == "" | "`cv_arg'" == "" | "`panelvar_arg'" == "" | "`timevar_arg'" == "" {
	di as error "Usage: do regression_summary.do input.dta ""y1 y2"" ""x"" ""cv1 cv2"" """" 1 ""id"" ""year"" ..."
	exit 198
}

// cluster_var = panelvar, cluster_var2 = timevar per user-data-spec
local panelvar_name = trim("`panelvar_arg'")
local cluster_var "`panelvar_name'"
local cluster_var2 = trim("`timevar_arg'")

capture confirm file "`input_arg'"
if _rc {
	di as error "Input file not found: `input_arg'"
	exit 601
}

// Load data: .dta, .xlsx, .xls, or .csv (first row as headers for non-dta)
local input_ext = lower(substr("`input_arg'", -4, .))
local input_ext5 = lower(substr("`input_arg'", -5, .))
if "`input_ext'" == ".dta" {
	use "`input_arg'", clear
}
else if "`input_ext'" == ".csv" {
	import delimited "`input_arg'", clear varnames(1) case(preserve)
}
else if "`input_ext'" == ".xls" | "`input_ext5'" == ".xlsx" {
	import excel "`input_arg'", firstrow clear case(preserve)
}
else {
	di as error "Unsupported input format: `input_arg'"
	di as error "Supported formats: .dta, .xlsx, .xls, .csv"
	exit 198
}

capture confirm variable `panelvar_name'
if _rc {
	di as error "Panel entity variable not found: `panelvar_name'"
	exit 111
}

capture confirm string variable `panelvar_name'
if _rc == 0 {
	tempvar __simen_panel_probe
	capture gen double `__simen_panel_probe' = real(trim(`panelvar_name'))
	local panelvar_needs_group 0

	if _rc != 0 {
		local panelvar_needs_group 1
	}
	else {
		capture count if trim(`panelvar_name') != "" & missing(`__simen_panel_probe')
		if _rc != 0 {
			local panelvar_needs_group 1
		}
		else if r(N) > 0 {
			local panelvar_needs_group 1
		}
	}

	if `panelvar_needs_group' == 0 {
		capture destring `panelvar_name', replace
		if _rc == 0 {
			di "STARLANE_PANELVAR_NUMERIC: `panelvar_name'"
		}
	}
	else {
		local base = substr("`panelvar_name'", 1, 20)
		local target = "`base'_gid"
		capture confirm new variable `target'
		local suffix_idx = 0
		while _rc != 0 {
			local suffix_idx = `suffix_idx' + 1
			local target = "`base'_g`suffix_idx'"
			capture confirm new variable `target'
		}
		egen long `target' = group(`panelvar_name')
		di "STARLANE_PANELVAR_GROUP: `panelvar_name' -> `target'"
		local panelvar_name "`target'"
		local cluster_var "`target'"
	}

	capture drop `__simen_panel_probe'
}

global y "`y_arg'"
global x "`x_arg'"
global cv_all "`cv_arg'"
global panelvar "`panelvar_name'"
global timevar "`timevar_arg'"
global cluster_var "`cluster_var'"
global cluster_var2 "`cluster_var2'"

if "$STARLANE_EXPORT" == "" {
	global STARLANE_EXPORT ".starlane"
}
if "$STARLANE_TMP" == "" {
	global STARLANE_TMP ".starlane/tmp"
}
global export_dir "$STARLANE_EXPORT"
global temp_dir "$STARLANE_TMP"
* Stata mkdir does not create parent dirs; create export_dir and temp_dir hierarchy for robustness
capture mkdir "$export_dir"
local temp_dir_parent = substr("$temp_dir", 1, strrpos("$temp_dir", "/") - 1)
if "`temp_dir_parent'" != "" {
	capture mkdir "`temp_dir_parent'"
}
capture mkdir "$temp_dir"

local coef_direction = trim(lower("`coef_direction_arg'"))
if "`coef_direction'" == "" {
	local coef_direction "positive"
}
if !inlist("`coef_direction'", "positive", "negative") {
	di as error "coef_direction must be 'positive' or 'negative'"
	exit 198
}
global coef_direction "`coef_direction'"

local cv_fixed = trim("`cv_fixed_arg'")
local cv_min_count = trim("`cv_min_count_arg'")
if "`cv_min_count'" == "" {
	local cv_min_count 0
}
global cv_fixed "`cv_fixed'"
global cv_min_count `cv_min_count'

// Parse meds, mods, heterogeneity_discrete, heterogeneity_discrete_values, rob_vars, iv
global meds ""
local meds_raw = trim("`meds_arg'")
if "`meds_raw'" != "" {
	local meds_parsed = subinstr("`meds_raw'", "|", " ", .)
	global meds "`meds_parsed'"
}
// Canonical ModelPlan (model_plan.build_specs) keeps only the first mechanism
// variable in the summary chain; the full list still enters the sample pool.
global meds_run : word 1 of $meds

global mods ""
local mods_raw = trim("`mods_arg'")
if "`mods_raw'" != "" {
	local mods_parsed = subinstr("`mods_raw'", "|", " ", .)
	global mods "`mods_parsed'"
}

global heterogeneity_discrete ""
local heterogeneity_discrete_raw = trim("`het_disc_arg'")
if "`heterogeneity_discrete_raw'" != "" {
	local heterogeneity_discrete_parsed = subinstr("`heterogeneity_discrete_raw'", "|", " ", .)
	global heterogeneity_discrete "`heterogeneity_discrete_parsed'"
	// Validate: heterogeneity_discrete must be variable names (e.g. SOE|Region), not parameter names
	foreach _v of global heterogeneity_discrete {
		if regexm(`"`_v'"', "^_") | regexm(`"`_v'"', "_arg$") {
			di as error "Invalid heterogeneity_discrete: `_v'. Pass variable names (e.g. SOE|Region), not parameter names. Values belong in starlane_het_disc_vals (e.g. SOE:1;0)."
			exit 198
		}
	}
}

global heterogeneity_discrete_values "`het_disc_vals_arg'"
if regexm(`"$heterogeneity_discrete_values"', "^_[a-z_]+_arg$") {
	di as error "Invalid heterogeneity_discrete_values: pass values (e.g. SOE:1;0|Region:East;West), not param names."
	exit 198
}

global rob_ln_y ""
global rob_alt_x ""
global rob_ln_x ""
global rob_alt_y ""
global rob_lag_periods ""

local rob_raw = trim("`rob_vars_arg'")
if "`rob_raw'" != "" {
	local rob_rest "`rob_raw'"
	while "`rob_rest'" != "" {
		local pipe_pos = strpos("`rob_rest'", "|")
		if `pipe_pos' == 0 {
			local rob_item "`rob_rest'"
			local rob_rest ""
		}
		else {
			local rob_item = substr("`rob_rest'", 1, `pipe_pos' - 1)
			local rob_rest = substr("`rob_rest'", `pipe_pos' + 1, .)
		}
		local colon_pos = strpos("`rob_item'", ":")
		if `colon_pos' > 0 {
			local rob_type = substr("`rob_item'", 1, `colon_pos' - 1)
			local rob_value = substr("`rob_item'", `colon_pos' + 1, .)
			if "`rob_type'" == "ln_y" global rob_ln_y "`rob_value'"
			if "`rob_type'" == "alt_x" global rob_alt_x "`rob_value'"
			if "`rob_type'" == "ln_x" global rob_ln_x "`rob_value'"
			if "`rob_type'" == "alt_y" global rob_alt_y "`rob_value'"
			if "`rob_type'" == "lag" global rob_lag_periods "`rob_value'"
		}
	}
}

// y_ln, x_ln: "1"/"是"/"" = do ln robustness (default); "0"/"否" = skip
local y_ln_val = trim(lower("`y_ln_arg'"))
local x_ln_val = trim(lower("`x_ln_arg'"))
local y_ln_auto 0
local x_ln_auto 0
if inlist("`y_ln_val'", "", "1", "是", "true", "yes") {
	local y_ln_auto 1
}
if inlist("`x_ln_val'", "", "1", "是", "true", "yes") {
	local x_ln_auto 1
}
global y_ln_auto `y_ln_auto'
global x_ln_auto `x_ln_auto'

// rob_year_range: "year_left:year_right" (left < right). Empty = skip.
// Time window is the retained subsample-style robustness form in the current standard chain.
local rob_yr = trim("`rob_year_range_arg'")
global rob_year_range_cond ""
if "`rob_yr'" != "" {
	local colon_pos = strpos("`rob_yr'", ":")
	if `colon_pos' > 0 {
		local yr_left = trim(substr("`rob_yr'", 1, `colon_pos' - 1))
		local yr_right = trim(substr("`rob_yr'", `colon_pos' + 1, .))
		if "`yr_left'" != "" & "`yr_right'" != "" {
			global rob_year_range_cond "${timevar}>=`yr_left' & ${timevar}<=`yr_right'"
		}
	}
}

global iv ""
local iv_raw = trim("`iv_arg'")
if "`iv_raw'" != "" {
	global iv "`iv_raw'"
}

// Load canonical cv subsets generated from workflow/model_plan.py.
local n_valid = real("$starlane_plan_cv_subset_count")
if missing(`n_valid') {
	local n_valid 0
}

if `n_valid' == 0 {
	di as error "No valid cv subsets. Check cv_fixed and cv_min_count."
	exit 198
}

forvalues cv_plan_idx = 0/`=`n_valid' - 1' {
	local cv_sub_`cv_plan_idx' "${starlane_plan_cv_sub_`cv_plan_idx'}"
}

// Probe-only mode: write n_valid and exit (used by parallel orchestrator)
if "$STARLANE_CACHE_DTA" == "" {
	global STARLANE_CACHE_DTA "$temp_dir/.input_data.dta"
}
local starlane_cache_dta "$STARLANE_CACHE_DTA"
local probe_only = trim(lower("`probe_only_arg'"))
if inlist("`probe_only'", "1", "yes", "true") {
	// Save xlsx/xls to .dta for workers (import excel is 10-100x slower than use; avoid N workers each loading xlsx)
	if "`input_ext'" == ".xls" | "`input_ext5'" == ".xlsx" {
		save "`starlane_cache_dta'", replace
	}
	file open probe_fh using "$temp_dir/.n_valid.txt", write replace
	file write probe_fh "`n_valid'"
	file close probe_fh
	exit 0
}

// Parse cv range for parallel chunk (optional)
local cv_start ""
local cv_end ""
local use_range 0
if "`cv_idx_start_arg'" != "" & "`cv_idx_end_arg'" != "" {
	local cv_start = real(trim("`cv_idx_start_arg'"))
	local cv_end = real(trim("`cv_idx_end_arg'"))
	if !missing(`cv_start') & !missing(`cv_end') & `cv_start' >= 0 & `cv_end' < `n_valid' & `cv_start' <= `cv_end' {
		local use_range 1
	}
}

// Sample logic aligned with the final-stage generator:
// Per cv_subset: sample_pool_vars (with current cv), __base_raw_ok, reghdfe y x cv if __base_raw_ok, __base_sample = e(sample).
// All regressions use if __base_sample. Sample setup done inside cv loop.
tsset $panelvar $timevar

// Create rob vars once (like oneclick: no reload per iteration)
// Per user-data-spec: when y_ln=是 or x_ln=是, do ln(y)/ln(x) robustness; when 否, skip
capture drop _rob_ln_*
local rob_ln_y_use ""
if $y_ln_auto {
	local rob_ln_y_use "$rob_ln_y"
	foreach y of global y {
		capture confirm numeric variable `y'
		if _rc == 0 {
			capture gen double _rob_ln_`y' = ln(`y') if `y' > 0 & !missing(`y')
			if _rc == 0 {
				local rob_ln_y_use "`rob_ln_y_use' _rob_ln_`y'"
			}
		}
	}
}
local rob_ln_x_use ""
if $x_ln_auto {
	local rob_ln_x_use "$rob_ln_x"
	foreach x of global x {
		capture confirm numeric variable `x'
		if _rc == 0 {
			capture gen double _rob_ln_`x' = ln(`x') if `x' > 0 & !missing(`x')
			if _rc == 0 {
				local rob_ln_x_use "`rob_ln_x_use' _rob_ln_`x'"
			}
		}
	}
}

// Create moderation std vars once (they do not depend on cv or vce)
if "$mods" != "" {
	capture drop std_x_* std_mod_*
	foreach x of global x {
		quietly egen std_x_`x' = std(`x')
	}
	foreach mod_var of global mods {
		quietly egen std_mod_`mod_var' = std(`mod_var')
	}
}

capture program drop _calc_effective_stars
program define _calc_effective_stars
	args coef se
	local effective_stars 0
	if !missing(`coef') & !missing(`se') & `se' > 0 {
		local dir_ok 0
		if ("$coef_direction" == "positive" & `coef' > 0) | ("$coef_direction" == "negative" & `coef' < 0) {
			local dir_ok 1
		}
		if `dir_ok' {
			capture local df = e(df_r)
			if _rc != 0 | missing(`df') {
				capture local df = e(N) - e(df_m) - 1
			}
			if missing(`df') | `df' <= 0 {
				local df 999999
			}
			local t = `coef' / `se'
			local pval = 2 * ttail(`df', abs(`t'))
			local effective_stars = cond(`pval' < 0.01, 3, cond(`pval' < 0.05, 2, cond(`pval' < 0.1, 1, 0)))
		}
	}
	c_local effective_stars `effective_stars'
end

capture program drop _post_coef
program define _post_coef
	args scorehandle vce_suffix section target_var
	local coef = _b[`target_var']
	local se   = _se[`target_var']
	local dep  = "`e(depvar)'"
	_calc_effective_stars `coef' `se'
	post `scorehandle' ("`vce_suffix'") ("`section'") ("`dep'") ("`target_var'") (`coef') (`se') (`effective_stars')
end

capture program drop _urldecode
program define _urldecode
	args raw_input
	local in `"`raw_input'"'
	local out ""
	local in_len = length(`"`in'"')
	local i 1
	while `i' <= `in_len' {
		local ch = substr(`"`in'"', `i', 1)
		if "`ch'" == "%" & `i' + 2 <= `in_len' {
			local hexpair = upper(substr(`"`in'"', `i' + 1, 2))
			local h1 = strpos("0123456789ABCDEF", substr("`hexpair'", 1, 1))
			local h2 = strpos("0123456789ABCDEF", substr("`hexpair'", 2, 1))
			if `h1' > 0 & `h2' > 0 {
				local ascii = (`h1' - 1) * 16 + (`h2' - 1)
				local out = `"`out'"' + char(`ascii')
				local i = `i' + 3
				continue
			}
		}
		local out = `"`out'"' + "`ch'"
		local i = `i' + 1
	}
	c_local decoded `"`out'"'
end

capture program drop _load_discrete_values_for_var
program define _load_discrete_values_for_var
	args raw target_var prefix
	local count 0
	c_local `prefix'_count 0
	local rest `"`raw'"'
	while `"`rest'"' != "" {
		local pipe_pos = strpos(`"`rest'"', "|")
		if `pipe_pos' == 0 {
			local item `"`rest'"'
			local rest ""
		}
		else {
			local item = substr(`"`rest'"', 1, `pipe_pos' - 1)
			local rest = substr(`"`rest'"', `pipe_pos' + 1, .)
		}
		local colon_pos = strpos(`"`item'"', ":")
		if `colon_pos' <= 0 {
			continue
		}
		local key_encoded = trim(substr(`"`item'"', 1, `colon_pos' - 1))
		local values_encoded = trim(substr(`"`item'"', `colon_pos' + 1, .))
		_urldecode `"`key_encoded'"'
		local parsed_key `"`decoded'"'
		if `"`parsed_key'"' != `"`target_var'"' {
			continue
		}
		local values_rest `"`values_encoded'"'
		while `"`values_rest'"' != "" {
			local sep_pos = strpos(`"`values_rest'"', ";")
			if `sep_pos' == 0 {
				local value_encoded `"`values_rest'"'
				local values_rest ""
			}
			else {
				local value_encoded = substr(`"`values_rest'"', 1, `sep_pos' - 1)
				local values_rest = substr(`"`values_rest'"', `sep_pos' + 1, .)
			}
			local value_encoded = trim(`"`value_encoded'"')
			if `"`value_encoded'"' == "" {
				continue
			}
			_urldecode `"`value_encoded'"'
			local value_decoded `"`decoded'"'
			if `"`value_decoded'"' == "" {
				continue
			}
			local count = `count' + 1
			c_local `prefix'_enc_`count' `"`value_encoded'"'
			c_local `prefix'_dec_`count' `"`value_decoded'"'
			c_local `prefix'_count `count'
		}
		continue, break
	}
end

// Column header generated from workflow/model_plan.py.
local col_names "$starlane_plan_summary_columns"
if trim("`col_names'") == "" {
	di as error "Missing starlane_plan_summary_columns. Regenerate Stata summary config."
	exit 198
}

// CSV output path: intermediates to temp_dir, final to export_dir
// If csv_timestamp_arg is provided, use timestamped filename to prevent overwriting
local csv_timestamp = trim("`csv_timestamp_arg'")
if `use_range' {
	local csv_path "$temp_dir/combination_summary_part_`cv_start'_`cv_end'.csv"
}
else if "`csv_timestamp'" != "" {
	local csv_path "$export_dir/combination_summary_`csv_timestamp'.csv"
}
else {
	local csv_path "$export_dir/combination_summary.csv"
}
tempname csv_fh
file open `csv_fh' using "`csv_path'", write replace
local header = subinstr(`"`col_names'"', " ", ",", .)
file write `csv_fh' "`header'" _n

// Minimum observations per cv_subset for regression; skip and log if insufficient
// Reghdfe may drop singletons; use conservative threshold to avoid r(2001)
local min_n_cv 30

// Outer loop: cv subsets (full or chunk range)
// Avoid cond() with empty cv_start/cv_end when use_range=0
local loop_start 0
local loop_end = `n_valid' - 1
if `use_range' {
	local loop_start `cv_start'
	local loop_end `cv_end'
}
forvalues cv_idx = `loop_start'/`loop_end' {
	local cv_subset "`cv_sub_`cv_idx''"
	global cv "`cv_subset'"

	// Sample size check: skip cv_subset if insufficient observations for y,x,cv,panel,time
	preserve
	quietly egen _n_check = rowmiss($y $x $cv $panelvar $timevar)
	quietly keep if _n_check == 0
	local n_avail = _N
	restore
	if `n_avail' < `min_n_cv' {
		continue
	}

	// Sample pool and __base_sample per cv_subset (align with final-stage output)
	local sample_pool_vars "$panelvar $timevar $y $x $cv"
	if "$meds" != "" local sample_pool_vars "`sample_pool_vars' $meds"
	if "$mods" != "" local sample_pool_vars "`sample_pool_vars' $mods"
	if "$iv" != "" local sample_pool_vars "`sample_pool_vars' $iv"
	if "$heterogeneity_discrete" != "" local sample_pool_vars "`sample_pool_vars' $heterogeneity_discrete"
	if "$rob_alt_x" != "" local sample_pool_vars "`sample_pool_vars' $rob_alt_x"
	if "$rob_alt_y" != "" local sample_pool_vars "`sample_pool_vars' $rob_alt_y"
	quietly egen __base_miss = rmiss(`sample_pool_vars')
	quietly gen byte __base_raw_ok = (__base_miss == 0)
	quietly drop __base_miss
	local first_y : word 1 of $y
	local first_x : word 1 of $x
	capture quietly reghdfe `first_y' `first_x' $cv if __base_raw_ok, absorb($timevar $panelvar)
	if _rc != 0 {
		quietly drop __base_raw_ok
		continue
	}
	quietly gen byte __base_sample = e(sample)
	quietly drop __base_raw_ok

	// Inner loop: VCE choices generated from workflow/model_plan.py.
	forvalues vce_idx = 0/3 {
		local vce_suffix "${starlane_plan_vce_suffix_`vce_idx'}"
		local vce_option "${starlane_plan_vce_option_`vce_idx'}"
		if `vce_idx' == 0 {
			global vce ""
			local vce_suffix "ols"
		}
		else if `vce_idx' == 1 {
			global vce "vce(robust)"
			local vce_suffix "robust"
		}
		else if `vce_idx' == 2 {
			global vce "vce(cluster $cluster_var)"
			if "`vce_suffix'" == "" local vce_suffix "cluster_$cluster_var"
		}
		else if `vce_idx' == 3 {
			global vce "vce(cluster $cluster_var $cluster_var2)"
			if "`vce_suffix'" == "" local vce_suffix "cluster_${cluster_var}_${cluster_var2}"
		}

		local selection_id "`cv_idx'_`vce_idx'"

		// Use temp_dir for score accumulation (intermediate; parallel workers share same temp_dir)
		local scoreaccum "$temp_dir/.score_`cv_idx'_`vce_idx'.dta"
		postfile scorehandle str32 vce_suffix str64 section str64 depvar str64 target_var coef se stars using "`scoreaccum'", replace

		local m 0

		// Baseline nocv: compute per (cv_idx,vce_idx) with if __base_sample (align with final-stage output)
		foreach y of global y {
			foreach x of global x {
				local ++m
				capture quietly reghdfe `y' `x' if __base_sample, absorb($timevar $panelvar) $vce
				if _rc == 0 {
					_post_coef scorehandle "`vce_suffix'" "baseline_nocv" "`x'"
				}
				else {
					post scorehandle ("`vce_suffix'") ("baseline_nocv") ("`y'") ("`x'") (.) (.) (0)
				}
			}
		}

		local any_sig_cv 0
		local any_dir_ok 0
		foreach y of global y {
			foreach x of global x {
				local ++m
				capture quietly reghdfe `y' `x' $cv if __base_sample, absorb($timevar $panelvar) $vce
				if _rc == 0 {
					_post_coef scorehandle "`vce_suffix'" "baseline_cv" "`x'"
					capture {
						local coef_cv = _b[`x']
						local se_cv = _se[`x']
						if !missing(`coef_cv') & !missing(`se_cv') & `se_cv' > 0 {
							local t = `coef_cv' / `se_cv'
							capture local df = e(df_r)
							if _rc != 0 | missing(`df') capture local df = e(N) - e(df_m) - 1
							if missing(`df') | `df' <= 0 local df 999999
							if 2 * ttail(`df', abs(`t')) < 0.1 local any_sig_cv 1
						}
						if !missing(`coef_cv') {
							if ("$coef_direction" == "positive" & `coef_cv' > 0) | ("$coef_direction" == "negative" & `coef_cv' < 0) {
								local any_dir_ok 1
							}
						}
					}
				}
				else {
					post scorehandle ("`vce_suffix'") ("baseline_cv") ("`y'") ("`x'") (.) (.) (0)
				}
			}
		}

		// Robustness (skip unless at least one baseline-cv is significant AND has correct direction), order per user-data-spec: alt_x, alt_y, ln_x, ln_y, lag, year
		if `any_sig_cv' & `any_dir_ok' {
		if "$rob_alt_x" != "" {
			foreach y of global y {
				foreach x of global rob_alt_x {
					local ++m
					capture quietly reghdfe `y' `x' $cv if __base_sample, absorb($timevar $panelvar) $vce
					if _rc == 0 {
						_post_coef scorehandle "`vce_suffix'" "robustness_alt_x" "`x'"
					}
					else {
						post scorehandle ("`vce_suffix'") ("robustness_alt_x") ("`y'") ("`x'") (.) (.) (0)
					}
				}
			}
		}
		if "$rob_alt_y" != "" {
			foreach y of global rob_alt_y {
				foreach x of global x {
					local ++m
					capture quietly reghdfe `y' `x' $cv if __base_sample, absorb($timevar $panelvar) $vce
					if _rc == 0 {
						_post_coef scorehandle "`vce_suffix'" "robustness_alt_y" "`x'"
					}
					else {
						post scorehandle ("`vce_suffix'") ("robustness_alt_y") ("`y'") ("`x'") (.) (.) (0)
					}
				}
			}
		}
		if "`rob_ln_x_use'" != "" {
			foreach y of global y {
				foreach x of local rob_ln_x_use {
					local ++m
					capture quietly reghdfe `y' `x' $cv if __base_sample, absorb($timevar $panelvar) $vce
					if _rc == 0 {
						_post_coef scorehandle "`vce_suffix'" "robustness_ln_x" "`x'"
					}
					else {
						post scorehandle ("`vce_suffix'") ("robustness_ln_x") ("`y'") ("`x'") (.) (.) (0)
					}
				}
			}
		}
		if "`rob_ln_y_use'" != "" {
			foreach y of local rob_ln_y_use {
				foreach x of global x {
					local ++m
					capture quietly reghdfe `y' `x' $cv if __base_sample, absorb($timevar $panelvar) $vce
					if _rc == 0 {
						_post_coef scorehandle "`vce_suffix'" "robustness_ln_y" "`x'"
					}
					else {
						post scorehandle ("`vce_suffix'") ("robustness_ln_y") ("`y'") ("`x'") (.) (.) (0)
					}
				}
			}
		}
		if "$rob_lag_periods" != "" {
			foreach p of global rob_lag_periods {
				foreach y of global y {
					foreach x of global x {
						local ++m
						capture quietly reghdfe `y' l`p'.`x' $cv if __base_sample, absorb($timevar $panelvar) $vce
						if _rc == 0 {
							_post_coef scorehandle "`vce_suffix'" "robustness_lag" "l`p'.`x'"
						}
						else {
							post scorehandle ("`vce_suffix'") ("robustness_lag") ("`y'") ("l`p'.`x'") (.) (.) (0)
						}
					}
				}
			}
		}
		if "$rob_year_range_cond" != "" {
			foreach y of global y {
				foreach x of global x {
					local ++m
					capture quietly reghdfe `y' `x' $cv if __base_sample & $rob_year_range_cond, absorb($timevar $panelvar) $vce
					if _rc == 0 {
						_post_coef scorehandle "`vce_suffix'" "robustness_year" "`x'"
					}
					else {
						post scorehandle ("`vce_suffix'") ("robustness_year") ("`y'") ("`x'") (.) (.) (0)
					}
				}
			}
		}

		// IV (per user-data-spec: 2SLS two stages, stage1=iv coef in x~iv+cv, stage2=x coef in y~x_hat+cv)
		if "$iv" != "" {
			foreach y of global y {
				foreach x of global x {
					foreach ivv of global iv {
						local ++m
						capture quietly reghdfe `x' `ivv' $cv if __base_sample, absorb($timevar $panelvar) $vce
						if _rc == 0 {
							_post_coef scorehandle "`vce_suffix'" "iv_stage1" "`ivv'"
						}
						else {
							post scorehandle ("`vce_suffix'") ("iv_stage1") ("`x'") ("`ivv'") (.) (.) (0)
						}
						local ++m
						capture quietly ivreghdfe `y' $cv (`x' = `ivv') if __base_sample, absorb($timevar $panelvar) $vce
						if _rc == 0 {
							_post_coef scorehandle "`vce_suffix'" "iv_stage2" "`x'"
						}
						else {
							post scorehandle ("`vce_suffix'") ("iv_stage2") ("`y'") ("`x'") (.) (.) (0)
						}
					}
				}
			}
		}

		// Mediation
		foreach med_var of global meds_run {
			foreach y of global y {
				foreach x of global x {
					local ++m
					capture quietly reghdfe `y' `x' $cv if __base_sample, absorb($timevar $panelvar) $vce
					if _rc == 0 {
						_post_coef scorehandle "`vce_suffix'" "mediation_`med_var'" "`x'"
					}
					else {
						post scorehandle ("`vce_suffix'") ("mediation_`med_var'") ("`y'") ("`x'") (.) (.) (0)
					}
				}
			}
			foreach x of global x {
				local ++m
				capture quietly reghdfe `med_var' `x' $cv if __base_sample, absorb($timevar $panelvar) $vce
				if _rc == 0 {
					_post_coef scorehandle "`vce_suffix'" "mediation_`med_var'" "`x'"
				}
				else {
					post scorehandle ("`vce_suffix'") ("mediation_`med_var'") ("`med_var'") ("`x'") (.) (.) (0)
				}
			}
		}

		// Moderation (std vars already created before loop)
		if "$mods" != "" {
			foreach mod_var of global mods {
				foreach y of global y {
					foreach x of global x {
						local ++m
						capture quietly reghdfe `y' c.std_x_`x'##c.std_mod_`mod_var' $cv if __base_sample, absorb($timevar $panelvar) $vce
						if _rc == 0 {
							local coef = _b[c.std_x_`x'#c.std_mod_`mod_var']
							local se   = _se[c.std_x_`x'#c.std_mod_`mod_var']
							local dep  = "`e(depvar)'"
							_calc_effective_stars `coef' `se'
							post scorehandle ("`vce_suffix'") ("moderation_`mod_var'") ("`dep'") ("interaction") (`coef') (`se') (`effective_stars')
						}
						else {
							post scorehandle ("`vce_suffix'") ("moderation_`mod_var'") ("`y'") ("interaction") (.) (.) (0)
						}
					}
				}
			}
		}
		* Same (y,x) grouped; within each (y,x), all group values adjacent (align with Stata final source generator)
		foreach group_var of global heterogeneity_discrete {
			_load_discrete_values_for_var `"$heterogeneity_discrete_values"' "`group_var'" discrete_vals
			if `discrete_vals_count' <= 0 {
				continue
			}
			foreach y of global y {
				foreach x of global x {
					forvalues discrete_idx = 1/`discrete_vals_count' {
						local group_value_dec `"`discrete_vals_dec_`discrete_idx''"'
						local section_name "heterogeneity_discrete_`group_var'_`discrete_idx'"
						capture confirm number `group_value_dec'
						if _rc == 0 {
							local group_cond "`group_var' == `group_value_dec'"
						}
						else {
							local group_value_escaped = subinstr(`"`group_value_dec'"', `"""', `""""', .)
							local group_cond `"`group_var' == "`group_value_escaped'""'
						}
						local ++m
						capture quietly reghdfe `y' `x' $cv if __base_sample & `group_cond', absorb($timevar $panelvar) $vce
						if _rc == 0 {
							_post_coef scorehandle "`vce_suffix'" "`section_name'" "`x'"
						}
						else {
							post scorehandle ("`vce_suffix'") ("`section_name'") ("`y'") ("`x'") (.) (.) (0)
						}
					}
				}
			}
		}
		}

		postclose scorehandle

		// Compute score and build row from scoreaccum (coef+stars per user-data-spec)
		tempname S_score
		preserve
		scalar `S_score' = 0
		capture use "`scoreaccum'", clear
		if _rc == 0 & _N > 0 {
			capture collapse (max) stars, by(vce_suffix section)
			if _rc == 0 {
				capture collapse (sum) stars, by(vce_suffix)
				if _rc == 0 {
					quietly summarize stars
					scalar `S_score' = cond(r(N) > 0, r(sum), 0)
				}
			}
		}
		restore

		preserve
		capture use "`scoreaccum'", clear
		local row_vals ""
		local n_coef : word count `col_names'
		local n_coef = `n_coef' - 6
		local n_rows = cond(_rc == 0 & _N > 0, _N, 0)
		if `n_rows' > 0 {
			forvalues i = 1/`n_rows' {
				local c = coef[`i']
				local s = stars[`i']
				if missing(`c') {
					local v ""
				}
				else {
					local star_str = cond(`s' >= 3, "***", cond(`s' >= 2, "**", cond(`s' >= 1, "*", "")))
					local v "`=strofreal(`c')'`star_str'"
				}
				local row_vals "`row_vals'`v',"
			}
		}
		local n_pad = `n_coef' - `n_rows'
		forvalues i = 1/`=max(0, `n_pad')' {
			local row_vals "`row_vals',"
		}
		if length("`row_vals'") > 0 {
			local row_vals = substr("`row_vals'", 1, length("`row_vals'") - 1)
		}
		restore

		local score_str = strofreal(scalar(`S_score'))
		local cv_selected_csv = subinstr("`cv_subset'", " ", "|", .)
		file write `csv_fh' "`selection_id',`cv_idx',`vce_idx',`vce_suffix',`cv_selected_csv',`score_str',`row_vals'" _n

		* Temp files; cleanup runs periodically.
	}
	quietly drop __base_sample
}

file close `csv_fh'
* Temp files; cleanup runs periodically.

di "STARLANE_OUTPUT: `csv_path'"
