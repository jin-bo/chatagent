# PowerShell 支持 —— 轻量方案（默认基础级，严格级选入）

> **本文是方案，不是规范。** 它不定义规则、不分配 ID，只引用规范里已有的 ID；被采纳之后，
> 它的每一条折入 `powershell-support-spec.zh.md` 并在那里分配 ID，本文随即降为历史。
> 规范描述「现在必须怎样」，本文描述「建议改成怎样」，两者不能同时是权威。
> **文件集：** 见 `powershell-support-spec.zh.md` 文件头。

**日期：** 2026-09-06 · **状态：** 初稿，未实施
**触发：** 评审记录 rev 53 的七条发现，其中五条由本方案消解（§7）。

## 1. 决定

**从当前 HEAD 做减法，不对 main 做硬回退。** 用户定案，2026-09-06。

不回退的理由是提交本身混着三样东西。PR #213（`3e08345`）一次带进了基础 PowerShell 支持、
严格认证策略，以及 Windows job 首跑抓出的那批缺陷修复 —— CRLF 写入、状态目录、sqlite、
会话、`os.replace`、ACP 窗口、内存关闭。第三样与 PowerShell 无关，整体回退会把它们一起丢掉。

`682bd3a`（PR #212）是**审查基线**，不是恢复目标：它停在大实现之前，适合用来对照
「哪些属于基础支持、哪些属于严格策略」，但它自己不含任何 Windows 缺陷修复。

**没有紧急压力。** 默认路径仍是 `%COMSPEC% /c`，严格阶梯要 `shell.ladder: true` 才走
（LADDER-05）。瘦身可以在独立分支做完、按 §8 验收完再合。

## 2. 三档，不是两档

今天 `ShellSpec.policy_enabled` 是一个布尔，而 SPEC-03 让它等于「rung 不在 `POLICY_OFF_RUNGS` 里」。
于是只有两种可能：关 = 今天的 cmd 加今天的正则地板；开 = 可信根、封闭集、认证、钉值环境，全套一起来。
中间没有任何东西，而「让 agentao 在 Windows 上正确使用 PowerShell」要的正是中间那一档。

提出把它拆成三档，并让**档位与 rung 正交**：rung 回答「选中了哪个解释器」（SPEC-02 本来就是这么写的），
档位回答「加多少政策」。

| 档 | 含义 |
|---|---|
| `legacy` | 今天的行为。Windows 上 `%COMSPEC% /c`，POSIX 上 `system_posix`。退路 |
| `basic` | **建议的新默认。** 方言正确、发现解释器、危险类地板、继承环境 |
| `strict` | 今天的政策开启级，一字不改，改为选入 |

| 能力 | `legacy` | `basic` | `strict` |
|---|---|---|---|
| 解释器发现（`auto` / `cmd` / `powershell`） | 否，恒 cmd | 是 | 是 |
| 按方言构造 argv、引用、编码、起始目录、退出码 | 今天的 | 是 | 是 |
| 前台与后台同一份启动请求（LAUNCH-01） | 是 | 是 | 是 |
| 提示词按方言渲染（PR-5） | 是 | 是 | 是 |
| 权限引擎与 hardline 地板 | 是 | 是 | 是 |
| 危险类地板按方言词法（`_windows` 危险表） | 否，跑 POSIX 正则 | **是** | 是 |
| 可信根链（IMG-01、IMG-06a） | 否 | 否 | 是 |
| 签名与 allowlist（IMG-03、IMG-05） | 否 | 否 | 是 |
| 精确 build 命令表（NAME-02） | 否 | 否 | 是 |
| 封闭集与效果标志（IMG-02、EFF-04） | 否 | 否 | 是 |
| PATH 过滤（ENV-01） | 否 | 否 | 是 |
| 钉值封闭子环境（ENV-06） | 否 | 否 | 是 |

## 3. basic 的地板：只因看见危险类而拒，绝不因读不懂而拒

这是本方案唯一一条**新的**判据，也是 `basic` 与 `strict` 的分界线。

两个扫描函数今天都是「先危险表、后可读性」，两半在源码里已经分开：

- `_powershell.py::scan_powershell` 先 `lower_powershell(body)`，再对每条降级出来的命令跑
  `_WINDOWS_DANGEROUS_COMPILED`。降级失败抛 `LoweringError`，函数把它变成一次拒绝。
- `_cmd.py::scan_cmd` 先跑 `_CMD_DANGEROUS_COMPILED`，再做 TOK-02 的动态 token 与 CMD-01 的
  控制关键字这两项可读性拒绝。

`basic` 只取前一半。降级失败或读不懂时**不拒绝**，回落到今天默认路径已经在跑的那张通用危险表，
也就是与 `legacy` 同强度 —— 因此 `basic` 在任何输入上都不比今天的默认更弱，只可能更强。

`strict` 保持原样：读不懂就是不透明，那是封闭集的前提，不是可以商量的严厉程度。

第三处改动在 `_scanner.py`：PowerShell 分支今天在 `scan_powershell` 没拒时返回
`hardline:powershell-opaque:EFF-04:closed-set analysis needs the decided record`。
`basic` 下这里改为落到通用 BFS，和 POSIX 分支现在的写法一致。

## 4. basic 的环境：不过滤 PATH

