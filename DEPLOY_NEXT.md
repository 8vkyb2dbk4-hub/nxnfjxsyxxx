# 正式部署步骤与当前状态

本项目由用户提供的 v9 ZIP 直接修复，保留原有布局和模块。

## GitHub Pages
1. 在 GitHub 创建仓库，将本目录作为仓库根目录推送至 main。
2. Settings → Pages → Source 选择 GitHub Actions。
3. Settings → Actions → General 允许工作流读写仓库。
4. 执行 Tests 和 Deploy Pages；每日任务北京时间约 07:10 运行。GitHub 定时任务可能延迟，不能保证精确到分钟。
5. Daily AI Brief 完成后通过 workflow_run 发布更新，避免机器人提交不触发 push 工作流的问题。

## Supabase
1. 创建 Supabase 项目，执行 db/supabase_schema.sql（可重复执行）。
2. 在 GitHub 仓库 Variables 设置 SUPABASE_URL、SUPABASE_ANON_KEY（仅公开 anon 或 publishable key）。不要放入 service_role 或 secret key。
3. 在 Supabase Auth 配置网站 URL、邮件确认与允许的重定向地址。登录采用邮箱密码；开启邮件确认时注册后须先确认邮件。
4. 重新运行 Deploy Pages，进入“同步”登录同一账号。
5. 第一次登录导入当前匿名本地数据；退出后保留独立账号快照，其他账号不会自动继承上一个账号的数据。

## 验收
电脑、iPhone Safari、iPad Safari 分别登录相同账号：各自添加不同收藏、标记已读、增删观察词、切换阅读模式与学习偏好。等待同步或点击立即同步；关闭页面重开检查一致性。
先在线打开完整页面，再断网重载；检查可阅读、收藏和模式仍可修改。恢复网络后同步。云端 500 或网络错误必须保留本地修改。
使用两个专用测试账号运行 tests/test_rls_live.py，环境变量名称见文件开头；禁止使用 service_role 进行 RLS 验收。
真实 iOS Safari/PWA、真实 RLS、邮件注册与线上定时更新尚未验收；本地设备尺寸模拟不等同于真机测试。

## 本地启动与测试
安装 Python 3.12+、Node 22+。运行 pip install -r requirements.txt，然后 python serve.py。
测试：python tests/test_quality.py；python tests/test_trends.py；node tests/test_sync.js；node tests/test_sync_integration.js。
浏览器测试：安装 playwright 并安装 Chromium，先 python scripts/build_static.py，再 node tests/test_browser.js。可通过 BROWSER_EXECUTABLE 指定现有 Edge/Chrome。
静态发布目录由 python scripts/build_static.py 生成 dist/；不发布数据库脚本、测试与开发工具。

## 合并规则与限制
收藏、已读、观察词逐项时间戳合并；同时间戳采用确定性规则。学习结果和 UI 偏好仍按 v9 整体时间戳合并，不合并两个设备同时进行的学习增量。设备时间应准确。
云写入采用数据库原子 revision 检查，冲突后重新读取合并重试；上传期间新产生的本地修改保留并补同步。
本地账号快照适用于个人设备，不提供共享电脑上针对同一浏览器使用者的保密保证。
