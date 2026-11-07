import { Node } from '/engine/Node.js'
import { fetchJson } from '/engine/url.js'

export default class RoomController extends Node {
  ready() {
    this.tileMap = this.getChild('TileMap')
    this.layoutId = ''
    this.doorsClosed = true
    this.solidLayerReady = false
    this.routeFocus = null
    this.rejectedRouteDoor = null
    this.mapData = null
    this._colliders = []
    this._visualNodes = []
    this.visualProps = []
    this.victoryLightingActive = false
  }

  async loadLayout(layoutId) {
    const path = this.config.mapFiles[layoutId]
    if (!path) throw new Error(`Unknown layout: ${layoutId}`)
    this.mapData = await fetchJson(path)
    this.layoutId = layoutId
    this.routeFocus = null
    this.rejectedRouteDoor = null
    this.victoryLightingActive = false
    this._clearColliders()
    this._clearVisuals()
    this.tileMap.init(this.mapData.width, this.mapData.height, {
      layers: this.config.layers
    })

    this._markers = { player_spawn: [], enemy_spawn: [], exit: [], ritual_route: [], route_recovery: [], route_elite: [] }
    for (const layer of this.mapData.layers) {
      for (let y = 0; y < this.mapData.height; y++) {
        for (let x = 0; x < this.mapData.width; x++) {
          const tile = layer.data[y][x]
          this.tileMap.setTile(layer.name, x, y, tile)
          const role = this.tileMap.getTileProperties(layer.name, x, y)?.role
          if (role) this._markers[role].push([(x + 0.5) * this.mapData.tileSize, (y + 0.5) * this.mapData.tileSize])
        }
      }
    }
    await this._loadVisuals()
    this._doorCells = []
    const face = this.mapData.layers.find(layer => layer.name === 'face')
    for (let y = 0; y < this.mapData.height; y++) for (let x = 0; x < this.mapData.width; x++) if (face.data[y][x] === 'door_face') this._doorCells.push([x, y])
    this.setDoorsClosed(!this.config.initiallyOpenLayouts.includes(layoutId))
    this.solidLayerReady = true
    for (const node of [...this.findByTag('player'), ...this.findByTag('enemy'), ...this.findByTag('projectile')]) this.bindNode(node)
    return this.mapData
  }

  setDoorsClosed(closed) {
    this.doorsClosed = !!closed
    for (const [x, y] of this._doorCells || []) {
      this.tileMap.setTile('face', x, y, closed ? 'door_face' : null)
      this.tileMap.setTile('top', x, y, closed ? 'door_top' : null)
    }
  }

  async showVictoryLighting() {
    const victory = this.mapData?.metadata?.victory
    if (this.victoryLightingActive || !victory) return
    this.victoryLightingActive = true
    for (const [x, y] of victory.floorCells || []) this.tileMap.setTile('floor', x, y, 'floor_ember')
    const placement = victory.brazier
    if (placement) await this._instantiateVisual({ ...placement, kind: 'victory' })
  }

  lockRejectedRoute(selectedRoute) {
    const rejectedRoute = selectedRoute === 'recovery' ? 'elite' : selectedRoute === 'elite' ? 'recovery' : null
    if (!rejectedRoute) throw new Error(`Unknown route selection: ${selectedRoute}`)

    const selectedPoint = this._requiredMarker(`route_${selectedRoute}`)
    const rejectedPoint = this._requiredMarker(`route_${rejectedRoute}`)
    const selectedCell = this.worldToCell(...selectedPoint)
    const faceCell = this.worldToCell(...rejectedPoint)
    const topCell = { x: faceCell.x, y: faceCell.y - 1 }
    if (topCell.y < 0) throw new Error(`Route ${rejectedRoute} entrance cannot host a door top`)

    // Keep the selected entrance open and close the rejected entrance as one synchronous tile update.
    this.tileMap.setTile('face', selectedCell.x, selectedCell.y, null)
    this.tileMap.setTile('top', selectedCell.x, selectedCell.y - 1, null)
    this.tileMap.setTile('face', faceCell.x, faceCell.y, 'door_face')
    this.tileMap.setTile('top', topCell.x, topCell.y, 'door_top')
    this.rejectedRouteDoor = {
      routeId: rejectedRoute,
      faceCell,
      topCell
    }
  }

  bindNode(node) {
    const object = node?.getPhysicsObject?.()
    const solids = this.tileMap?.getCollisionLayer('face')
    if (!object?.body || !solids || this._colliders.some(entry => entry.node === node)) return
    const collider = this.scene.physics.add.collider(object, solids, () => {
      if (node.tags?.includes('projectile')) node.expire?.()
    })
    this._colliders.push({ node, collider })
  }

