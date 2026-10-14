# Windows 使用说明

照着下面做就能在自己的 Windows 电脑上一直运行价格监控。所有操作都是**双击文件**，不需要输入命令。

## 0. 第一次之前：安装 Python（只需一次）

1. 打开 https://www.python.org/downloads/windows/ ，下载最新的 Python（3.10 以上即可）
2. 运行安装程序时，**一定要勾选最下面的 “Add python.exe to PATH”**，然后点 “Install Now”

## 1. 安装

双击 **`setup.bat`**。第一次需要几分钟，看到 **`SETUP OK`** 就好了。

> 为了在中文版、日文版 Windows 上都不出乱码，这些 .bat 窗口里的提示都是英文。

## 2. 导入你的价格表

1. 双击 **`start.bat`** 启动（会出现一个黑色窗口，显示 `pricewatch is RUNNING`。**不要关掉它**，关掉就停止监控）
2. 双击 **`open.bat`**，浏览器会打开监控画面
3. 点上方的「監視対象」→「一括登録」，选择你现在的 Excel 表格 → 「読み込む」
   - 表格里需要有「販売商品URL」这一列（你现在的表格就有）；「サイト」「店舗」「商品名」「アラート価格1/2」也会一起读进来
   - 价格.com 的行，「店舗」一定要写对，程序靠店铺名在价格.com 页面里找对应那一行
4. 点上方的「今すぐ確認」，等几分钟，表格里就会出现价格

> **第一次请核对一下**：把画面上的价格和实际网页上的价格对一下。取不到的（空白）或者不对的，
> 把那一行的 URL 发给 Claude 来修。也可以双击 `check-now.bat`，黑色窗口里会显示每一行的结果和原因。

## 3. 设置成开机自动运行

双击 **`autostart-on.bat`**。

- 以后登录 Windows 后会自动启动（窗口最小化在任务栏）
- 它会用英文问你要不要「插着电源时不睡眠」（Also stop this PC from sleeping...），**建议按 Y**，电脑睡眠时监控会停止
- 不想自动启动了：双击 `autostart-off.bat`

另外建议在 Windows 设置里打开**自动登录**或者不要注销，否则开机后要先登录才会开始监控。

## 4. 设置通知和密码（可选）

用记事本打开 **`.env`** 文件（如果看不到，在资源管理器的「查看」里勾选「文件扩展名」和「隐藏的项目」）。

| 设置 | 说明 |
| --- | --- |
| `PRICEWATCH_INTERVAL=60` | 每隔几分钟检查一次 |
| `SLACK_WEBHOOK_URL=` | 填 Slack 的 Webhook 地址，价格变化时发到 Slack |
| `LINE_CHANNEL_ACCESS_TOKEN=` / `LINE_TO=` | 发到 LINE（需要 LINE Official Account 的 Messaging API） |
| `SMTP_HOST=` 等 | 发邮件（Gmail 的话用「应用专用密码」） |
| `PRICEWATCH_PASSWORD=` | 打开画面时要求输入密码（用户名随便填） |
| `PRICEWATCH_HOST=0.0.0.0` | 允许家里的手机/其他电脑打开画面（请同时设置密码） |

改完保存，关掉 `start.bat` 的黑色窗口，再双击 `start.bat` 重新启动就会生效。

### 在家里的手机上看

1. `.env` 里设置 `PRICEWATCH_HOST=0.0.0.0` 和 `PRICEWATCH_PASSWORD=你的密码`，重新启动
2. 第一次启动时 Windows 防火墙会弹出提示，选「允许」（专用网络）
3. 在这台电脑上打开命令提示符输入 `ipconfig`，找到「IPv4 地址」（例如 192.168.1.23）
4. 手机连同一个 Wi-Fi，浏览器打开 `http://192.168.1.23:8000`

在外面也想看的话，推荐安装免费的 **Tailscale**（电脑和手机都装），不需要改路由器设置。

## 5. 数据和备份

- 所有价格记录都在 `data\pricewatch.db`
- 每天自动备份到 `data\backups\`（保留最近 30 天）。建议偶尔把这个文件夹复制到云盘
- 运行日志在 `data\server.log`，出问题时把最后几十行发给 Claude

## 6. 更新程序

- 如果是用 `git clone` 下载的：在文件夹里打开命令提示符，运行 `git pull`，然后再双击一次 `setup.bat`
- 如果是下载 ZIP 解压的：下载新的 ZIP，**把旧文件夹里的 `data` 文件夹和 `.env` 文件复制到新文件夹**，然后双击 `setup.bat`

## 常见问题

| 现象 | 处理 |
| --- | --- |
| 双击 setup.bat 说找不到 Python | 重新安装 Python，并勾选 “Add python.exe to PATH” |
| open.bat 打开后显示「无法访问此网站」 | `start.bat` 没有在运行，先双击它 |
| 黑色窗口显示 `pricewatch STOPPED` | 窗口里会显示 `data\server.log` 的最后几行，截图发给 Claude |
| 某些行一直是空白 | 那个网站没取到价格，用 `check-now.bat` 看原因，把 URL 发给 Claude |
| Amazon 一直取不到 | Amazon 拦截很严格，见 README 的「Amazon」说明 |
