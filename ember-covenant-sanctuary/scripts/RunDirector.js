import { Node } from '/engine/Node.js'
import { fetchJson } from '/engine/url.js'
import SeededRng, { seedFromQuery } from './rules/SeededRng.js'
import { offerSigils } from './rules/SigilRules.js'
import { sigilEffect } from './rules/CombatRules.js'

export default class RunDirector extends Node {
  async ready() {
    const data = await fetchJson('config/sigils.json')
    this.sigilRegistry = data.sigils
    this.seed = seedFromQuery()
    this.bootId = crypto.randomUUID()
    this.runId = `${this.bootId}:run-1`
    this.rng = new SeededRng(this.seed)
    this.layoutOrder = this.rng.shuffle(this.config.ordinaryLayouts)
    this.runState = 'title'
    this.stage = 1
    this.roomName = ''
    this.layoutId = ''
    this.wave = 1
    this.enemyCount = 0
    this.exitOpen = false
    this.ownedSigils = []
    this.offeredSigils = []
    this.selectedRoute = null
    this.result = null
    this.assetFailures = []
    this._assetFailureKeys = new Set()
    this.routeOptions = this._initialRouteOptions()
    this._frameFacts = { playerDied: null, bossZero: false, enemyDeaths: 0 }
    this._busy = false
    this._titleRemaining = this.config.timings.title
    this._terminalRemaining = 0
    this._waveWarningRemaining = 0

    this.on('enemy_died', event => { if (!event.boss) this._frameFacts.enemyDeaths++ })
    this.on('player_died', event => { this._frameFacts.playerDied = event.damageSource || 'unknown' })
    this.on('boss_zero', () => { this._frameFacts.bossZero = true })
    this.on('boss_damage_cancelled', () => this._removeBossDamage())
    this.on('damage_number', event => this.getChild('HUD')?.addDamageNumber(event.amount, event.x, event.y))
    this.on('player_hurt', event => {
      this.getChild('Overlay')?.flashHurt()
      this.scene.cameras.main.shake(this.config.cameraShake.durationMs, this.config.cameraShake.intensity)
      this._lastDamageSource = event.damageSource
    })
    this.on('interaction_activated', event => { void this._handleInteraction(event.interactionId) })
    this.on('visual_asset_failed', event => this._recordAssetFailure(event))
    this._postUpdate = () => this._resolveFrame()
    this.scene.events.on('postupdate', this._postUpdate)
    await this.enterStage(1)
    this.getChild('Overlay').showMenu('title')
  }

  update(dt) {
    const input = this.getChild('Input')
    if (input?.isPressed('pause') && ['combat', 'route'].includes(this.runState) && !this.getChild('Overlay').authority) {
      this.getChild('Overlay').showMenu('pause')
      return
    }
    if (this.runState === 'title') {
      this._titleRemaining -= dt
      if (this._titleRemaining <= 0) {
        input.clearHeld()
        this.getChild('Overlay').hideTitle()
        this.runState = 'combat'
      }
    }
    if (this._waveWarningRemaining > 0) {
      this._waveWarningRemaining -= dt
      if (this._waveWarningRemaining <= 0 && this._stageDef().waves?.['2'] && this.wave === 1) void this._spawnSecondWave()
    }
    if (this.runState === 'death-presentation' || this.runState === 'victory-presentation') {
      this._terminalRemaining -= dt
      if (this._terminalRemaining <= 0) this._showTerminal()
    }
  }

