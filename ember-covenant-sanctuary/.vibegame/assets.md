# Asset Inventory

<!-- Maintained by artist agent. Do not edit manually. -->

## Runtime Pack Status

- 正式 manifest：`assets/manifest.json`，已由 `project.json.manifests` 加载。
- 总计：60 个 runtime key；5 个角色 atlas，共 100 个 semantic frame。
- 原型兼容：原型 manifest 的 44 个 final key 全部存在；5 个角色的 semantic frame 集合完全匹配。
- 视觉基准：`assets/reference.png`，高对比度风格化 Pixel Art，top-down 冷绿灰熄灭圣堂。
- 通用方向与语义限制：方向性弹体使用向右 canonical direction；不包含 `dodge`、`roll`、`dash`、护盾或无敌语义。

## Character Atlases

以下角色均为透明背景 `atlas`，group-level `pivot: [0.5, 1]`，以脚底中心稳定落地。每个动作均为 4 帧。

- `ember_keeper` -> `assets/characters/ember_keeper.png`（20 帧）
  - `idle_0..3`、`run_0..3`、`attack_0..3`、`skill_0..3`、`death_0..3`
- `shadow_fang` -> `assets/characters/shadow_fang.png`（16 帧）
  - `idle_0..3`、`run_0..3`、`attack_0..3`、`death_0..3`
- `shadow_acolyte` -> `assets/characters/shadow_acolyte.png`（16 帧）
  - `idle_0..3`、`move_0..3`、`ranged-attack_0..3`、`death_0..3`
- `dusk_deacon` -> `assets/characters/dusk_deacon.png`（20 帧）
  - `idle_0..3`、`move_0..3`、`melee-attack_0..3`、`ranged-attack_0..3`、`death_0..3`
- `fallen_bishop` -> `assets/characters/fallen_bishop.png`（28 帧）
  - `idle_0..3`、`move_0..3`、`melee-attack_0..3`、`ranged-attack_0..3`、`summon_0..3`、`phase-transition_0..3`、`death_0..3`

上一实例的 split atlas 已移至 `assets/artifacts/trash/legacy-split-atlases/` 作为可恢复的历史源，不在正式 manifest 中加载。程序应只使用上述 final key 与 semantic frame，不应回退到 split key 或通用 `frame_*` key。

## Projectiles And VFX

以下均为透明背景 `image`，使用中心 `pivot: [0.5, 0.5]`。

### Projectiles

- `ember_bolt` -> `assets/projectiles/ember_bolt.png`
- `shadow_dart` -> `assets/projectiles/shadow_dart.png`
- `shadow_spear` -> `assets/projectiles/shadow_spear.png`

### Combat VFX

- `fang_warning` -> `assets/vfx/fang_warning.png`
- `fang_impact` -> `assets/vfx/fang_impact.png`
- `deacon_warning` -> `assets/vfx/deacon_warning.png`
- `deacon_impact` -> `assets/vfx/deacon_impact.png`
- `bishop_warning` -> `assets/vfx/bishop_warning.png`
- `bishop_impact` -> `assets/vfx/bishop_impact.png`
- `ritual_warning` -> `assets/vfx/ritual_warning.png`
- `shadow_flame` -> `assets/vfx/shadow_flame.png`
- `pureflame_pulse` -> `assets/vfx/pureflame_pulse.png`
- `hit_spark` -> `assets/vfx/hit_spark.png`
- `ash_burst` -> `assets/vfx/ash_burst.png`
- `last_flame` -> `assets/vfx/last_flame.png`

`pureflame_pulse` 是短暂清场波纹，不是持续护盾。`*_warning` 与 `*_impact` 分离，便于先提示、后结算伤害。

## World Markers

以下均为透明背景 `image`，使用中心 `pivot: [0.5, 0.5]`。

- `exit_marker` -> `assets/markers/exit_marker.png`
- `route_recovery` -> `assets/markers/route_recovery.png`
- `route_elite` -> `assets/markers/route_elite.png`
- `entry_warning` -> `assets/markers/entry_warning.png`

## Tileset

### `sanctuary_tiles`

- 文件：`assets/tilesets/sanctuary_tiles.png`
- 类型：`tileset`
- 规格：`tileSize: 32`，3 列 x 5 行，索引按 row-major 固定为 0-14。
- 适用布局：前厅、侧礼拜堂、回廊、地穴、祭坛区，以及恢复、精英和 Boss 路线房；实际七段布局由 prototype 的 tilemap/runtime room 数据组合这些稳定 semantic tile。
- 本项走 tilemap/tileset contract，不是单张 rastermap，因此没有 image-pixel landmark。