  unbindNode(node) {
    const entries = this._colliders.filter(entry => entry.node === node)
    for (const entry of entries) entry.collider?.destroy?.()
    this._colliders = this._colliders.filter(entry => entry.node !== node)
  }

  isPassable(x, y) { return this.tileMap?.isPassable(x, y) ?? false }
  playerSpawn() { return this._requiredMarker('player_spawn') }
  enemySpawns() { return this._markers?.enemy_spawn || [] }
  exitPoint() { return this._requiredMarker('exit') }
  routePoints() { return { recovery: this._markers?.route_recovery?.[0], elite: this._markers?.route_elite?.[0] } }
  ritualRoutePoints() { return this._markers?.ritual_route || [] }
  semanticLayerOrder() {
    return this.config.layers.map(def => def.name).filter(name => {
      const source = this.mapData?.layers?.find(layer => layer.name === name)
      return source?.data.some((row, y) => row.some((tile, x) => tile !== null && this.tileMap.getTile(name, x, y) === tile))
    })
  }
  corridorReady() {
    const floor = this.mapData?.layers?.find(layer => layer.name === 'floor')
    return !!floor?.data.some((row, y) => row.some((tile, x) => tile === 'exit_floor' && this.tileMap.getTile('floor', x, y) === 'exit_floor'))
  }
  tileSize() { return this.mapData?.tileSize || this.tileMap?.config?.tileSize }
  worldToCell(x, y) { const size = this.tileSize(); return { x: Math.floor(x / size), y: Math.floor(y / size) } }
  isCirclePassable(x, y, radius) {
    return [[x - radius, y], [x + radius, y], [x, y - radius], [x, y + radius]]
      .every(([sampleX, sampleY]) => {
        const cell = this.worldToCell(sampleX, sampleY)
        return this.isPassable(cell.x, cell.y)
      })
  }
  containsWorldPoint(x, y, padding = 0) {
    return x >= padding && y >= padding && x <= this.mapData.width * this.tileSize() - padding && y <= this.mapData.height * this.tileSize() - padding
  }
  clampWorldPoint(x, y) {
    const inset = this.parent.config.combatBoundsInset
    return {
      x: Phaser.Math.Clamp(x, inset, this.mapData.width * this.tileSize() - inset),
      y: Phaser.Math.Clamp(y, inset, this.mapData.height * this.tileSize() - inset)
    }
  }

  _requiredMarker(role) {
    const point = this._markers?.[role]?.[0]
    if (!point) throw new Error(`Layout ${this.layoutId} is missing required marker ${role}`)
    return point
  }

  _clearColliders() {
    for (const entry of this._colliders) entry.collider?.destroy?.()
    this._colliders = []
  }

  async _loadVisuals() {
    for (const placement of this.mapData.metadata?.visuals || []) await this._instantiateVisual(placement)
  }

  async _instantiateVisual(placement) {
    const size = this.tileSize()
    const [gridX, gridY] = placement.grid
    const node = await this.instantiate(placement.template, {
      x: (gridX + 0.5) * size,
      y: (gridY + 0.5) * size,
    })
    const depth = placement.depth ?? (placement.kind === 'decor' ? this.config.decorDepth : placement.kind === 'victory' ? this.config.victoryDepth : this.config.propDepth)
    node.getVisualObject()?.setDepth(depth)
    this._visualNodes.push(node)
    this.visualProps.push({ key: placement.key, kind: placement.kind, grid: [gridX, gridY] })
    return node
  }

  _clearVisuals() {
    for (const node of this._visualNodes) node.removeSelf()
    this._visualNodes = []
    this.visualProps = []
  }

  runtimeState() {
    return {
      layoutId: this.layoutId,
      doorsClosed: this.doorsClosed,
      solidLayerReady: this.solidLayerReady,
      routeFocus: this.routeFocus,
      rejectedRouteDoor: this.rejectedRouteDoor ? {
        ...this.rejectedRouteDoor,
        faceCell: { ...this.rejectedRouteDoor.faceCell },
        topCell: { ...this.rejectedRouteDoor.topCell },
        faceTile: this.tileMap.getTile('face', this.rejectedRouteDoor.faceCell.x, this.rejectedRouteDoor.faceCell.y),
        topTile: this.tileMap.getTile('top', this.rejectedRouteDoor.topCell.x, this.rejectedRouteDoor.topCell.y),
        collisionActive: !this.isPassable(this.rejectedRouteDoor.faceCell.x, this.rejectedRouteDoor.faceCell.y)
      } : null,
      layerOrder: this.semanticLayerOrder(),
      visualProps: this.visualProps.map(prop => ({ ...prop, grid: [...prop.grid] })),
      victoryLightingActive: this.victoryLightingActive,
      corridorReady: this.corridorReady()
    }
  }

  destroy() { this._clearColliders(); this._clearVisuals() }
}
