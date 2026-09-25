# 湖北经视专项核验（2026-09-25）

结论：找到并确认两条湖北经视线路。其中第二条通过北京时间 2026-09-25 23:16:23 完成的 GitHub Actions 专项检查，已发布在重点频道订阅。**短时可以播放，但还不能称为稳定无损线路。**

## 可以添加的订阅

- [重点频道 M3U](https://raw.githubusercontent.com/gchust/iptv-daily/main/playlists/priority.m3u)
- [重点频道 TXT](https://raw.githubusercontent.com/gchust/iptv-daily/main/playlists/priority.txt)
- [逐路检查报告](priority.json)
- [本次成功的云端运行](https://github.com/gchust/iptv-daily/actions/runs/36152869207)

当前收录：湖北经视，720×576 标清；URL 为 http://58.19.32.207:4022/rtp/239.254.96.178:9148 。这是经 HTTP 转发的实时电视流，路径里的 rtp 不代表需要在播放器中改用 rtp 协议。

专项订阅与原先大列表独立记录检测时间。本次没有改写大列表的历史检测结论；新候选及两个上游已接入每日完整检测，下一轮完整检查通过后才能进入 all / regional / hubei 列表。

## 频道身份与来源

1. [jmheqiao/i-p-t-v 原始列表](https://github.com/jmheqiao/i-p-t-v/blob/fba192f80bac6ec454f0e11d2390caf88a095ebd/py/live.txt) 将该地址标注为“湖北经视频道”；实际抽帧可见“湖北经视”台标及《桃花朵朵开》节目。已修正别名归并，避免优先筛选漏掉“湖北经视频道”。[台标截图](evidence/hubei-jingshi-second-2026-09-25.jpg)
2. [huaxiong96/TVBOX 原始列表](https://github.com/huaxiong96/TVBOX/blob/065a0fd1ad51aa1f1f54b45cf0c9c06cbba9705e/IPTV/湖北电信组播.txt) 提供另一条 hiliu.myds.me 线路。多个画面同样确认湖北经视身份。[多时点截图](evidence/hubei-jingshi-2026-09-25.jpg)

## 播放证据及局限

| 线路 | 本地20秒 | 本地180秒 | 最新云端60秒 | 本轮发布 |
|---|---|---|---|---|
| 58.19.32.207:4022 | 通过 | 有画面声音，无检测到的黑屏/冻结，但出现坏包及解码错误 | 59.98秒、1494帧、非静音音轨，零已记录解码错误，中文OCR通过 | 是 |
| hiliu.myds.me:18088 | 通过 | 同样出现坏包及解码错误 | HTTP 503 Client limit reached | 否 |

180秒延长测试的失败结果完整保存在 [发现报告](hubei-jingshi-discovery-2026-09-25.json)，没有被短样本成功覆盖。可播放、台标确认、短样本通过和长期稳定是不同结论；电视端表现还取决于家庭网络。此次没有放宽媒体检测标准。

此前的 207.56.13.146 广告流又采样了约10分钟媒体、取10帧；仍未见可确认频道身份的台标，继续隔离，不作为湖北经视发布。

## 自动维护

- 上游列表由20个增加到22个，增加上述两个公开来源。
- 每天北京时间06:23的完整任务继续筛选全部候选，并同步刷新重点频道订阅。
- 新增手动专项工作流，每路检测60秒并执行中文OCR；没有任何合格源时清空重点频道列表、记录失败，避免沿用旧成功伪装新结果。
- 实时状态见 [priority.json](priority.json)；固定订阅内容会随后续实测改变。本说明记录的是2026-09-25这一轮证据。