| Index | Semantic key | Collision | 用法 |
| ---: | --- | :---: | --- |
| 0 | `floor_stone` | false | 主地面，低噪声冷绿灰石材 |
| 1 | `floor_ember` | false | 克制的暖色地面变化，不作为危险提示 |
| 2 | `wall_face` | true | 直立墙体正面与实体边界 |
| 3 | `wall_top` | false | 墙顶深度层，与 `wall_face` 配对 |
| 4 | `door_face` | true | 门体正面与实体边界 |
| 5 | `door_top` | false | 门楣深度层，与 `door_face` 配对 |
| 6 | `altar_face` | true | 祭坛正面与实体边界 |
| 7 | `altar_top` | false | 祭坛顶部，与 `altar_face` 配对 |
| 8 | `void` | true | 不可通行的场外区域 |
| 9 | `spawn_player` | false | 玩家出生语义 tile |
| 10 | `spawn_enemy` | false | 敌人出生语义 tile |
| 11 | `exit_floor` | false | 出口地面语义 tile |
| 12 | `ritual_route` | false | 熄灯祭阵路径语义 tile |
| 13 | `route_recovery_floor` | false | 恢复路线地面语义 tile |
| 14 | `route_elite_floor` | false | 精英路线地面语义 tile |

组合规则：`wall_top` 放在 `wall_face` 上方；`door_top` 放在 `door_face` 上方；`altar_top` 放在 `altar_face` 上方。collision 只由 face/void tile 承担，top tile 负责视觉深度，禁止交换语义或重排索引。

### `room_boundary_skirt`

- 文件：`assets/tilesets/room_boundary_skirt.png`
- 类型：`image`；manifest key：`room_boundary_skirt`；`pivot: [0.5, 1]`。
- 规格：`1280x16`，全不透明，无透明或未渲染像素；横向以 32 px 为周期无缝重复，首尾 tile 完全一致。
- 材质来源：直接取自正式 `sanctuary_tiles` 的 `wall_top`（index 3）下半 16 px，横向重复 40 次；仅将该源 tile 的既有半透明边缘按项目背景色 `#111218` 预合成，因此最终 RGB 与原候选在 runtime 中的显示结果一致，不含新绘制纹理或占位图形。
- Runtime 用法：`nodes/room-boundary-skirt.node.json` 以 `1280x16` 显示在逻辑画面 `y=704..720`，只补齐七个 Stage 共用的底墙可见下缘。
- 语义边界：无 collider、无道路/门/开口/marker，不改变现有 tilemap 尺寸、底墙 collision、spawn、exit、camera 或 gameplay 坐标。

## Props

以下均为透明背景 `image`，使用中心 `pivot: [0.5, 0.5]`。实体障碍是否阻挡由 scene/node collider 配置，不由图片本身决定。

### Solid Obstacles

- `extinguished_altar` -> `assets/props/extinguished_altar.png`
- `stone_pillar` -> `assets/props/stone_pillar.png`
- `broken_pew` -> `assets/props/broken_pew.png`
- `gravestone` -> `assets/props/gravestone.png`
- `collapsed_wall_h` -> `assets/props/collapsed_wall_h.png`
- `collapsed_wall_v` -> `assets/props/collapsed_wall_v.png`

### Restrained Decoration

- `cold_candelabrum` -> `assets/props/cold_candelabrum.png`
- `old_drapery` -> `assets/props/old_drapery.png`
- `wall_relief` -> `assets/props/wall_relief.png`
- `ash_scatter` -> `assets/props/ash_scatter.png`
- `thin_smoke` -> `assets/props/thin_smoke.png`
- `victory_brazier` -> `assets/props/victory_brazier.png`

装饰避免红紫危险色；`victory_brazier` 的暖金亮度用于胜利状态，不应在普通战斗房中竞争玩家、奖励或危险信息层级。

## UI

所有 UI 都是不含烘焙文字的 `image`；icon、slot、panel 与 button 使用透明背景，状态栏 fill 是供 bbox 裁切/拉伸的实心纹理。运行时文字、数值与本地化内容必须由 UI layer 叠加。

### Status Bars

- Player：`hud_player_icon`、`hud_player_slot`、`hud_player_fill`
  - 文件：`assets/ui/hud_player_icon.png`、`assets/ui/hud_player_slot.png`、`assets/ui/hud_player_fill.png`
  - slot source bbox / fill placement：`[38, 48, 581, 120]`
  - node template：`nodes/hud-player-bar.node.json`
