# 复现、文件恢复与原始输入

## A. 查看与核查已发表结果

克隆本私有仓库后，在仓库根目录运行：

```sh
python3 research/scripts/restore_archives.py
```

脚本核对每个分块的SHA256，按顺序重组、核对归档SHA256，再恢复到 `research/restored/`。不覆盖不同内容的已有文件，不执行下载文件或远程脚本。恢复项目包括：

- `all_660912_cost_results.csv.gz`：全部0/10基点费用结果。
- `全部330456种组合_单边10基点.csv`：全部净结果的中文精简表。
- `frozen_family_55076.csv`：主家族完整网格。
- `完整交互报告.html`：原自包含交互报告，包含图表和查询数据。

比率字段以小数保存，CSV不会仅保留最优或前100名。完整字段见数据字典。用浏览器打开恢复后的HTML；如浏览器限制本地脚本，可在restored目录运行 `python3 -m http.server 8835`，再访问 `http://127.0.0.1:8835/完整交互报告.html`。此报告为本次冻结证据，不是自动接入新行情的生产服务。

仓库可读Markdown、图表、关键CSV和验证回执无需恢复即可查看。原始数值文件保持不变；中文文档、数据字典、年度重置表与归档工具属于本次整理新增材料。

## B. 完全重算需要什么

1. 原800份CSV，字段包含date、open、close、adj close、volume；对应名单与指纹在data目录。
2. 原冻结SPY Yahoo chart JSON的gzip，指纹见 `results/benchmark_receipt.json`。该文件并非由代码从网络自动重新抓取；更新后的行情不一定与已发表快照相同。
3. Linux、支持OpenMP的C++17编译器、Python数据依赖和能在RTX5090运行的PyTorch CUDA环境。
4. 足够空间保存派生矩阵、候选池、全部n的有序Top5索引和统计；这些大型中间文件没有随仓库分发。

原始行情及第二份快照没有上传到此仓库。原研究完整工作目录保存在Olliee Ubuntu；不能只靠恢复输出文件就宣称重新运行过原始数据计算。

## C. 原运行环境记录

|环节|实际记录|
|---|---|
|GPU|NVIDIA GeForce RTX5090，32GB|
|数值环境|Python3.12.13、NumPy2.4.4、pandas3.0.5、torch2.13.0+cu132、CUDA13.2|
|准备日历环境|Python3.11.15、exchange_calendars4.11.2|
|账本编译|g++15.2，C++17，OpenMP，8线程|
|排名|GPU float64，稳定ticker并列顺序|
|账本|CPU编译程序逐日现金/lot模拟；不是把全部交易模拟声称为GPU执行|

这是原机器环境记录，不是所有版本都已在其他机器验证的可移植性承诺。GPU代码明确要求设备名称包含5090，并设进程显存比例0.024；其他GPU或共享显存状态需要新环境验证。未为归档修改这些数值源文件。

## D. 安全建立独立重跑目录

归档原程序的prepare.py包含原机器输入路径。为保留原件，新增stage_inputs工具会复制代码和输入到**全新空目录**，通过导入时设置SOURCE选择输入，并预放SPY；不改动归档源码，也不在仓库结果目录直接重算。

使用安装了NumPy、pandas和exchange_calendars的数据Python：

```sh
python3 research/scripts/stage_inputs.py \
  --workspace /absolute/new-a800-run \
  --csv-dir /absolute/800-csv-directory \
  --spy-json /absolute/SPY.json.gz \
  --require-original-hashes
```

`--require-original-hashes`要求800份CSV及SPY全部与发表快照一致。若有意研究更新数据，可省略，但须将结果标成新快照；仍要求精确800个代码。脚本会记录不同的指纹。prepare对末日2025-12-31的断言仍保留，更新到其他末日需要新研究版本，不能静默继续旧协议。

然后进入新工作目录，使用可运行CUDA的数值Python：

```sh
cd /absolute/new-a800-run
g++ -O3 -march=native -fopenmp -std=c++17 code/book.cpp -o code/book
python3 code/gpu_core.py pools
python3 code/tests.py
python3 code/run_grid.py
python3 code/benchmarks.py
python3 code/freeze_choice.py
python3 code/analyze.py
python3 code/export_compact.py
```

`freeze_choice.py`只读取dev_cagr/dev_sharpe及n/m/mode排序；已有冻结选择不同会报错。`run_grid.py`有progress、pool状态及中间索引续跑。**输入或规则变化时必须使用新工作目录，不能复用旧缓存。** 原prepare生成的archive使用硬链接，不应编辑或chmod这些输入链接。

原 `audit_raw.py`还需要此前2466研究的第二份快照，包含机器绝对路径。若要复现561笔交叉快照核对，必须另取得那份冻结矩阵并在独立副本中配置路径。缺少第二快照不阻止主回测，但不能声称复现了交叉审计。

原研究的5个合成场景、270个GPU/CPU排序样本、7条独立逐日路径，以及原CSV1,004笔成交核对，其已执行回执原样保留在results。新归档脚本的输入检查不替代这些计算检验。

## E. 数值代码对应的工作

|源文件|职责|
|---|---|
|prepare.py|读800份CSV、对齐XNYS、生成资格与复权价矩阵、冻结指纹|
|gpu_core.py|GPU流动性候选池、动量Top5、有序并列处理|
|book.cpp|6家族逐日现金/持仓、费用、缺失报价、相位与风险指标|
|run_grid.py|全部n/m、两费用、长历史与后段重置计算|
|benchmarks.py|3类买入持有、相同费用与日期、基准日净值|
|freeze_choice.py|仅开发期选参并写入/核对冻结选择|
|analyze.py|选定候选的4费用、同期重置、5相位、独立Python复算与汇总|
|audit_raw.py|原CSV及第二快照成交核对|
|export_compact.py|330,456行中文结果导出|
|tests.py|合成账本、并列及真实排序独立检验|

本仓库没有交易下单、账户资金连接、自动实盘或替换生产策略的程序入口。
