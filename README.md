# Android 面试学习笔记

公开的 Android 高级面试 8 周系统复习笔记，内容覆盖 Kotlin 基础、协程、Android Framework、Jetpack、架构与性能优化。

本仓库是独立公开学习站，内容源自私有知识库中**已审校确认**的文章，按 [Kotlin 官方文档](https://kotlinlang.org/docs/home.html) 核验。仅导出公开文章，不含知识库的原始来源、维护日志、进度协议、项目资料或任何私有内容。

## 内容

- Week 1（Kotlin 基础）：Day 1～Day 7
- Week 2（协程与 Flow）：Day 8～（连载中）

后续课程完成后按篇增量发布。

## 本地预览

```bash
python scripts/build.py
# 用任意静态服务器打开 dist/
python -m http.server -d dist 8000
```

构建只依赖 Python 标准库，无第三方依赖。

## 目录结构

```
posts/          # Markdown 源文章（Day 1～7）
templates/      # 页面模板（可选，当前内嵌在 build.py）
assets/         # 静态资源（CSS）
scripts/
  build.py      # 纯静态构建脚本
.github/
  workflows/
    deploy.yml  # GitHub Pages 部署工作流
dist/           # 构建产物（gitignore，由 Actions 生成）
```

## 发布协议

每篇文章发布前都经过：白名单检查、敏感信息扫描（密码 / Token / Cookie / 私钥 / 本地绝对路径 / 对话提示词）、本地构建验证。新增公开文章需获得明确授权。

## 许可

内容仅供学习交流，引用请注明来源并以 Kotlin / Android 官方文档为最终依据。