- Boss：`hud_boss_icon`、`hud_boss_slot`、`hud_boss_fill`
  - 文件：`assets/ui/hud_boss_icon.png`、`assets/ui/hud_boss_slot.png`、`assets/ui/hud_boss_fill.png`
  - slot source bbox / fill placement：`[57, 49, 866, 123]`
  - node template：`nodes/hud-boss-bar.node.json`

### Panels And Buttons

- `ui_panel` -> `assets/ui/ui_panel.png`：pause、confirmation、death、victory 共用无文字面板皮肤。
- `ui_button_idle` -> `assets/ui/ui_button_idle.png`
- `ui_button_hover` -> `assets/ui/ui_button_hover.png`
- `ui_sigil_card` -> `assets/ui/ui_sigil_card.png`：契印三选一/路线选择卡片底板；收益与代价文字必须同等显著地实时叠加。

### Sigils And Combat Indicators

- `sigil_piercing_ember` -> `assets/ui/sigil_piercing_ember.png`
- `sigil_ash_crown` -> `assets/ui/sigil_ash_crown.png`
- `sigil_sacred_nail` -> `assets/ui/sigil_sacred_nail.png`
- `sigil_light_ember` -> `assets/ui/sigil_light_ember.png`
- `sigil_rekindle` -> `assets/ui/sigil_rekindle.png`
- `sigil_wide_radiance` -> `assets/ui/sigil_wide_radiance.png`
- `sigil_close_flame` -> `assets/ui/sigil_close_flame.png`
- `sigil_last_candle` -> `assets/ui/sigil_last_candle.png`
- `sigil_blood_prayer` -> `assets/ui/sigil_blood_prayer.png`
- `pureflame_icon` -> `assets/ui/pureflame_icon.png`
- `aim_reticle` -> `assets/ui/aim_reticle.png`
- `aim_reticle_close` -> `assets/ui/aim_reticle_close.png`：`Close Flame` 距离反馈状态，不是护盾状态。

上述 12 个 icon/reticle key 使用中心 `pivot: [0.5, 0.5]`。九枚契印在 HUD 与三选一卡片尺度下保持不同轮廓。

## Reference

### `project_visual_reference`

- 文件：`assets/reference.png`
- 用途：《烬契圣堂》正式角色、敌人、UI、tilemap、prop 与 VFX 的项目级视觉基准；不作为运行时地图，不登记到 manifest。
- 场景：Stage 3 `破誓回廊`的真实 top-down 战斗时刻。
- 风格：高对比度风格化 Pixel Art；冷绿灰圣堂环境、暖金玩家与可用火种、红紫敌方伤害和临近危险。
- 一致性要求：后续新增视觉资产必须继续以本图作为 `reference`，继承轮廓、配色、材质、像素密度和信息层级。

## QC Evidence

- 角色 cross-action scale：`assets/artifacts/runtime-pack-processed/scale-qc/`
- Player 状态栏 bbox 与满值合成：`assets/artifacts/runtime-pack-processed/status-bar-qc/player_slot_bbox.png`、`player_slot_bar.png`
- Boss 状态栏 bbox 与满值合成：`assets/artifacts/runtime-pack-processed/status-bar-qc/boss_slot_bbox.png`、`boss_slot_bar.png`
- tileset 放大检查：`assets/artifacts/runtime-pack-processed/sanctuary_tiles_qc_8x.png`
- 底墙延伸裙边放大检查：`assets/artifacts/runtime-boundary-skirt-qc/room_boundary_skirt_8x.png`
- props、marker、UI、契印与 VFX bbox preview：`assets/artifacts/runtime-pack-processed/*-bboxes.preview.png`

## Missing / Blocked

- 本次 `must_have` runtime art pack 无缺口、无阻塞。
- Font 与 Audio 不属于本次 visual asset pack，仍未登记。

## Handoff Notes

- `assets/manifest.json` 是唯一正式运行时 manifest；`assets/artifacts/` 下不得保留或重新生成 orphan `manifest.json`。
- `assets/artifacts/raw/` 和其他 processing/QC 文件仅用于追溯，不应加入 `project.json.manifests`。
- 正式 manifest 不含 placeholder，所有路径存在，所有 atlas bbox 均在源图范围内。
- 后续若必须再次运行 `vibegame art concat`，应把自动生成的中间 manifest 立即移入 `assets/artifacts/trash/`，并重新执行 `vibegame check .`。

---

> Use the `language` value defined in `.vibegame/global.json` to write this file. Keep code identifiers, file paths, asset keys, and engine vocabulary in English.
