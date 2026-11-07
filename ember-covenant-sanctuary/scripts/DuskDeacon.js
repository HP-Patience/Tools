import EnemyController from './EnemyController.js'

export default class DuskDeacon extends EnemyController {
  ready() { super.ready(); this.behaviorState = 'approach' }

  update(dt) {
    super.update(dt)
    if (this._dying || this.parent.runState !== 'combat') return
    const vector = this.playerVector()
    if (this.behaviorState === 'approach') {
      if (vector.distance > this.config.attackRange + this.config.approachPadding) this.moveToward(vector.player.getPhysicsObject(), this.config.speed)
      else this._beginCast(vector.distance <= this.config.attackRange ? 'melee' : 'ranged')
      return
    }
    this.stop(); this._stateTime -= dt
    if (this.behaviorState.endsWith('-charge') && this._stateTime <= 0) {
      if (this.behaviorState === 'melee-charge') {
        this.behaviorState = 'active'; this._stateTime = this.config.meleeActive; this._attackKind = 'melee'
      } else {
        this._releaseFan(vector)
        this.behaviorState = 'active'; this._stateTime = 0; this._attackKind = 'ranged'
      }
    } else if (this.behaviorState === 'active' && ((this._attackKind === 'melee' && this._stateTime <= 0) || (this._attackKind === 'ranged' && !this.findByTag('damaging').some(node => node.groupAttackId === this.attackId)))) {
      this.behaviorState = 'recover'; this._stateTime = this._attackKind === 'melee' ? this.config.meleeRecovery : this.config.rangedRecovery
    } else if (this.behaviorState === 'recover' && this._stateTime <= 0) {
      this.behaviorState = 'approach'; this.attackId = null
    }
  }

  _beginCast(kind) {
    this.faceDirection(this.playerVector().dx)
    this.stop(); this.behaviorState = `${kind}-charge`; this._stateTime = this.config[`${kind}Charge`]
    this.attackId = `deacon-${kind}-${this.id}-${this.scene.time.now}`
    this.playAnim(`${kind}-attack`)
    if (kind === 'melee') this._releaseMelee(this.playerVector())
  }

  _releaseMelee(vector) {
    const p = this.getPhysicsObject()
    void this.parent.instantiate('entities/deacon-melee.node.json', { x: p.x + vector.direction.x * this.config.meleeAreaOffset, y: p.y + vector.direction.y * this.config.meleeAreaOffset, attackId: this.attackId, warningDuration: this.config.meleeCharge })
  }

  _releaseFan(vector) {
    const p = this.getPhysicsObject(); const base = Math.atan2(vector.dy, vector.dx)
    this.config.rangedFanAngles.forEach((offset, index) => void this.parent.instantiate('entities/shadow-dart.node.json', {
      x: p.x, y: p.y, angle: base + offset, attackId: `${this.attackId}-${index}`, groupAttackId: this.attackId, sourceKind: 'Dusk Deacon fan'
    }))
  }
}
