# FindRealSubs

泛解析子域名爆破命令行版。

## 用法

```powershell
FindRealSubs.exe -d example.com -w subdomains.txt [选项]
FindRealSubs.exe -df domains.txt -w subdomains.txt [选项]
```

## 参数

```text
-d,  -domain        目标根域名，多个可用逗号/空格/换行分隔
-df, -domfile       目标域名文件，一行一个；可替代 -d
-w,  -wordlist      子域名字典文件，必填
-c                  并发数，默认 80
-t,  -timeout       HTTP/DNS 超时时间，单位秒，默认 3
-r,  -retries       DNS 重试次数，默认 1
-m,  -samples       泛解析随机样本数量，默认 5
-dns                DNS 服务器，逗号分隔
-o                  结果输出文件
-sf, -show-filtered 显示被泛解析过滤的抽样日志
-j,  -json          输出 JSON 报告
-h                  显示帮助
```

## 输出格式

```text
发现：http或https子域名地址，标题：xxx；长度：xxx；状态码=200
```
