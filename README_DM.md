# 达梦

dm8.iso从 https://www.dameng.com/download/ 选择合适系统下载解压出来就有这个文件了，放到项目里面就行
```shell

# 测试打包（dmpython 这些安装可以参考 dockerfile）
docker build --platform=linux/amd64 -f Dockerfile.dameng -t schemarag-dameng:latest . 
# 测试允许
docker run --rm --platform=linux/amd64 -v "$PWD":/app schemarag-dameng:latest
```
