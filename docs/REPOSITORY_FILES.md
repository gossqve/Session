# S0–S3 文件保留与发布规范

服务器同步与 GitHub 使用逐文件白名单：[server_files.txt](../release/server_files.txt)、
[github_files.txt](../release/github_files.txt)。两份列表当前内容相同，均为仓库相对路径，
没有目录或通配符。新增正式文件后需人工审查并分别补入列表；新增 S3/S4/S5 结果不会自动进入发布包。
白名单限定发布范围，不代表已提交 Git，也不证明所有私有内容已经过公开许可审查。

## 分类与保留

| 类别 | 路径 / 用途 | GitHub 与服务器 |
|---|---|---|
| 正式运行依赖 | `src/**/*.py`、`configs/*.json`、`pyproject.toml` | 白名单保留 |
| 测试依赖 | `tests/**/*.py`，含独立 Oracle `max_min_oracle.py` 和代码内 fixtures | 白名单保留 |
| 必需回归基准 | `docs/s1d_verification.json`，由 `verify_s1e.py` 实际读取 | 特例保留原路径、原内容 |
| 权威与必要文档 | `docs/model_spec/**/*.md`、README、AGENTS、本文件、ARCHITECTURE | 白名单保留 |
| 可复现脚本 | `scripts/*.py`，含验收、压力、Oracle 审计与发布检查 | 白名单保留 |
| 纯输出 | `runs/`，各阶段 verification JSON、测试 stdout/stderr、trace、配置输出副本 | 只在本地，忽略 |
| 历史审计 | `docs/` 下阶段报告、开发计划、旧上传/修改/删除清单；本轮审计报告 | 只在本地，忽略 |
| 临时缓存 | `__pycache__/`、环境、构建物、临时目录、压缩包、权重 | 只在本地，忽略 |

`docs/model_spec/` 中原始 Markdown 与历史修订一起保留建模出处；当前有效优先级由该目录
README 说明。模型正文中的旧阶段规则不能覆盖用户最新约束。
当前优化目标原稿为
`docs/model_spec/2026-11-07-weighted/Section_III_E_Problem_Formulation_加权时延与开销_精简修订稿_2026-11-07.md`，
按用户原稿字节保留；2026-11-06 两份完整主文仅在 E 标题后增加过时标记，A–D 未改。
来源、SHA-256、权威顺序及旧文档历史属性见 [model_spec/README.md](model_spec/README.md)。
新增正式原稿、随机测试 helper/入口和验收脚本均须逐项审查并补入两份发布白名单；
只发布显式文件，不包含本地来源目录、失败样例或随机测试输出。
`docs/s1d_verification.json` 中旧运行目录只是来源字符串，不需要同步那些历史运行目录。
其余阶段审计 JSON 均不是输入。不要按扩展名一概忽略 JSON，也不要删除真正的测试 fixtures。
将来新增 fixtures 应显式加入白名单并检查 Git 忽略状态。

## 本地检查与打包

在仓库根目录执行；以下命令不访问服务器、不暂存 Git：

```powershell
python scripts/prepare_release.py --target server
python scripts/prepare_release.py --target github
python scripts/prepare_release.py --target server --package
python -m unittest discover -s tests -v
python scripts/verify_s2c.py
```

包仅含服务器白名单中的文件，输出到全新 `runs/release_packages/session_server_*.zip`，
打包后检查 ZIP 文件表和 CRC。服务器只接收这个来源包中的输入；验收在服务器生成自己的新 runs。
脚本拒绝绝对路径、越界、目录、重复、缺失、符号链接及非批准类型。不要直接上传整个仓库目录。
同步不自动删除服务器旧文件；以前清理阶段已经移除的根转发模块仍需用户单独审核处理，不能恢复。

GitHub 提交前将白名单与 `git status --short -uall`、`git ls-files` 和暂存 diff 对照，
只选择列表里的文件。不要用无范围的 `git add .` 代替审核；忽略规则不能撤销已跟踪文件，
也不能阻止人为强制添加。若输出已被跟踪，先列明路径、保留本地副本，并由用户批准后另行处理索引。
本次审计未执行索引删除、暂存、提交或远程操作。

## 后续阶段规则

`.gitignore` 在仓库根和 docs 采用默认排除、逐项开放规则；常见结果、缓存与权重也在子目录排除。
正式源码、配置、测试目录保持可见。所有新实验、训练、评估和审计产物写入 `runs/<stage>_<unique>/`，
不得将其放进 `src/`、`configs/`、`tests/` 或权威文档目录。新增阶段代码只有审查后才补白名单。
白名单刻意不自动扫描扩充，避免把结果副本当成正式输入。

复现入口与模块职责见 [ARCHITECTURE.md](ARCHITECTURE.md)。本地阶段报告可供研究审查，
但正式复现不能要求这些报告、日志、旧 runs 或历史上传清单存在。
测试临时文件使用各自创建的系统临时目录；CLI 输出由写入模块创建父目录。
随机失败的配置、Trace、Seed 与复现命令属于本地 `runs/` 诊断产物，不是测试 fixture。
干净环境验收使用按白名单复制的独立临时副本，排除 `.git`、`runs/`、环境与缓存，
不删除当前工作区历史结果。S3 本轮收尾后冻结，S4 尚未设计、尚未实现，S5 未开始。
