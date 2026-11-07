import { Node } from '/engine/Node.js'
import { shotDamageAtHit } from './rules/CombatRules.js'

export default class CombatProjectile extends Node {
  ready() {
    this.ownerSide = this.config.ownerSide || 'enemy'
    this.damage = Number(this.config.damage) || 0
    this.pierceRemaining = Number(this.config.pierce) || 0
    this.attackId = this.config.attackId || `${this.ownerSide}-${this.id}`
    this.groupAttackId = this.config.groupAttackId || this.attackId
    this.hitRegistered = false
    this._spent = false
    this._hitTargets = new Set()
    this._overlaps = []
    const angle = Number(this.config.angle) || 0
    const speed = Number(this.config.speed) || 0
    const object = this.getPhysicsObject()
    this.getVisualObject()?.setDepth(this.parent.config.depths.projectile)
    object.setRotation(angle)
    object.body.setVelocity(Math.cos(angle) * speed, Math.sin(angle) * speed)
    this.parent.getChild('Room')?.bindNode(this)
    const targets = this.ownerSide === 'player' ? this.findByTag('enemy') : this.findByTag('player')
    for (const target of targets) {
      this._overlaps.push(this.scene.physics.add.overlap(object, target.getPhysicsObject(), () => this._hit(target)))
    }
  }

  update() {
    const object = this.getPhysicsObject()
    const padding = object?.body ? Math.max(object.body.halfWidth, object.body.halfHeight) : 0
    if (!object || !this.parent.getChild('Room')?.containsWorldPoint(object.x, object.y, padding)) this.expire()
  }

  _hit(target) {
    if (this._spent || this._hitTargets.has(target.id)) return
    this._hitTargets.add(target.id)
    if (this.ownerSide === 'player') {
      const player = this.findByTag('player')[0]
      const p = player?.getPhysicsObject()
      const t = target.getPhysicsObject()
      const distance = p && t ? Phaser.Math.Distance.Between(p.x, p.y, t.x, t.y) : Infinity
      const finalDamage = shotDamageAtHit(this.damage, player?.ownedSigils || [], this.parent.sigilRegistry, player?.hp || 0, player?.maxHp || 1, distance)
      target.receiveDamage?.(finalDamage, this.attackId, { showDamageNumber: true })
    } else {
      target.receiveDamage?.(this.damage, this.config.sourceKind || 'projectile', this.attackId)
    }
    this.hitRegistered = true
    if (this.pierceRemaining > 0) this.pierceRemaining--
    else this.expire()
  }

  expire(reason = 'expired') {
    if (this._spent) return
    this._spent = true
    if (this.ownerSide === 'enemy') {
      const object = this.getPhysicsObject()
      if (object) void this.parent.instantiate('entities/projectile-clear.node.json', {
        x: object.x,
        y: object.y,
        label: reason,
        depth: this.parent.config.depths.feedback,
      })
    }
    this.removeSelf()
  }

  runtimeState() {
    return { ownerSide: this.ownerSide, damage: Math.round(this.damage), pierceRemaining: this.pierceRemaining, attackId: this.attackId, hitRegistered: this.hitRegistered }
  }

  destroy() {
    for (const overlap of this._overlaps) overlap?.destroy?.()
    this._overlaps = []
    this.parent?.getChild('Room')?.unbindNode(this)
  }
}
