import { Node } from '/engine/Node.js'

export default class TelegraphedArea extends Node {
  ready() {
    this.phase = 'warning'
    this.attackId = this.config.attackId || `area-${this.id}`
    this.groupAttackId = this.config.groupAttackId || this.attackId
    this.damage = Number(this.config.damage) || 0
    this.warningDuration = Number(this.config.warningDuration) || 0
    this.hitPlayer = false
    this._elapsed = 0
    this.visualTexture = this.getVisualObject()?.texture?.key || null
    this.getVisualObject()?.setDepth(this.parent.config.depths.warning)
    const player = this.findByTag('player')[0]
    this._overlap = player ? this.scene.physics.add.overlap(this.getPhysicsObject(), player.getPhysicsObject(), () => this._hit()) : null
  }

  update(dt) {
    this._elapsed += dt
    if (this.phase === 'warning' && this._elapsed >= this.warningDuration) {
      this.phase = 'active'
      this._elapsed = 0
      this._setVisualTexture(this.config.impactTexture)
      this.getVisualObject()?.setDepth(this.parent.config.depths.feedback ?? this.parent.config.depths.projectile)
    } else if (this.phase === 'active' && this._elapsed >= Number(this.config.activeDuration)) {
      this.phase = 'done'
      this.removeSelf()
    }
  }

  _hit() {
    if (this.phase !== 'active' || this.hitPlayer) return
    if (this.config.bossOwned && !this.findByTag('boss')[0]?.damageEnabled) return
    this.hitPlayer = true
    this.findByTag('player')[0]?.receiveDamage(this.damage, this.config.sourceKind || 'attack-area', this.attackId)
  }

  _setVisualTexture(texture) {
    const visual = this.getVisualObject()
    if (!visual || !this.scene.textures.exists(texture)) {
      visual?.setVisible?.(false)
      console.error(`TelegraphedArea[${this.name || this.id}]: texture "${texture}" is not loaded`)
      this.emit('visual_asset_failed', { texture, kind: 'telegraphed-area', phase: this.phase })
      return
    }
    visual.setTexture(texture)
    visual.setVisible?.(true)
    this.visualTexture = texture
  }

  runtimeState() { return { phase: this.phase, attackId: this.attackId, warningDuration: this.warningDuration, damage: this.damage, hitPlayer: this.hitPlayer, visualTexture: this.visualTexture } }

  destroy() { this._overlap?.destroy?.(); this._overlap = null }
}
