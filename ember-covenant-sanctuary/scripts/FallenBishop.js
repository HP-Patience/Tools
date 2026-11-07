import EnemyController from './EnemyController.js'

export default class FallenBishop extends EnemyController {
  ready() {
    super.ready()
    this.phase = 1
    this.phase2Cycle = []
    this.attackSequence = []
    this.currentAttack = null
    this.consecutiveRanged = 0
    this.behaviorState = 'adjust'
    this._phaseSlot = 0
  }

  update(dt) {
    super.update(dt)
    if (this._dying || this.parent.runState !== 'combat') return
    if (this.behaviorState === 'phase-transition') {
      this.stop(); this._stateTime -= dt
      if (this._stateTime <= 0) { this.phase = 2; this.damageEnabled = true; this.behaviorState = 'adjust' }
      return
    }
    const vector = this.playerVector()
    if (this.behaviorState === 'adjust') {
      if (Math.abs(vector.distance - this.config.attackRange) > this.config.adjustTolerance) {
        const target = vector.distance > this.config.attackRange
          ? vector.player.getPhysicsObject()
          : { x: this.getPhysicsObject().x - vector.dx, y: this.getPhysicsObject().y - vector.dy }
        this.moveToward(target, this.config.speed)
      } else this._beginAttack(this._chooseAttack(vector.distance), vector)
      return
    }
    this.stop(); this._stateTime -= dt
    if (this.behaviorState.endsWith('-charge') && this._stateTime <= 0) {
      const kind = this.behaviorState.replace('-charge', '')
      if (kind === 'slam' || kind === 'ritual') {
        this.behaviorState = 'active'; this._stateTime = this.config[`${kind}Active`]
      } else {
        this._release(kind, vector)
        this.behaviorState = 'active'; this._stateTime = 0
      }
    } else if (this.behaviorState === 'active' && this._stateTime <= 0 && (this.currentAttack !== 'spear' || this.damagePhaseActiveCount === 0)) {
      this._completeAttack(this.currentAttack)
      this.behaviorState = 'recover'; this._stateTime = this.config.recoveryDuration
    } else if (this.behaviorState === 'recover' && this._stateTime <= 0) {
      if (this.damagePhaseActiveCount === 0) {
        this.behaviorState = 'adjust'; this.attackId = null; this.currentAttack = null
      } else this._stateTime = this.config.damagePollInterval
    }
  }

  _afterDamage() {
    if (this.hp > 0 && this.phase === 1 && this.hp <= this.maxHp * this.config.phaseThreshold && this.behaviorState !== 'phase-transition') {
      this.damageEnabled = false
      this.behaviorState = 'phase-transition'
      this.currentAttack = null
      this.attackId = null
      this._stateTime = this.config.transitionDuration
      this.playAnim('phase-transition')
      this.emit('boss_damage_cancelled')
    }
  }

  _chooseAttack(distance) {
    if (this.phase === 2) {
      const slot = this._phaseSlot % this.config.phase2CycleLength
      this._phaseSlot++
      if (slot === this.config.ritualCycleSlot) return 'ritual'
    }
    if (distance <= this.config.attackRange && this.consecutiveRanged >= this.config.closeRangedLimit) return 'slam'
    if (this.consecutiveRanged >= this.config.maxConsecutiveRanged) return 'slam'
    return distance <= this.config.attackRange ? 'slam' : 'spear'
  }

  _beginAttack(kind, vector) {
    this.faceDirection(vector.dx)
    this.currentAttack = kind
    this.behaviorState = `${kind}-charge`
    this._stateTime = this.config[`${kind}Charge`]
    this.attackId = `bishop-${kind}-${this.id}-${this.scene.time.now}`
    this.playAnim(kind === 'ritual' ? 'summon' : (kind === 'slam' ? 'melee-attack' : 'ranged-attack'))
    if (kind === 'slam') this._spawnSlam(vector)
    if (kind === 'ritual') this._spawnRitual(vector)
  }

  _release(kind, vector) {
    const p = this.getPhysicsObject()
    if (kind === 'slam') {
      this.consecutiveRanged = 0
    } else if (kind === 'spear') {
      this.consecutiveRanged++
      const base = Math.atan2(vector.dy, vector.dx)
      this.config.spearFanAngles.forEach((offset, index) => void this.parent.instantiate('entities/shadow-spear.node.json', {
        x: p.x, y: p.y, angle: base + offset, attackId: `${this.attackId}-${index}`, groupAttackId: this.attackId
      }))
    }
  }

  _spawnSlam(vector) {
    this.consecutiveRanged = 0
    const p = this.getPhysicsObject()
    void this.parent.instantiate('entities/bishop-slam.node.json', { x: p.x + vector.direction.x * this.config.slamOffset, y: p.y + vector.direction.y * this.config.slamOffset, attackId: this.attackId, warningDuration: this.config.slamCharge })
  }

  _spawnRitual(vector) {
    this.consecutiveRanged = 0
    const player = vector.player.getPhysicsObject()
    const authored = this.parent.getChild('Room').ritualRoutePoints()
      .map(([x, y]) => ({ x, y, distance: Phaser.Math.Distance.Between(player.x, player.y, x, y) }))
      .sort((a, b) => a.distance - b.distance)
    const points = [{ x: player.x, y: player.y }, ...authored.slice(0, this.config.ritualRouteCount)]
    points.forEach((point, index) => void this.parent.instantiate('entities/ritual-area.node.json', { x: point.x, y: point.y, attackId: `${this.attackId}-${index}`, groupAttackId: this.attackId, warningDuration: this.config.ritualCharge }))
  }

  _completeAttack(kind) {
    this.attackSequence.push(kind)
    if (this.attackSequence.length > this.config.attackHistoryLimit) this.attackSequence.shift()
    if (this.phase === 2) {
      this.phase2Cycle.push(kind)
      if (this.phase2Cycle.length > this.config.phase2CycleLength) this.phase2Cycle.shift()
    }
  }

  get damagePhaseActiveCount() {
    const ids = new Set()
    for (const projectile of this.findByTag('boss_projectile')) ids.add(projectile.groupAttackId || projectile.attackId)
    for (const hazard of this.findByTag('boss_hazard')) if (hazard.phase === 'active') ids.add(hazard.groupAttackId || hazard.attackId)
    return ids.size
  }

  beginDeath() {
    this.damageEnabled = false
    this.emit('boss_damage_cancelled')
    this.emit('boss_zero')
    super.beginDeath()
  }

  runtimeState() {
    return {
      ...super.runtimeState(), phase: this.phase, currentAttack: this.currentAttack,
      attackSequence: [...this.attackSequence], phase2Cycle: [...this.phase2Cycle],
      consecutiveRanged: this.consecutiveRanged, damagePhaseActiveCount: this.damagePhaseActiveCount
    }
  }
}