  async enterStage(stage) {
    if (this._busy) return
    this._busy = true
    this._clearRuntimeNodes()
    this.stage = stage
    this.wave = 1
    this.exitOpen = false
    this.offeredSigils = []
    this.enemyCount = 0
    const stageDef = this._stageDef(stage)
    this.layoutId = stageDef.layout || this.layoutOrder[stageDef.layoutOrderIndex]
    this.roomName = stageDef.name
    await this.getChild('Room').loadLayout(this.layoutId)
    const player = this.getChild('EmberKeeper')
    player.getPhysicsObject().setPosition(...this.getChild('Room').playerSpawn())
    player.getPhysicsObject().body.setVelocity(0, 0)
    player.applySigils(this.ownedSigils)
    this.getChild('HUD').showRoom(stage, this.roomName)
    this.getChild('HUD').hideRouteChoices()

    if (stageDef.kind === 'route') {
      this.runState = 'route'
      const routePoints = this.getChild('Room').routePoints()
      await this._spawnRoutes(routePoints)
      this.routeOptions = this._initialRouteOptions()
      this.getChild('HUD').showRouteChoices(routePoints, this.routeOptions)
    } else if (stageDef.kind === 'boss') {
      this.runState = 'combat'
      await this._spawnRoster(this._roster(stage, 1))
    } else {
      this.runState = stage === 1 && this._titleRemaining > 0 ? 'title' : 'combat'
      await this._spawnRoster(this._roster(stage, 1))
    }
    this._busy = false
  }

  _roster(stage, wave) {
    return this._stageDef(stage).waves?.[String(wave)] || []
  }

  async _spawnRoster(roster, spawnOverride = null) {
    const paths = { fang: 'entities/shadow-fang.node.json', acolyte: 'entities/shadow-acolyte.node.json', deacon: 'entities/dusk-deacon.node.json', bishop: 'entities/fallen-bishop.node.json' }
    const spawns = spawnOverride || this.getChild('Room').enemySpawns()
    if (!spawns.length && roster.length) throw new Error(`Layout ${this.layoutId} has no eligible enemy spawn`)
    let index = 0
    for (const group of roster) {
      for (let count = 0; count < group.count; count++) {
        const [x, y] = spawns[index++ % spawns.length]
        await this.instantiate(paths[group.type], { x, y })
        this.enemyCount++
      }
    }
  }

  async _spawnRoutes(points) {
    await this.instantiate('entities/route-recovery.node.json', { x: points.recovery[0], y: points.recovery[1] })
    await this.instantiate('entities/route-elite.node.json', { x: points.elite[0], y: points.elite[1] })
  }

  async _spawnSecondWave() {
    this.wave++
    const player = this.getChild('EmberKeeper').getPhysicsObject()
    const available = this.getChild('Room').enemySpawns().filter(([x, y]) => Phaser.Math.Distance.Between(x, y, player.x, player.y) >= this.config.waveSpawnGap)
    await this._spawnRoster(this._roster(this.stage, this.wave), available)
    this.getChild('HUD').showToast('第二波阴影正在进入')
  }

  _resolveFrame() {
    const facts = this._frameFacts
    this._frameFacts = { playerDied: null, bossZero: false, enemyDeaths: 0 }
    if (facts.bossZero) return this._beginVictory()
    if (facts.playerDied) return this._beginDeath(facts.playerDied)
    if (facts.enemyDeaths > 0) {
      this.enemyCount = Math.max(0, this.enemyCount - facts.enemyDeaths)
      if (this.enemyCount === 0) void this._handleClear()
    }
  }

  async _handleClear() {
    if (this._busy || this.runState !== 'combat') return
    this._busy = true
    this._clearDamagingNodes()
    const player = this.getChild('EmberKeeper')
    if (this._stageDef().waves?.[String(this.wave + 1)]) {
      this._waveWarningRemaining = this.config.timings.waveWarning
      await this.instantiate('entities/entry-warning.node.json', { ...this.config.waveWarningPosition, ttl: this.config.timings.waveWarning })
      this._busy = false
      return
    }
    if (this.ownedSigils.includes('rekindle')) player.heal(sigilEffect(this.sigilRegistry, 'rekindle').clearHeal)
    if (this._stageDef().kind === 'route' && this.selectedRoute === 'elite') player.heal(this._routeDef('elite').heal)
    if (this._stageDef().kind === 'boss') { this._busy = false; return }
    this.runState = 'reward'
    this.offeredSigils = offerSigils(this.sigilRegistry, this.ownedSigils, this.rng, this.config.sigilOfferCount)
    this.getChild('SigilChoice').showOffer(this.offeredSigils, id => this._selectSigil(id))
    this._busy = false
  }

