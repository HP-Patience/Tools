import { Node } from '/engine/Node.js'
import { nextWaypoint } from './rules/GridNavigator.js'

export default class EnemyController extends Node {
  ready() {
    this.kind = this.config.kind || 'enemy'
    this.hp = Number(this.config.hp) || 1
    this.maxHp = this.hp
    this.behaviorState = 'idle'
    this.attackId = null
    this.damageEnabled = true
    this._stateTime = 0
    this._deathTime = 0
    this._dying = false
    this._hitFlash = 0
    this.parent.getChild('Room')?.bindNode(this)
    this.getVisualObject()?.setDepth(this.parent.config.depths.character)
    this.playAnim('idle', { restart: false })
  }

  update(dt) {
    if (this.parent.runState !== 'combat' && !this._dying) this.stop()
    if (this._hitFlash > 0) {
      this._hitFlash -= dt
      this.getVisualObject()?.setTint(this._hitFlash > 0 ? this.parent.config.hitFlash.tint : this.parent.config.hitFlash.clearTint)
    }
    if (!this._dying) return
    this._deathTime -= dt
    if (this._deathTime <= 0) {
      const p = this.getPhysicsObject()
      if (!this.tags.includes('boss')) void this.parent.instantiate('entities/ash-burst.node.json', { x: p.x, y: p.y })
      this.emit('enemy_died', { kind: this.kind, boss: this.tags.includes('boss'), elite: this.tags.includes('elite') })
      this.removeSelf()
    }
  }

  receiveDamage(amount, attackId = '', feedback = null) {
    if (this._dying) return false
    const appliedDamage = Math.round(amount)
    this.hp = Math.max(0, this.hp - appliedDamage)
    this._hitFlash = this.parent.config.hitFlash.duration
    const p = this.getPhysicsObject()
    void this.parent.instantiate('entities/hit-spark.node.json', { x: p.x, y: p.y })
    if (feedback?.showDamageNumber) this.emit('damage_number', { amount: appliedDamage, x: p.x, y: p.y })
    this._afterDamage?.()
    if (this.hp <= 0) this.beginDeath()
    return true
  }

  beginDeath() {
    if (this._dying) return
    this._dying = true
    this.damageEnabled = false
    this.cancelOwnedAttack()
    this.behaviorState = 'dead'
    this.getPhysicsObject().body.setVelocity(0, 0)
    this.playAnim('death')
    this._deathTime = this.config.deathDuration
    this.emit('enemy_damage_disabled', { kind: this.kind })
  }

  receivePulse(originX, originY, distance) {
    if (!this.tags.includes('ordinary_enemy') || this._dying) return false
    const object = this.getPhysicsObject()
    const dx = object.x - originX
    const dy = object.y - originY
    const length = Math.hypot(dx, dy) || 1
    const room = this.parent.getChild('Room')
    let safe = { x: object.x, y: object.y }
    for (let step = this.parent.config.knockbackStep; step <= distance; step += this.parent.config.knockbackStep) {
      const candidate = room.clampWorldPoint(object.x + dx / length * step, object.y + dy / length * step)
      if (!room.isCirclePassable(candidate.x, candidate.y, object.body.halfWidth)) break
      safe = candidate
    }
    object.setPosition(safe.x, safe.y)
    if (this.behaviorState === 'charge') {
      this.cancelOwnedAttack()
      this.behaviorState = 'recover'
      this._stateTime = this.config.recoveryDuration
      this.attackId = null
    }
    return true
  }

  playerVector() {
    const player = this.findByTag('player')[0]
    const from = this.getPhysicsObject()
    const to = player?.getPhysicsObject()
    if (!to) return { player: null, dx: 0, dy: 0, distance: Infinity, direction: { x: 0, y: 0 } }
    const dx = to.x - from.x
    const dy = to.y - from.y
    const distance = Math.hypot(dx, dy) || 1
    return { player, dx, dy, distance, direction: { x: dx / distance, y: dy / distance } }
  }

  moveToward(target, speed) {
    const body = this.getPhysicsObject().body
    const from = this.getPhysicsObject()
    const room = this.parent.getChild('Room')
    const waypoint = nextWaypoint(room, from, target, room.tileSize())
    const dx = waypoint.x - from.x
    const dy = waypoint.y - from.y
    const length = Math.hypot(dx, dy) || 1
    this.faceDirection(dx)
    body.setVelocity(dx / length * speed, dy / length * speed)
    this.playAnim(this.config.moveClip || 'move', { restart: false })
  }

  stop() { this.getPhysicsObject().body.setVelocity(0, 0) }

  faceDirection(dx) {
    if (!Number.isFinite(dx) || Math.abs(dx) < this.parent.config.facingDeadzone) return
    this.getVisualObject()?.setFlipX(dx < 0)
  }

  cancelOwnedAttack() {
    if (!this.attackId) return
    for (const attack of this.findByTag('damaging')) {
      if (attack.attackId !== this.attackId && attack.groupAttackId !== this.attackId) continue
      if (typeof attack.expire === 'function') attack.expire()
      else attack.removeSelf()
    }
  }

  runtimeState() {
    return { kind: this.kind, hp: this.hp, maxHp: this.maxHp, behaviorState: this.behaviorState, attackId: this.attackId, damageEnabled: this.damageEnabled, animationClip: this.animationPlayer?.currentClipName || null }
  }

  destroy() { this.parent?.getChild('Room')?.unbindNode(this) }
}
