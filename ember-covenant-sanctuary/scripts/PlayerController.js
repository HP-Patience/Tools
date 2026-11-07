import { Node } from '/engine/Node.js'
import { clampHp, derivePlayerStats, sigilEffect } from './rules/CombatRules.js'

export default class PlayerController extends Node {
  ready() {
    this.baseStats = { ...this.config.baseStats }
    this.hp = this.baseStats.maxHp
    this.maxHp = this.baseStats.maxHp
    this.ownedSigils = []
    this.movementSpeed = this.baseStats.movementSpeed
    this.shotDamage = this.baseStats.shotDamage
    this.shotsPerSecond = this.baseStats.shotsPerSecond
    this.projectileSpeed = this.baseStats.projectileSpeed
    this.pulseRadius = this.baseStats.pulseRadius
    this.pulseCooldown = this.baseStats.pulseCooldown
    this.pierce = 0
    this.fanAngles = [0]
    this.firing = false
    this.skill = { ready: true, cooldownRemaining: 0, buffRemaining: 0, lastRejected: null }
    this.aimDirection = { ...this.config.initialAimDirection }
    const object = this.getPhysicsObject()
    this.aimPoint = { x: object.x + this.aimDirection.x, y: object.y + this.aimDirection.y }
    this._shotCooldown = 0
    this._shotSerial = 0
    this._dead = false
    this._actionClip = null
    this._receivedAttacks = new Set()
    this.parent.getChild('Room')?.bindNode(this)
    this.getVisualObject()?.setDepth(this.parent.config.depths.character)
    this.playAnim('idle', { restart: false })
  }

  update(dt) {
    const director = this.parent
    const body = this.getPhysicsObject()?.body
    const input = this.parent.getChild('Input')
    if (!body || !input || !['combat', 'route'].includes(director.runState) || this._dead) {
      body?.setVelocity(0, 0)
      this.firing = false
      return
    }

    const dx = (input.isHeld('move_right') ? 1 : 0) - (input.isHeld('move_left') ? 1 : 0)
    const dy = (input.isHeld('move_down') ? 1 : 0) - (input.isHeld('move_up') ? 1 : 0)
    const length = Math.hypot(dx, dy) || 1
    const bloodPrayer = sigilEffect(this.parent.sigilRegistry, 'blood_prayer')
    const buffSpeed = this.skill.buffRemaining > 0 ? bloodPrayer.buffMovementSpeedMultiplier : 1
    body.setVelocity(dx / length * this.movementSpeed * buffSpeed, dy / length * this.movementSpeed * buffSpeed)
    const position = this.getPhysicsObject()
    this.aimPoint = { ...input.aim }
    const aimX = input.aim.x - position.x
    const aimY = input.aim.y - position.y
    const aimLength = Math.hypot(aimX, aimY)
    if (aimLength > this.config.aimDeadzone) this.aimDirection = { x: aimX / aimLength, y: aimY / aimLength }

    this._shotCooldown = Math.max(0, this._shotCooldown - dt)
    this.skill.cooldownRemaining = Math.max(0, this.skill.cooldownRemaining - dt)
    this.skill.buffRemaining = Math.max(0, this.skill.buffRemaining - dt)
    this.skill.ready = this.skill.cooldownRemaining <= 0
    if (this.skill.lastRejected === 'blood-prayer-low-hp' && this.hp - bloodPrayer.skillHpCost >= bloodPrayer.minimumHpAfterCost) this.skill.lastRejected = null
    if (director.runState === 'route') {
      this.firing = false
      this._updateVisualState(dx, dy)
      return
    }
    this.firing = input.isHeld('fire')
    if (this.firing && this._shotCooldown <= 0) this._fire()
    if (input.isPressed('skill')) this.useSkill()
    this._updateVisualState(dx, dy)
  }

  applySigils(ids) {
    this.ownedSigils = [...ids]
    const stats = derivePlayerStats(ids, this.hp, this.baseStats, this.parent.sigilRegistry)
    Object.assign(this, stats)
    this._shotDamageRaw = stats.shotDamage
    this.shotDamage = Math.round(stats.shotDamage)
  }

  heal(amount) { this.hp = clampHp(this.hp + amount, this.maxHp) }

  receiveDamage(amount, source = 'unknown', attackId = '') {
    if (source && typeof source === 'object') {
      attackId = source.attackId || attackId
      source = source.source || 'unknown'
    }
    if (this._dead || this.parent.runState !== 'combat') return false
    if (attackId && this._receivedAttacks.has(attackId)) return false
    if (attackId) this._receivedAttacks.add(attackId)
    this.hp = clampHp(this.hp - Math.round(amount), this.maxHp)
    this.emit('player_hurt', { amount: Math.round(amount), damageSource: source, attackId })
    if (this.hp <= 0) {
      this._dead = true
      this.getPhysicsObject().body.setVelocity(0, 0)
      this._actionClip = 'death'
      this.playAnim('death', { restart: true })
      this.emit('player_died', { damageSource: source })
    }
    return true
  }

