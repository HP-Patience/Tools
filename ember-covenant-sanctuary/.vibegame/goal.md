# Current Goal

## User Input

<!-- Written by the goal-capture hook: every prompt invoking vibegame-build is appended here verbatim.
     Never edit or summarize it. When the user overrides an earlier request, say so in Done When. -->

我想做一款肉鸽地牢游戏。请先根据现有空白项目提出一个可玩的最小版本方案，并向我确认题材、美术风格、战斗方式和局内成长选择；确认后再开始开发。

我确认最终方向：题材为‘熄灭圣堂，守烬人从影兽手中追回最后火种’；美术为‘高对比度风格化 Pixel Art’；战斗为‘自由瞄准远程射击 + 主动走位/技能’；局内成长为‘三选一双面契印，强化一项能力并公开附带代价’。注意战斗以我本次确认的主动走位/技能为准，不要擅自改回主动闪避。请写入 GDD，并按已确认的最小可玩版本开始开发。


## Task Breakdown

| 阶段 | Task | 目标状态 | 验证方式 | 依赖 |
|---|---|---|---|---|
| 1 | `playable-prototype` | 使用最终 manifest key 与语义 animation 名建立完整七段单局：移动、自由瞄准射击、净焰脉冲、房间战、路线选择、九枚双面契印、两阶段 Boss、暂停与胜负重开均可运行；原型不含任何主动闪避、位移技或免伤状态 | `vibegame check .`；Runtime API 状态断言；房间流、战斗、成长、Boss 与重开回归测试；关键界面截图 | 无 |
| 1 | `runtime-art-pack` | 依据用户批准的参考图制作并注册首版所需的高对比度风格化 Pixel Art，包括角色、敌人、Boss、弹体与 VFX、tilemap/障碍、HUD 与 overlay 资产 | Assets 面板检查；透明度、animation 和 manifest 注册检查；资产预览 | 用户批准参考图 |
| 2 | `visual-integration` | 将正式资产接入完整玩法，统一构图、层级、HUD 和反馈，移除所有 placeholder，保持 Stage 1 已验证规则不变 | `vibegame check .`；全部回归测试；桌面与移动视口运行截图；placeholder 零残留检查 | `playable-prototype`、`runtime-art-pack` |
| 3 | `final-review` | 对合并后的完整游戏执行最终质量门禁，修复所有拒绝项并确认主分支可交付 | reviewer 全量测试、运行时游玩、视觉与可操作性验收通过 | `visual-integration` |

## Done When

- [x] 用户确认题材、美术、战斗与局内成长方向，完整规则已写入 `GDD.md`。
- [x] 游戏可从 Stage 1 连续游玩至玩家死亡或击败失火主教，并可立即重新开始新一局。
- [x] 守烬人可持续走位、自由瞄准射击并使用净焰脉冲；不存在主动闪避、`roll`、`dash`、位移无敌或其他免伤状态。
- [x] 七段房间流程、恢复 / 精英路线、九枚双面契印、两种普通敌人、一种精英和两阶段 Boss 全部符合 `GDD.md`。
- [x] HUD、契印选择、路线提示、暂停、胜利和失败界面完整可用，并清楚呈现收益、代价与伤害来源。
- [x] 所有玩家可见的角色、环境、战斗物体、VFX 与 UI 均使用已注册的正式 Pixel Art 或成品视觉，不含 primitive placeholder、`placeholder_image` 或 `placeholder_atlas`。
- [x] Runtime State Contract 足以稳定验证移动、射击、技能、生命、契印、房间、路线、敌人、Boss 阶段及终局状态；相关自动化回归测试通过。
- [x] 桌面与移动浏览器视口均能完整显示游戏，UI 不遮挡关键战斗信息，输入与重开流程可用。
- [x] reviewer 最终验收通过，全部改动合并并提交，游戏可从 main 工作树通过 dashboard 的 Play 启动。

---

> Use the `language` value defined in `.vibegame/global.json` to write this file. Keep code identifiers, file paths, asset keys, and engine vocabulary in English.
