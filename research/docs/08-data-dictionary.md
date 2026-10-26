# 结果文件和字段字典

## 主要文件

|文件|粒度与用途|
|---|---|
|`all_660912_cost_results.csv.gz`（归档恢复后）|每个n、m、mode、bps一行；完整0/10基点、各时期指标及账户统计|
|`全部330456种组合_单边10基点.csv`（恢复后）|每个n、m、mode一行，固定10基点；中文精简列，含全期和后段重置结果|
|`frozen_family_55076.csv`（恢复后）|basket2家族的全部55,076组；不是只有最优附近样本|
|`selected_comparisons.csv`|选择键×long/matched/later×0/5/10/20bps；选定策略独立账户|
|`family_summary.csv`|6个家族分别按开发期选出的参数、后段结果与家族分布|
|`phase_sensitivity.csv`|主2只和固定5只候选，在matched/later的5个独立相位|
|`annual_selected.csv`|原程序产生的long账户年度收益；不能冒充后段现金重置年度收益|
|`annual_later_reset.csv`|从已冻结selected_paths和benchmark_paths重算的后段重置年度收益|
|`top100_development.csv`|按开发期排序的前100个方案；后段未参与排序|
|`selected_paths.npz`|已选账户10基点日净值，键为`选择键__时期`|
|`benchmark_paths.npz`|10基点基准日净值，键为`时期__基准名`|
|`trades/*-trades.csv`|入场日、离场日、代码、单笔扣费收益、实际持有交易间隔|
|`development_frozen_choice.json`|前段选参记录，归档原文|
|`analysis_summary.json`|候选、目标比较和全网格约束汇总|
|`source_manifest.json`|800个原CSV的SHA256、行数、末日|
|`meta.json`|固定代码顺序、日历日期及共同索引|

## 完整结果中的键和前缀

`n`流动性窗口；`m`动量分母间隔；`mode`见交易规则；`bps`为单边基点，0.1%=10bps。新网格排除期固定5，不作为完整结果键中的变化维度。

- `full_*`：1991-03-11起始，2025-12-31终点的连续账户。
- `dev_*`：同一连续账户在2015-12-31以前的估值指标；开发期选择只使用其中cagr与sharpe。
- `matched_running_*`：连续账户从1993-01-29归一化后的描述指标，**不是现金重置**。
- `later_*`：2015-12-31现金1重置后账户的指标。
- 选定结果的 `period=long/matched/later`：均按对应时期另行模拟；matched是现金重置，可用于正式同期SPY比较。

## 指标

`cagr`为日历年化；`total_return`为W终/W初−1；`max_drawdown`为负的最大逐日回撤；`volatility`为日样本标准差×√252；`sharpe`为无风险利率0的年化算术日均收益/年化波动；`final_nav`为终点净值比。

**比例均按小数存储。** 日收益、年收益、波动与回撤同理。`excess_cagr_pp`已乘100，为百分点；`bps`是基点整数。

## 账户统计

|字段|含义|
|---|---|
|buys|股票/批次成功入场次数|
|trades|已完成股票往返次数|
|wins|扣费往返收益严格大于0的笔数|
|sum_trade_return|各股票扣费往返收益之和；不是账户总收益|
|delayed_exits|已完成但晚于目标日卖出的笔数|
|missing_entries|无法成交而保留现金的预算份额次数|
|max_lots|最多同时lot数，daily1同一代码不同批次分开计|
|max_distinct|最多不同代码数|
|terminal_lots / terminal_value|终点尚未平仓的lot数/标记价值|
|holding_days_sum / max_holding_days|完成往返的交易间隔合计/最大值|
|stale_marks|持仓估值使用旧标记的lot×日次数|
|minimum_cash|最低现金余额|
|max_exposure|最大1−现金/净值|
|fees_paid|账户绝对净值单位的累积已付费用，不是年化费率|
|cohorts|获得轮换许可并分配预算的批次数|
|blocked_renewals|因旧仓未清而阻止的轮换机会|
|later_terminal_lots / later_max_lots|后段重置账户对应统计|

完整网格大部分无前缀账户统计对应full账户。后段缺失/延期等详细控制以 `selected_comparisons.csv` 为准，不要把full统计误认成later统计。

## 选择键

`frozen_all`：开发期全家族最高净CAGR，n164/m99/basket2；`frozen_basket5`：5只家族开发期最优，n184/m197；`frozen_daily1`：每日轮换家族开发期最优，n21/m94。

`full_descriptive`：按全历史看过之后最高的n187/m99/basket2，只作事后诊断；`original5`与`original_same_cap`：n200/m252/skip21，分别持有5只和2只。
