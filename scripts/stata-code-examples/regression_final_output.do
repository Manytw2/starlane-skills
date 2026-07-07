** 结构示例（供 py 对照生成）
** 1. 本文件用于说明最终 do 文件的结构，不是逐字输出模板
** 2. 实际生成时，py 会尽量把参数直接分发到正文代码
** 3. 只有少量重复使用的值会保留为 local，避免输出大段未使用宏

** 输出与解析结果占位
global result "."                            // Word 导出目录
global docx_name "全部结果.docx"             // 输出文件名
global data_file "data.dta"                  // 数据文件路径
global panel_id "id"                         // absorb 个体维度
global panel_time "year"                     // absorb 时间维度
global cluster_var "id"                      // cluster 维度 1
global cluster_var2 "year"                   // cluster 维度 2
global cv_selected "Scale Lev lnAge Tange Cash ROA SOE Top1 Inst" // 当前 selection_id 对应的控制变量组合
global vce_opt "cluster id"                  // 当前 selection_id 对应的标准误

** 正文直接使用的核心占位
global y_1 "lnApplyG"                        // 被解释变量 1
global y_2 "lnGrantG"                        // 被解释变量 2
global y "$y_1 $y_2"                         // 因变量集合
global x "Attention"                         // 核心自变量
global iv "Thermalinv"                       // 工具变量
global med "Charge Subsidy lnCSR"            // 中介变量集合
global inter "OverSea lnMediaPos lnMediaNeg" // 调节变量集合
global heterogeneity_discrete "Region"       // het_disc: 离散异质性变量集合
global heterogeneity_discrete_values "Region:East;West" // het_disc_vals: 离散异质性已选值（扁平编码）
global med_1 "Charge"                        // 中介机制模板变量
global y_alt_1 "lnAGreenInv"                 // 替换被解释变量 1
global y_alt_2 "lnGGreenInv"                 // 替换被解释变量 2

* 对数稳健性在正文中临时生成 lnx_*/lny_* 辅助变量
global year_start 2008                       // 时间窗口起点
global year_end 2019                         // 时间窗口终点

** reg2docx 格式选项
local doc_star "star(* 0.1 ** 0.05 *** 0.01)"
local doc_b "b(%9.3f)"
local doc_se "se(%9.3f)"
local doc_scalar "scalars(N(%9.0fc) r2_a(%9.3f))"
local doc_fe `"addfe("Entity FE = Yes" "Time FE = Yes")"'
local doc_font "font(Times New Roman, 11)"
local doc_common "`doc_star' `doc_b' `doc_se' `doc_scalar' `doc_fe' depvar `doc_font'"
local doc_common_nodepvar "`doc_star' `doc_b' `doc_se' `doc_scalar' `doc_fe' `doc_font'"

********************************************
*************** 以下为正文程序 ***************
********************************************

use "$data_file", clear
global docxout "$result/$docx_name"

capture confirm string variable $panel_id
if _rc == 0 egen long __panel_gid = group($panel_id), label
if _rc == 0 global panel_id "__panel_gid"

** 全篇可比板块共用样本池
local sample_pool_vars "$panel_id $panel_time $x $y $cv_selected $iv $med $inter $heterogeneity_discrete $y_alt_1 $y_alt_2"
local desc_vars "$x $y $cv_selected $iv $med $inter $heterogeneity_discrete $y_alt_1 $y_alt_2"
egen __base_miss = rmiss(`sample_pool_vars')
gen byte __base_raw_ok = (__base_miss == 0)
drop __base_miss

quietly reghdfe $y_1 $x $cv_selected if __base_raw_ok, absorb($panel_time $panel_id) vce($vce_opt)
gen byte __base_sample = e(sample)
drop __base_raw_ok

** 基准回归 (全篇统一使用 $vce_opt)
**无cv
reghdfe $y_1 $x if __base_sample, absorb($panel_time $panel_id) vce($vce_opt)
est store m1
reghdfe $y_2 $x if __base_sample, absorb($panel_time $panel_id) vce($vce_opt)
est store m2
**有cv
reghdfe $y_1 $x $cv_selected if __base_sample, absorb($panel_time $panel_id) vce($vce_opt)
est store m3
reghdfe $y_2 $x $cv_selected if __base_sample, absorb($panel_time $panel_id) vce($vce_opt)
est store m4