  _selectSigil(id) {
    if (this.runState !== 'reward' || !this.offeredSigils.includes(id)) return
    this.ownedSigils.push(id)
    this.getChild('EmberKeeper').applySigils(this.ownedSigils)
    this.offeredSigils = []
    this.runState = 'combat'
    this.openExit()
  }

  async openExit() {
    this.exitOpen = true
    this.getChild('Room').setDoorsClosed(false)
    const [x, y] = this.getChild('Room').exitPoint()
    await this.instantiate('entities/exit.node.json', { x, y })
    this.getChild('HUD').showExitFeedback('出口已经开启')
  }

  async _handleInteraction(id) {
    if (id === 'exit' && this.exitOpen && this.stage < this._maxStage()) return this.enterStage(this.stage + 1)
    if (this._stageDef().kind !== 'route' || this.selectedRoute) return
    if (id === 'route-recovery') {
      if (!this._lockRoutes('recovery')) return
      const route = this._routeDef('recovery')
      this.getChild('EmberKeeper').heal(route.heal)
      return this.enterStage(route.nextStage)
    } else if (id === 'route-elite') {
      if (!this._lockRoutes('elite')) return
      this._removeByTag('interaction')
      this.runState = 'combat'
      return this._spawnRoster(this._routeDef('elite').roster)
    }
  }

  _beginDeath(source) {
    if (this.runState.includes('presentation') || ['death', 'victory'].includes(this.runState)) return
    this._clearDamagingNodes()
    this.runState = 'death-presentation'
    this._terminalRemaining = this.config.timings.deathPresentation
    this.result = { outcome: 'lose', stage: this.stage, sigils: [...this.ownedSigils], remainingHp: 0, damageSource: source }
  }

  _beginVictory() {
    if (this.runState.includes('presentation') || this.runState === 'victory') return
    this._clearDamagingNodes()
    const player = this.getChild('EmberKeeper')
    player.hp = Math.max(1, player.hp)
    this.runState = 'victory-presentation'
    this._terminalRemaining = this.config.timings.victoryPresentation
    this.result = { outcome: 'win', stage: this._maxStage(), sigils: [...this.ownedSigils], remainingHp: player.hp, damageSource: null }
    void this.getChild('Room').showVictoryLighting()
    const boss = this.findByTag('boss')[0]?.getPhysicsObject()
    if (boss) void this.instantiate('entities/last-flame.node.json', { x: boss.x, y: boss.y, ttl: this.config.timings.victoryPresentation })
  }

  _showTerminal() {
    const kind = this.runState === 'victory-presentation' ? 'victory' : 'death'
    this.runState = kind
    this.getChild('Overlay').showResult(kind, this.result)
  }

  _removeBossDamage() {
    for (const node of [...this.findByTag('boss_projectile'), ...this.findByTag('boss_hazard')]) node.removeSelf()
  }

  _clearDamagingNodes() { this._removeByTag('damaging') }
  _clearRuntimeNodes() { this._removeByTag('runtime') }
  _removeByTag(tag) { for (const node of [...this.findByTag(tag)]) node.removeSelf() }

  _recordAssetFailure(event) {
    const failure = {
      texture: event.texture || null,
      frame: event.frame ?? null,
      kind: event.kind || 'visual',
      label: event.label || null,
    }
    const key = `${failure.kind}:${failure.texture}:${failure.frame}`
    if (this._assetFailureKeys.has(key)) return
    this._assetFailureKeys.add(key)
    this.assetFailures.push(failure)
  }

