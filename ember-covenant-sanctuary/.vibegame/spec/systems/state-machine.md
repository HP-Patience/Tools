# 状态机

> **Owner**：Architect
> **依据**：`.vibegame/tasks/001-playable-prototype/prd.md`

Animator 只选择 Task Constraints 指定的 clip；gameplay script 维护下列语义 behavior state。攻击 commit、hit area 与退出均由 state + `dt` 驱动，不读取 raw animation frame。

## Run

`title -> combat -> reward -> combat/route -> death-presentation|victory-presentation -> death|victory`

- Stage 1/2/3/5/6 清场进入 `reward`，选择后才开出口。
- Stage 4 进入 `route`；Recovery 直达 Stage 5，Elite 进入 `combat`，死亡后 heal + reward。
- Stage 7 Boss 0 HP 进入 `victory-presentation`；普通场同帧玩家 0 HP 优先进入 `death-presentation`。

## Ember Keeper

- Animator states：`idle`, `run`, `attack`, `skill`, `death`。
- Alive 时 movement 与 AIM/FIRE/SKILL 并行；`attack` / `skill` 不锁 movement。
- damage 不进入控制锁定 state，只触发 hit feedback；HP 0 才进入 `death`。

## Shadow Fang

Gameplay：`approach -> charge -> strike -> recover -> approach`，任意 alive state -> `dead`。

- Pulse 只可把 `charge` 改为 `recover`；`strike` 不回滚。
- Animator 使用 `run` 表现 approach、`attack` 表现 charge/strike、`idle` 表现 recover、`death` 表现 dead。

## Shadow Acolyte

Gameplay：`move -> charge -> release -> recover -> move`，任意 alive state -> `dead`。

- charge/recovery 期间停止移动；release instantiate 一枚 Shadow Dart。
- Pulse 只可把 `charge` 改为 `recover`。
- Animator：`idle`, `move`, `ranged-attack`, `death`。

## Dusk Deacon

Gameplay：`approach -> melee-charge|ranged-charge -> active -> recover -> approach`，任意 alive state -> `dead`。

- attack 开始后 committed；Pulse 不改变 behavior state 或位置。
- Animator：`idle`, `move`, `melee-attack`, `ranged-attack`, `death`。

## Fallen Bishop

Gameplay：`adjust -> slam-charge|spear-charge|ritual-charge -> active -> recover -> adjust`；50% 时当前 attack -> `phase-transition`；HP 0 -> `death`。

- Phase 1 使用 Slam/Spear；Phase 2 每组三次 attack 恰有一次 Ritual。
- ranged 最多连续两次；attack 开始后不换 category。
- transition 不输出伤害、不可 interrupt，但仍接受合法玩家 hit；若 HP 归零则直接进入 death，不继续 transition。death 立即关闭全部 Boss damage。
- Animator：`idle`, `move`, `melee-attack`, `ranged-attack`, `summon`, `phase-transition`, `death`。

## 禁止状态

任何 controllable/enemy state、action、config、animation 或代码路径均不得加入 `dodge`, `roll`, `dash`、移动无敌、伤害免疫或主动位移技能。
