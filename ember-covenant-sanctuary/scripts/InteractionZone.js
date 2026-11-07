import { Node } from '/engine/Node.js'

export default class InteractionZone extends Node {
  ready() {
    this._overlapping = false
    this._touchedThisFrame = false
    this._locked = false
    const player = this.findByTag('player')[0]
    if (player) {
      this._overlap = this.scene.physics.add.overlap(this.getPhysicsObject(), player.getPhysicsObject(), () => { this._touchedThisFrame = true })
      this._worldStep = () => {
        if (this._touchedThisFrame && !this._overlapping) {
          this._overlapping = true
          this.parent.getChild('Room').routeFocus = this.config.interactionId
        } else if (!this._touchedThisFrame && this._overlapping) {
          this._overlapping = false
          if (this.parent.getChild('Room').routeFocus === this.config.interactionId) this.parent.getChild('Room').routeFocus = null
        }
        this._touchedThisFrame = false
      }
      this.scene.physics.world.on('worldstep', this._worldStep)
    }
  }

  update() {
    if (!this._overlapping || this._locked) return
    if (this.parent.getChild('Input')?.isPressed('interact')) {
      this._locked = true
      this.emit('interaction_activated', { interactionId: this.config.interactionId })
    }
  }

  destroy() {
    this._overlap?.destroy?.()
    if (this._worldStep) this.scene.physics.world.off('worldstep', this._worldStep)
    if (this.parent?.getChild('Room')?.routeFocus === this.config.interactionId) this.parent.getChild('Room').routeFocus = null
  }
}