reg2docx m1 m2 m3 m4 using "$docxout", replace `doc_common' title("Table 1: 基准回归") note("Standard errors in parentheses; *** p<0.01, ** p<0.05, * p<0.1")


**稳健性检验：X取对数
capture drop lnx_1
gen double lnx_1 = ln($x) if $x > 0 & !missing($x)
reghdfe $y_1 lnx_1 $cv_selected if __base_sample, absorb($panel_time $panel_id) vce($vce_opt)
est store m1
reghdfe $y_2 lnx_1 $cv_selected if __base_sample, absorb($panel_time $panel_id) vce($vce_opt)
est store m2

reg2docx m1 m2 using "$docxout", append `doc_common' title("Table 2: 稳健性检验-X取对数")

**稳健性检验：Y取对数
capture drop lny_1 lny_2
gen double lny_1 = ln($y_1) if $y_1 > 0 & !missing($y_1)
gen double lny_2 = ln($y_2) if $y_2 > 0 & !missing($y_2)
reghdfe lny_1 $x $cv_selected if __base_sample, absorb($panel_time $panel_id) vce($vce_opt)
est store m1
reghdfe lny_2 $x $cv_selected if __base_sample, absorb($panel_time $panel_id) vce($vce_opt)
est store m2

reg2docx m1 m2 using "$docxout", append `doc_common' title("Table 3: 稳健性检验-Y取对数")


**稳健性检验：替换变量 (x、y替换变量同理)
reghdfe $y_alt_1 $x $cv_selected if __base_sample, absorb($panel_time $panel_id) vce($vce_opt)
est store m1
reghdfe $y_alt_2 $x $cv_selected if __base_sample, absorb($panel_time $panel_id) vce($vce_opt)
est store m2

reg2docx m1 m2 using "$docxout", append `doc_common' title("Table 4: 稳健性检验-替换变量")


**稳健性检验：滞后期
** 先设置 panel_id 和 panel_time 才可以
** 对 x 滞后
tsset $panel_id $panel_time
reghdfe $y_1 l1.$x $cv_selected if __base_sample, absorb($panel_time $panel_id) vce($vce_opt)
est store m1
reghdfe $y_1 l2.$x $cv_selected if __base_sample, absorb($panel_time $panel_id) vce($vce_opt)
est store m2
reghdfe $y_1 l3.$x $cv_selected if __base_sample, absorb($panel_time $panel_id) vce($vce_opt)
est store m3

reghdfe $y_2 l1.$x $cv_selected if __base_sample, absorb($panel_time $panel_id) vce($vce_opt)
est store m4
reghdfe $y_2 l2.$x $cv_selected if __base_sample, absorb($panel_time $panel_id) vce($vce_opt)
est store m5
reghdfe $y_2 l3.$x $cv_selected if __base_sample, absorb($panel_time $panel_id) vce($vce_opt)
est store m6

reg2docx m1 m2 m3 m4 m5 m6 using "$docxout", append `doc_common' title("Table 5: 稳健性检验-滞后期")


** 稳健性检验：更改时间窗口
reghdfe $y_1 $x $cv_selected if __base_sample & $panel_time >= $year_start & $panel_time <= $year_end, absorb($panel_time $panel_id) vce($vce_opt)
est store m1
reghdfe $y_2 $x $cv_selected if __base_sample & $panel_time >= $year_start & $panel_time <= $year_end, absorb($panel_time $panel_id) vce($vce_opt)
est store m2

reg2docx m1 m2 using "$docxout", append `doc_common' title("Table 6: 稳健性检验-时间窗口")

local tbl 7

** 工具变量检验 (2SLS: first stage x~iv+cv, second stage y~x_hat+cv)
reghdfe $x $iv $cv_selected if __base_sample, absorb($panel_time $panel_id) vce($vce_opt)
est store m1
ivreghdfe $y_1 $cv_selected ($x = $iv) if __base_sample, absorb($panel_time $panel_id) vce($vce_opt)
est store m2
ivreghdfe $y_2 $cv_selected ($x = $iv) if __base_sample, absorb($panel_time $panel_id) vce($vce_opt)
est store m3

