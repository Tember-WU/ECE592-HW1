# Sunbird Section 8.5

[hitrate01 中文报告与失败分析](hitrate01/SUNBIRD_NOTES.md)：54 次串行百万样本采集全部完成。
冻结阈值 70 TSC ticks；同次执行平均绝对误差 26.882 pp，最差 96.692 pp。
数据完整性校验通过，但原算法在 48/128 KiB 负载上出现严重错误分类。

[原流程报告](hitrate01/RUN_NOTES.md) · [逐重复对照](hitrate01/comparison.csv) ·
[执行审计](hitrate01/execution_audit.json) · [图](hitrate01/figures/)
