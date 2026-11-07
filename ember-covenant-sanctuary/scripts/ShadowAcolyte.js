import EnemyController from './EnemyController.js'

export default class ShadowAcolyte extends EnemyController {
  ready() {
    super.ready()
    this.behaviorState = 'move'
    this._attackGap = 0
    this._gameplayElapsed = 0
    this._lastAttackCommitTime = null
    this.attackCommitCount = 0
    this.lastAttackCommitInterval = null
  }

  update(dt) {
    super.update(dt)
    if (this._dying || this.parent.runState !== 'combat') return
    this._gameplayElapsed += dt
    this._attackGap = Math.max(0, this._attackGap - dt)
    const vector = this.playerVector()
    if (this.behaviorState === 'move') {
      if (vector.distance > this.config.desiredRange + this.config.farTolerance) this.moveToward(vector.player.getPhysicsObject(), this.config.speed)
      else if (vector.distance < this.config.desiredRange - this.config.nearTolerance) this.moveToward({ x: this.getPhysicsObject().x - vector.dx, y: this.getPhysicsObject().y - vector.dy }, this.config.speed)
      else {
        this.stop(); this.playAnim('idle', { restart: false })
        if (this._attackGap <= 0) {
          this.faceDirection(vector.dx)
          this.behaviorState = 'charge'; this._stateTime = this.config.chargeDuration
          this.attackId = `dart-${this.id}-${this.scene.time.now}`
          if (this._lastAttackCommitTime !== null) this.lastAttackCommitInterval = this._gameplayElapsed - this._lastAttackCommitTime
          this._lastAttackCommitTime = this._gameplayElapsed
          this.attackCommitCount++
          this._attackGap = this.config.minimumAttackInterval
          this.playAnim('ranged-attack')
        }
      }
    } else {
      this.stop(); this._stateTime -= dt
      if (this.behaviorState === 'charge' && this._stateTime <= 0) {
        const p = this.getPhysicsObject(); const angle = Math.atan2(vector.dy, vector.dx)
        void this.parent.instantiate('entities/shadow-dart.node.json', { x: p.x, y: p.y, angle, attackId: this.attackId })
        this.behaviorState = 'release'; this._stateTime = this.config.releaseDuration
      } else if (this.behaviorState === 'release' && this._stateTime <= 0) {
        this.behaviorState = 'recover'; this._stateTime = this.config.recoveryDuration
      } else if (this.behaviorState === 'recover' && this._stateTime <= 0) {
        this.behaviorState = 'move'; this.attackId = null
      }
    }
  }

  runtimeState() {
    return {
      ...super.runtimeState(),
      attackCommitCount: this.attackCommitCount,
      attackCommitTime: this._lastAttackCommitTime,
      lastAttackCommitInterval: this.lastAttackCommitInterval
    }
  }
}