  useSkill() {
    if (!this.skill.ready || this._dead) {
      this.skill.lastRejected = this.skill.ready ? 'dead' : 'cooldown'
      return false
    }
    const bloodPrayer = this.ownedSigils.includes('blood_prayer')
    const effect = sigilEffect(this.parent.sigilRegistry, 'blood_prayer')
    if (bloodPrayer && this.hp - effect.skillHpCost < effect.minimumHpAfterCost) {
      this.skill.lastRejected = 'blood-prayer-low-hp'
      return false
    }
    if (bloodPrayer) { this.hp -= effect.skillHpCost; this.skill.buffRemaining = effect.buffDuration }
    this.skill.cooldownRemaining = this.pulseCooldown
    this.skill.ready = false
    this.skill.lastRejected = null
    this._actionClip = 'skill'
    this.playAnim('skill', { restart: true })
    const position = this.getPhysicsObject()
    for (const projectile of this.findByTag('hostile_projectile')) {
      const object = projectile.getPhysicsObject()
      if (object && Phaser.Math.Distance.Between(position.x, position.y, object.x, object.y) <= this.pulseRadius) projectile.expire?.('pulse')
    }
    for (const enemy of this.findByTag('ordinary_enemy')) {
      const object = enemy.getPhysicsObject()
      if (object && Phaser.Math.Distance.Between(position.x, position.y, object.x, object.y) <= this.pulseRadius) enemy.receivePulse?.(position.x, position.y, this.config.pulseKnockback)
    }
    void this.parent.instantiate('entities/pureflame-pulse.node.json', { x: position.x, y: position.y, width: this.pulseRadius * 2, height: this.pulseRadius * 2 })
    this.emit('skill_used', { radius: this.pulseRadius })
    return true
  }

  _fire() {
    const effect = sigilEffect(this.parent.sigilRegistry, 'blood_prayer')
    this._shotCooldown = 1 / (this.shotsPerSecond * (this.skill.buffRemaining > 0 ? effect.buffShotsPerSecondMultiplier : 1))
    if (this._actionClip !== 'skill' || this.animationPlayer?.isFinished()) {
      this._actionClip = 'attack'
      this.playAnim('attack', { restart: true })
    }
    const origin = this.getPhysicsObject()
    const baseAngle = Math.atan2(this.aimDirection.y, this.aimDirection.x)
    const attackId = `player-${this.id}-${++this._shotSerial}`
    for (const offset of this.fanAngles) {
      void this.parent.instantiate('entities/ember-bolt.node.json', {
        x: origin.x + Math.cos(baseAngle + offset) * this.config.muzzleOffset,
        y: origin.y + Math.sin(baseAngle + offset) * this.config.muzzleOffset,
        angle: baseAngle + offset, speed: this.projectileSpeed, damage: this._shotDamageRaw,
        pierce: this.pierce, attackId
      })
    }
  }

  resetFiringCadence() {
    this._shotCooldown = 0
    this.firing = false
  }

  _updateVisualState(dx, dy) {
    this.getVisualObject()?.setFlipX(this.aimDirection.x < 0)
    if (this._dead) return
    if (this._actionClip && this.animationPlayer?.currentClipName === this._actionClip && !this.animationPlayer.isFinished()) return
    this._actionClip = null
    this.playAnim(dx || dy ? 'run' : 'idle', { restart: false })
  }

  resetForRun(x, y) {
    this._dead = false
    this._actionClip = null
    this._receivedAttacks.clear()
    this.resetFiringCadence()
    this.hp = this.baseStats.maxHp
    this.applySigils([])
    this.skill = { ready: true, cooldownRemaining: 0, buffRemaining: 0, lastRejected: null }
    this.getPhysicsObject().setPosition(x, y)
    this.getPhysicsObject().body.setVelocity(0, 0)
    this.playAnim('idle')
  }

  runtimeState() {
    const object = this.getPhysicsObject()
    const body = object?.body
    const bloodPrayer = sigilEffect(this.parent.sigilRegistry, 'blood_prayer')
    return {
      hp: this.hp, maxHp: this.maxHp,
      movementSpeed: this.movementSpeed * (this.skill.buffRemaining > 0 ? bloodPrayer.buffMovementSpeedMultiplier : 1), shotDamage: this.shotDamage,
      shotsPerSecond: this.shotsPerSecond * (this.skill.buffRemaining > 0 ? bloodPrayer.buffShotsPerSecondMultiplier : 1), projectileSpeed: this.projectileSpeed, pulseRadius: this.pulseRadius,
      position: { x: object?.x || 0, y: object?.y || 0 }, velocity: { x: body?.velocity.x || 0, y: body?.velocity.y || 0 },
      aimDirection: { ...this.aimDirection }, aimPoint: { ...this.aimPoint }, firing: this.firing, skill: { ...this.skill },
      animationClip: this.animationPlayer?.currentClipName || null
    }
  }
}