`basic` 沿用 `capabilities/process.py::build_child_env()` —— 继承整份环境再剥掉 provider 凭据，
也就是今天 POSIX 与今天 Windows 各自在做的事。

**这一条单独就决定了「能不能替我构建并测试项目」。** ENV-01 把 PATH 过滤成「子进程主体写不了」的
目录，而 Windows 上开发工具几乎都装在用户可写的位置：scoop、npm 全局、cargo、pyenv、uv，
以及项目自己的虚拟环境。过滤之后裸 `node`、`python`、`uv`、`gh` 一律解析不出来。

两条便宜且不限制用户的守卫**保留**在 `basic` 里：ENV-04 的 `NoDefaultCurrentDirectoryInExePath`，
以及 LAUNCH-09 的「子进程以 launcher 自己所在目录为起始目录，再由前奏 `cd -P` 切到工作目录」。
它们挡的是工作树里的同名 DLL 抢在前奏之前被加载，代价是零。

## 5. 提权在 basic 下不再是问题

`basic` 不问 IMG-01，所以提权 token 的可信集为不为空与它无关，阶梯也不会走空。
证据 §3.23 那条「提权的 Windows token 可信集为空、LADDER-03 拒掉每一次 shell 调用」
只对 `strict` 成立。

由此，`strict` 的选入路径欠一件东西：选入时若当前 token 已提权，必须当场说明这一级对它不可用，
而不是让用户在第一次 shell 调用时收到一个没有上下文的拒绝。这是 rev 53 第 2 条在本方案下的余量。

## 6. 平台重新对称

规范 §7 的 q4 定的是 `system_posix` 维持政策关闭，TOK-02、EFF-\*、IMG-02 只在 Windows 的政策开启级生效。
`strict` 一旦不是默认，Windows 的默认强度就与 POSIX 的默认强度相当：两边都是危险类地板加继承环境。
今天那种「同一个模型、同样的注入面、两套标准」的不对称随之消失。

## 7. 与评审记录 rev 53 七条的对应

| rev 53 | 本方案 |
|---|---|
| 1 分布收不上来 | **消解。** 默认路径不再依赖任何分布；分布只对 `strict` 有意义，而选入者自己知道自己选了什么 |
| 2 提权无诊断 | **默认路径消解**，`strict` 选入时仍需诊断（§5），保留为它的门槛 |
| 3 退路与删除相撞 | **消解。** `legacy` 作为一档保留，`legacy_cmd` 不删，`shell.mode: legacy` 就是退路 |
| 4 强模型只对 Windows 生效 | **消解**（§6） |
| 5 缺中间那一级 | **本方案就是它** |
| 6 门槛里没有真实开发任务 | **仍需做，且是本方案的验收门**（§8） |
| 7 实现文件状态段过期 | **仍需做。** 与本方案无关的独立回修 |

## 8. 验收：真实开发任务，不是契约测试通过

内部契约测试全绿不构成验收。Windows job 上，`basic` 档要跑通下面这一串，每一项失败都算红：

1. 克隆一个真实仓库。
2. 建虚拟环境并装依赖（`uv sync`，以及 `python -m venv` 加 `pip install` 各一遍）。
3. 跑一次构建。
4. 跑一次测试。
5. 装一个用户级工具（scoop 或 npm 全局各一个），随后**裸名字**调用它。
6. 第 5 步之后重新解析一次 PATH，确认新装的工具仍然可用。

第 5、6 两项是专门冲着 ENV-01 去的：它们在 `strict` 下必然红，在 `basic` 下必须绿，
两个答案都要写进门槛矩阵 —— **一道门要能红，才是门**（方法规则 29）。

## 9. PR 阶梯（减法方向）

| 步 | 交付 | 默认是否改变 |
|---|---|---|
| L1 | `PolicyLevel` 三态；`policy_enabled` 降为 `level is not legacy` 的派生读法；SPEC-03、SPEC-06、CFG-02c 的不变量按档重写 | 否 |
| L2 | 地板按档分支（§3 的三处） | 否 |
| L3 | `select_rung` 在 `basic` 下跳过 `trusted_root_chain`、`host_identity_ok`、NAME-02、ENV-01、ENV-06；launcher 仍解析（LAUNCH-01 的复核要它的路径与哈希），但不做认证 | 否 |
| L4 | 配置：`shell.mode: legacy \| basic \| strict`；`shell.ladder` 保留为兼容别名，`true` 映到 `strict`、`false` 映到 `legacy` | 否 |
| L5 | §8 的验收门在 Windows job 上跑绿 | 否 |
| L6 | 默认改为 `basic`；`strict` 保持选入 | **是** |

L1 至 L5 用户不可见，与 LADDER-05 当初对 PR-1 至 PR-6 的承诺同性质。只有 L6 改变行为。

## 10. 不做什么

- **不删除 `strict` 的任何代码。** 它已经写完、有门槛、有两次 Windows 实测，作为选入项留着。
  删掉等于把已经付出的验证一并丢弃 —— 与不做硬回退是同一条理由。
- **不动 POSIX。** q4 的定案不变。
- **不动子代理计划**（原 PR-0）。
- **不把 `682bd3a` 当作恢复目标。** 它只用于对照。
- **不在本方案里定分布、百分比或验收人。** 那正是 rev 48 与 rev 53 两次判掉的东西。
