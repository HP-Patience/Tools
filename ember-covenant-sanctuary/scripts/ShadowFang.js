import EnemyController from './EnemyController.js'

export default class ShadowFang extends EnemyController {
  ready() { super.ready(); this.behaviorState = 'approach' }

  update(dt) {
    super.update(dt)
    if (this._dying || this.parent.runState !== 'combat') return
    const vector = this.playerVector()
    if (this.behaviorState === 'approach') {
      if (vector.distance <= this.config.attackRange) {
        this.faceDirection(vector.dx)
        this.stop(); this.behaviorState = 'charge'; this._stateTime = this.config.chargeDuration
        this.attackId = `fang-${this.id}-${this.scene.time.now}`; this.playAnim('attack')
        const p = this.getPhysicsObject()
        void this.parent.instantiate('entities/fang-melee.node.json', {
          x: p.x + vector.direction.x * this.config.attackAreaOffset, y: p.y + vector.direction.y * this.config.attackAreaOffset,
          angle: Math.atan2(vector.direction.y, vector.direction.x), attackId: this.attackId,
          warningDuration: this.config.chargeDuration
        })
      } else this.moveToward(vector.player.getPhysicsObject(), this.config.speed)
    } else {
      this.stop(); this._stateTime -= dt
      if (this.behaviorState === 'charge' && this._stateTime <= 0) {
        this.behaviorState = 'strike'; this._stateTime = this.config.activeDuration
      } else if (this.behaviorState === 'strike' && this._stateTime <= 0) {
        this.behaviorState = 'recover'; this._stateTime = this.config.recoveryDuration
      } else if (this.behaviorState === 'recover' && this._stateTime <= 0) {
        this.behaviorState = 'approach'; this.attackId = null
      }
    }
  }
}