  get damagingObjectCount() { return this.findByTag('damaging').length }
  get waveWarningActive() { return this._waveWarningRemaining > 0 }

  _initialRouteOptions() {
    return this.config.routeOptions.map(({ id, label, consequence, heal, sigilReward }) => ({ id, label, consequence, heal, sigilReward, open:true, locked:false, interactable:true }))
  }

  _stageDef(stage = this.stage) { return this.config.stageDefs[String(stage)] }
  _routeDef(id) { return this.config.routeOptions.find(option => option.id === id) }
  _maxStage() { return Math.max(...Object.keys(this.config.stageDefs).map(Number)) }

  _lockRoutes(selected) {
    if (this.selectedRoute || !this.routeOptions.some(option => option.id === selected)) return false
    const nextOptions = this.routeOptions.map(option => ({ ...option, open: option.id === selected, locked: option.id !== selected, interactable: false }))
    this.getChild('Room').lockRejectedRoute(selected)
    this.selectedRoute = selected
    this.routeOptions = nextOptions
    this.getChild('HUD').hideRouteChoices()
    return true
  }

  async runtimeTestSetup(scenario, params = {}) {
    this.scene.scene.resume()
    this.sceneTree.running = true
    const input = this.getChild('Input')
    input.clearHeld()
    input.pointerFireSuppressed = false
    this.getChild('Overlay').authority = null
    this.getChild('Overlay').hideMenu()
    this.getChild('SigilChoice').hide()
    this._titleRemaining = 0
    const bossStage = Object.entries(this.config.stageDefs).find(([, value]) => value.kind === 'boss')?.[0]
    const stage = Number(params.stage || (scenario === 'simultaneous-terminal' ? bossStage : 1))
    const stageDef = this._stageDef(stage)
    if (params.layout !== undefined) {
      if (stageDef.layout) {
        if (params.layout !== stageDef.layout) throw new Error(`Stage ${stage} requires layout ${stageDef.layout}`)
      } else {
        const targetIndex = stageDef.layoutOrderIndex
        const sourceIndex = this.layoutOrder.indexOf(params.layout)
        if (!Number.isInteger(targetIndex) || sourceIndex < 0) throw new Error(`Layout ${params.layout} is not valid for stage ${stage}`)
        const displacedLayout = this.layoutOrder[targetIndex]
        this.layoutOrder[targetIndex] = params.layout
        this.layoutOrder[sourceIndex] = displacedLayout
      }
    }
    await this.enterStage(stage)
    this.runState = this._stageDef(stage).kind === 'route' ? 'route' : 'combat'
    if (params.route && this._stageDef(stage).kind === 'route') await this._handleInteraction(`route-${params.route}`)
    if (params.wave === 2 && this._stageDef(stage).waves?.['2']) {
      this._removeByTag('enemy')
      this.enemyCount = 0
      this.wave = 2
      await this._spawnRoster(this._roster(stage, 2))
    }

    const player = this.getChild('EmberKeeper')
    if (params.player?.sigils) { this.ownedSigils = [...params.player.sigils]; player.applySigils(this.ownedSigils) }
    if (Number.isFinite(params.player?.hp)) player.hp = Math.max(0, Math.min(player.maxHp, params.player.hp))
    if (params.player?.position) player.getPhysicsObject().setPosition(params.player.position.x, params.player.position.y)
    if (params.player?.skill) Object.assign(player.skill, params.player.skill)

    if (Array.isArray(params.enemies)) {
      this._removeByTag('enemy'); this.enemyCount = 0
      const template = { fang:'entities/shadow-fang.node.json', acolyte:'entities/shadow-acolyte.node.json', deacon:'entities/dusk-deacon.node.json', bishop:'entities/fallen-bishop.node.json' }
      for (const setup of params.enemies) {
        const [defaultX, defaultY] = this.getChild('Room').enemySpawns()[0]
        const node = await this.instantiate(template[setup.type], { x: setup.position?.x ?? defaultX, y: setup.position?.y ?? defaultY })
        if (Number.isFinite(setup.hp)) node.hp = Math.max(0, Math.min(node.maxHp, setup.hp))
        if (setup.behaviorState) node.behaviorState = setup.behaviorState
        if (Number.isFinite(setup.stateTime)) node._stateTime = setup.stateTime
        if (setup.attackId) node.attackId = setup.attackId
        if (Number.isFinite(setup.phase) && 'phase' in node) node.phase = setup.phase
        if (Number.isFinite(setup.consecutiveRanged) && 'consecutiveRanged' in node) node.consecutiveRanged = setup.consecutiveRanged
        if (Number.isFinite(setup.phaseSlot) && '_phaseSlot' in node) node._phaseSlot = setup.phaseSlot
        this.enemyCount++
      }
    }
    const projectileTemplate = { bolt:'entities/ember-bolt.node.json', dart:'entities/shadow-dart.node.json', spear:'entities/shadow-spear.node.json' }
    for (const setup of params.projectiles || []) {
      const config = { x:setup.position.x, y:setup.position.y, angle:setup.angle || 0 }
      if (setup.type === 'bolt') { config.damage = player._shotDamageRaw; config.speed = player.projectileSpeed; config.pierce = player.pierce }
      if (Number.isFinite(setup.damage)) config.damage = setup.damage
      if (Number.isFinite(setup.speed)) config.speed = setup.speed
      if (Number.isFinite(setup.pierce)) config.pierce = setup.pierce
      if (setup.attackId) config.attackId = setup.attackId
      await this.instantiate(projectileTemplate[setup.type], config)
    }
    const areaTemplate = { fang:'entities/fang-melee.node.json', deacon:'entities/deacon-melee.node.json', slam:'entities/bishop-slam.node.json', ritual:'entities/ritual-area.node.json' }
    for (const setup of params.areas || []) {
      const area = await this.instantiate(areaTemplate[setup.type], { x:setup.position.x, y:setup.position.y, attackId:setup.attackId })
      if (setup.phase) {
        area.phase = setup.phase
        area._elapsed = 0
        if (setup.phase === 'active') area._setVisualTexture(area.config.impactTexture)
      }
    }

    if (scenario === 'clear-room') for (const enemy of [...this.findByTag('enemy')]) enemy.receiveDamage?.(enemy.hp, 'runtime-setup')
    if (scenario === 'simultaneous-terminal') {
      const boss = this.findByTag('boss')[0]
      player.hp = Number(params.playerHp || 1); boss.hp = Number(params.bossHp || 1)
      player.receiveDamage(player.hp, 'runtime-simultaneous', 'runtime-player-hit')
      boss.receiveDamage(boss.hp, 'runtime-boss-hit')
    }
    if (params.overlay) this.getChild('Overlay').showMenu(params.overlay)
    player.resetFiringCadence()
    return this.runtimeState()
  }

  runtimeState() {
    return {
      runState: this.runState, bootId: this.bootId, runId: this.runId, seed: this.seed,
      stage: this.stage, roomName: this.roomName, layoutId: this.layoutId,
      layoutOrder: [...this.layoutOrder], wave: this.wave, enemyCount: this.enemyCount,
      damagingObjectCount: this.damagingObjectCount, exitOpen: this.exitOpen, waveWarningActive: this.waveWarningActive,
      ownedSigils: [...this.ownedSigils], offeredSigils: [...this.offeredSigils], selectedRoute: this.selectedRoute,
      routeOptions: this.routeOptions.map(option => ({ ...option })),
      result: this.result ? { ...this.result, sigils: [...this.result.sigils] } : null,
      assetFailures: this.assetFailures.map(failure => ({ ...failure }))
    }
  }

  destroy() { this.scene.events.off('postupdate', this._postUpdate) }
}
