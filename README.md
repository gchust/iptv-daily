# IPTV Daily · 每日实测直播源

每天自动收集公开直播源，读取真实音视频，筛除失效、黑屏、静音、冻结画面和部分播出限制提示，再提交通过检测的列表。重点覆盖中国地方台，同时收录检测通过的央视、卫视等频道。可用于 nTv / NativeWasmTv 及其他支持 M3U、TXT 的播放器。

[每日刷新任务](https://github.com/gchust/iptv-daily/actions/workflows/refresh.yml) · [最近检测报告](reports/summary.md) · [机器可读状态](reports/status.json)

## 直接订阅

| 内容 | M3U | TXT |
|---|---|---|
| 全部通过检测的频道 | [all.m3u](https://raw.githubusercontent.com/gchust/iptv-daily/main/playlists/all.m3u) | [all.txt](https://raw.githubusercontent.com/gchust/iptv-daily/main/playlists/all.txt) |
| 地方台合集 | [regional.m3u](https://raw.githubusercontent.com/gchust/iptv-daily/main/playlists/regional.m3u) | [regional.txt](https://raw.githubusercontent.com/gchust/iptv-daily/main/playlists/regional.txt) |
| 湖北地方台 | [hubei.m3u](https://raw.githubusercontent.com/gchust/iptv-daily/main/playlists/hubei.m3u) | [hubei.txt](https://raw.githubusercontent.com/gchust/iptv-daily/main/playlists/hubei.txt) |
| 武汉 / 江夏 | [wuhan.m3u](https://raw.githubusercontent.com/gchust/iptv-daily/main/playlists/wuhan.m3u) | [wuhan.txt](https://raw.githubusercontent.com/gchust/iptv-daily/main/playlists/wuhan.txt) |

在 nTv 网页管理中进入“频道配置 → 添加网络地址/添加源地址”，填入上述 raw 地址，启用并刷新频道列表。订阅地址固定，内容随每天检测结果更新；电视端也需要刷新才能取得新列表。GitHub raw 在部分网络可能访问缓慢，可使用自己的可访问镜像或本地上传。

## 每天如何更新

- 默认北京时间每天 **06:23**（UTC 22:23）触发，也可在 Actions 页面手动 Run workflow。GitHub 定时任务可能排队、延迟，不能保证精确到分钟。
- 从 [config/sources.json](config/sources.json) 中启用的多个上游实时拉取候选，并合并 [data/custom.m3u](data/custom.m3u) 中的自定义频道。初始自定义列表包含人工核对过的武汉及其他地方台，它们每天仍需重新通过检测。
- 按 URL 去重，保留签名查询参数，并剔除可识别的广播、景区慢直播及演员电影轮播，避免混入地方台。默认每轮最多检测 **1600 个候选URL**，从 **17 个上游**收集候选。优先检查湖北经视的所有候选（最多128个）、自定义及上一轮通过的源，并为湖北地方台预留检查名额，上游临时不可达时会把该上游上次通过的URL加入本轮重新检测，绝不直接作为已验证结果；其余候选按日期轮换，地方台约占发现名额的三分之二。不是每天穷举整个互联网；可以调整上限。
- HLS 检查实际媒体清单、媒体分片链接及清单是否持续推进，排除结束的点播清单。
- FFmpeg 必须实际解码 **20 秒媒体内容**、有足够视频帧和非静音音轨；仅 HTTP 200 不算通过。遇到失败或超时会按配置重试一次。
- 自动剔除至少3秒黑屏、至少6秒冻结画面、明显解码错误。GitHub Actions 还使用中文 OCR 检测“暂不支持播放”“版权限制”等提示。
- 同一频道有多个通过源时，优先清晰度，再比较本次检测耗时；发布一个主源。通过的备选及失败原因保存在 [reports/latest.json](reports/latest.json)。
- 正常更新只发布**本轮通过**的源，旧源不会因历史成功而自动混入。若整轮零通过，保留上次成功列表并将状态标记失败，记录最后成功时间，Actions 报错；这时旧列表不能被当作当天验证通过。
- 所有分片均完成、URL数量完整、候选清单指纹一致、中文OCR已启用，才汇总发布。任一分片未完成或结果来自旧任务时，工作流报错并保留原列表；不会发布只测了部分候选的新列表。
- 列表和报告由 GitHub Actions 自动提交到 main，commit message 使用英文。无须个人访问令牌，工作流使用仓库自带、仅限该仓库的 GITHUB_TOKEN 写入权限。

## 如何增加频道和上游

1. 添加或修改 data/custom.m3u，保留标准 EXTINF 频道名和分组；直播URL写在下一行。
2. 或在 config/sources.json 添加一个公开的 M3U/TXT 上游地址。当前接入 iptv-org、CCSH、Collect-IPTV、doubwing、米奇TV、githubhc20、okay、maowei湖北电信、iptvjs、suxuang、Meroser、Hengstchon、CHINA-IPTV、Akira、reysc 等仓库/列表；上游名称只代表候选来源，不代表其中每路都能播放。支持 M3U 的 group-title 及 TXT 的“地区,#genre#”分组。
3. 在 Actions → Refresh live TV → Run workflow 手动执行，或等待每日任务。
4. 在 reports/summary.md 查看通过的地方台；在 reports/latest.json 查看逐源失败原因。

地域分类主要依据频道名和分组，不能自动证明频道身份。名称无法识别的源归入“其他”；可通过自定义列表设置“湖北”“浙江”等分组。自定义源同样接受检测，不会强行发布。

## 配置和本地运行

修改 config/settings.json 可设置检测上限、并发数、样本长度、单次FFmpeg超时和重试。priority_channels 是优先频道（现为湖北经视），priority_regions 是优先地区（现为湖北），shards 是云端检测分片数。每日任务先收集一次并冻结候选清单，再按主机分为4个并行检测任务，每个任务并发8。同一主机只分配给一个任务、最多2路同时检测；中文OCR最多并发2个且每个只用一个计算线程，避免集中请求。脚本仅依赖 Python 3.10+ 标准库及 FFmpeg。中文 OCR 需要 Tesseract 的 chi_sim 和 eng 语言包。

    python -m unittest discover -v
    python scripts/update.py --require-ocr
    python scripts/update.py --limit 300 --workers 6
    python scripts/update.py --custom-only

没有中文 OCR 时本地可运行基础检测，reports/status.json 会记录 ocr_enabled=false；每日 Actions 使用 --require-ocr，缺失OCR工具时会失败而不降低检测标准。

如果 GitHub 托管机器无法访问中国境内或运营商专网的源，可以在实际观看的家庭网络运行同一个脚本。需要家庭网络每日检测时，可将工作流改为你管理的 Linux self-hosted runner，并安装相同依赖；本项目没有自动安装或暴露任何本地 runner。

## 判断“可用”的边界

检测结果只说明某条URL在**这次检测环境、这20秒样本**内通过技术检查，不能保证全天、所有地区和所有电视都可播放。检测不能修复上游服务，也不会绕过地区、运营商、付费或鉴权限制；带签名的URL仍可能过期。每日拉取上游有机会取得更新后的地址，但上游不更新时无法自动凭空生成新地址。

OCR、黑屏、静音和冻结筛选有误判可能，正常静态节目、短暂转场也可能被严格剔除；动态提示画面或频道名不符也未必能被自动识别。因此这里不作“永久可用”或“每路内容身份完全核实”的承诺。请查看最后成功时间，并以电视端实际播放为准。

GitHub 的公开仓库在长期没有活动时可能暂停定时工作流，详见 [schedule 文档](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)。仓库每日成功更新报告会产生提交；仍建议偶尔检查 Actions 是否持续运行。

## 数据与授权

本项目不托管节目视频，只保存公开地址、来源出处和短时技术检测结果。使用者应遵守原始服务的条款和当地适用规则；请勿添加私密凭据、内部地址或未获授权的付费源。代码使用 MIT 许可；第三方流地址、节目内容和频道标识不因本代码许可而获得转播授权。