reg2docx m1 using "$docxout", append `doc_common' ///
	title("Table `tbl': 工具变量-一阶段") ///
	note("Standard errors in parentheses; *** p<0.01, ** p<0.05, * p<0.1; x ~ iv + cv; IV: $iv")
local ++tbl
reg2docx m2 m3 using "$docxout", append `doc_common' ///
	title("Table `tbl': 工具变量-二阶段 2SLS") ///
	note("Standard errors in parentheses; *** p<0.01, ** p<0.05, * p<0.1; y ~ x_hat + cv; IV: $iv")
local ++tbl

** 中介机制模板：江艇两步法
** 中介变量：$med_1
* 1. 总效应检验：Y <- X
reghdfe $y_1 $x $cv_selected if __base_sample, absorb($panel_time $panel_id) vce($vce_opt)
est store m1
reghdfe $y_2 $x $cv_selected if __base_sample, absorb($panel_time $panel_id) vce($vce_opt)
est store m2
* 2. 机制检验：M <- X
reghdfe $med_1 $x $cv_selected if __base_sample, absorb($panel_time $panel_id) vce($vce_opt)
est store m3

reg2docx m1 m2 m3 using "$docxout", append `doc_common' title("Table `tbl': 中介机制")
local ++tbl


**异质性分析：调节效应检验
local inter1 : word 1 of $inter
local inter2 : word 2 of $inter
local inter3 : word 3 of $inter
cap drop std$x std`inter1' std`inter2' std`inter3'
egen std$x = std($x)
foreach v in $inter {
	egen std`v' = std(`v')
}
reghdfe $y_1 c.std$x##c.std`inter1' $cv_selected if __base_sample, absorb($panel_time $panel_id) vce($vce_opt)
est store m1
reghdfe $y_2 c.std$x##c.std`inter1' $cv_selected if __base_sample, absorb($panel_time $panel_id) vce($vce_opt)
est store m2
reghdfe $y_1 c.std$x##c.std`inter2' $cv_selected if __base_sample, absorb($panel_time $panel_id) vce($vce_opt)
est store m3
reghdfe $y_2 c.std$x##c.std`inter2' $cv_selected if __base_sample, absorb($panel_time $panel_id) vce($vce_opt)
est store m4
reghdfe $y_1 c.std$x##c.std`inter3' $cv_selected if __base_sample, absorb($panel_time $panel_id) vce($vce_opt)
est store m5
reghdfe $y_2 c.std$x##c.std`inter3' $cv_selected if __base_sample, absorb($panel_time $panel_id) vce($vce_opt)
est store m6

reg2docx m1 m2 m3 m4 m5 m6 using "$docxout", append `doc_common' title("Table `tbl': 异质性分析-调节效应检验")
local ++tbl


**异质性分析：离散分组-Region
reghdfe $y_1 $x $cv_selected if __base_sample & Region=="East", absorb($panel_time $panel_id) vce($vce_opt)
est store m1
reghdfe $y_1 $x $cv_selected if __base_sample & Region=="West", absorb($panel_time $panel_id) vce($vce_opt)
est store m2
reghdfe $y_2 $x $cv_selected if __base_sample & Region=="East", absorb($panel_time $panel_id) vce($vce_opt)
est store m3
reghdfe $y_2 $x $cv_selected if __base_sample & Region=="West", absorb($panel_time $panel_id) vce($vce_opt)
est store m4

reg2docx m1 m2 m3 m4 using "$docxout", append `doc_common_nodepvar' mtitles("Region=East" "Region=West" "Region=East" "Region=West") title("Table `tbl': 异质性分析-离散分组-Region")
local ++tbl

** 描述性统计放在所有板块之后，并导出到 Word
sum2docx `desc_vars' if __base_sample using "$docxout", append ///
stats(N mean(%9.3f) sd(%9.3f) min(%9.3f) median(%9.3f) max(%9.3f)) ///
title(描述性统计)

di "全部结果已导出至: $docxout"
