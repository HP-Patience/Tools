# 基础：Engine 与技术设置

> **Owner**：Architect
> **依据**：`.vibegame/tasks/001-playable-prototype/prd.md`

## Engine

- [x] **Phaser 3 CE**：使用 Arcade Physics、pointer/input、animation 与 tilemap。
- [ ] Canvas raw
- [ ] PixiJS

**Decision**：使用项目既有 vibegame + Phaser 3 CE runtime，不建立平行 boot 或 physics/UI runtime。

## Viewport 与 Scale

- 逻辑分辨率：`1280x720`。
- Scale mode：`FIT`，使当前完整房间在 desktop/mobile viewport 内保持可见。
- Pixel Art：启用 nearest-neighbor 渲染。
- Camera：固定单房间镜头，不滚动；HUD 使用 `UiLayer` 逻辑坐标或 `scrollFactor=0`。

## World 与 UI

- 地图：单个可重建的 square-grid `TileMap`；`floor < face < top`，collision 位于 `face`。
- prototype tileset：PRD 已明确授权 pathless color-backed `type: "tileset"`；真实美术任务保持 key、semantic tile names、indices、collision 与 layers，仅增加 PNG `path` 并移除临时 `color`。
- 动态 gameplay 内容：全部通过 `.node.json` template + `instantiate()`。
- UI：数值/菜单使用 DOM/CSS，图片通过 manifest final key 与 `UiLayer` 解析；禁止 `Phaser.Text`。
- Pause：`GameOverlayModule` 同时冻结 Node updates 与 Phaser scene/physics/animations/timers。
