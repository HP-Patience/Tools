import { Node } from '/engine/Node.js'

const ACTIONS = ['move_up', 'move_down', 'move_left', 'move_right', 'fire', 'skill', 'interact', 'pause']

export default class CombatInput extends Node {
  ready() {
    const width = Number(this.scene.game.config.width)
    const height = Number(this.scene.game.config.height)
    this.aim = { x: width * this.config.initialAim.xRate, y: height * this.config.initialAim.yRate }
    this.heldActions = []
    this.pointerFireSuppressed = false
    this.touchControlsVisible = false
    this.inputSource = 'desktop'
    this.actionState = Object.fromEntries(ACTIONS.map(action => [action, false]))
    this._touchHeld = new Set()
    this._touchPressed = new Set()
    this._framePressed = new Set()
    this._suppressedActions = new Set()
    this._pointerFire = false
    this._pointerPressed = false
    this._mountControls()
    this._bindPointer()
    this._postUpdate = () => { this._touchPressed.clear(); this._framePressed.clear(); this._pointerPressed = false }
    this.scene.events.on('postupdate', this._postUpdate)
  }

  update() {
    const input = this.sceneTree.inputMap
    this._framePressed.clear()
    if (this.parent.runState === 'title') {
      for (const action of ACTIONS) this.actionState[action] = false
      this.heldActions = []
      return
    }
    for (const action of ACTIONS) {
      const keyboardHeld = input?.isHeld(action) || false
      const keyboardPressed = input?.isPressed(action) || false
      const active = keyboardHeld || keyboardPressed || this._touchHeld.has(action) || this._touchPressed.has(action) || (action === 'fire' && (this._pointerFire || this._pointerPressed))
      if (this._suppressedActions.has(action) && !active) this._suppressedActions.delete(action)
      if (keyboardPressed && !this._suppressedActions.has(action)) this._framePressed.add(action)
      this.actionState[action] = this._suppressedActions.has(action) ? false : active
      if (keyboardHeld) this.inputSource = 'desktop'
    }
    this.heldActions = ACTIONS.filter(action => this.actionState[action])
  }

  isHeld(action) { return !!this.actionState[action] }

  isPressed(action) {
    if (this._suppressedActions.has(action)) return false
    if (this._framePressed.delete(action)) return true
    if (this._touchPressed.delete(action)) return true
    return this.sceneTree.inputMap?.isPressed(action) || false
  }

  suppressPointerUntilRelease() {
    if (this._pointerFire || this._touchHeld.has('fire')) this.pointerFireSuppressed = true
    this._pointerFire = false
    this._pointerPressed = false
    this._touchHeld.delete('fire')
  }

  suppressActionUntilRelease(action) { this._suppressedActions.add(action) }

  clearHeld() {
    this._pointerFire = false
    this._pointerPressed = false
    this._touchHeld.clear()
    this._touchPressed.clear()
    this._suppressedActions.clear()
    this.sceneTree.inputMap?.clearAllInjections?.()
    this.scene.input.keyboard?.resetKeys?.()
    for (const action of ACTIONS) this.actionState[action] = false
    this.heldActions = []
  }

  _bindPointer() {
    const canvas = this.scene.game.canvas
    this._pointerMove = event => {
      if (event.pointerType === 'touch') return
      this._updateDesktopAim(event)
      this.inputSource = 'desktop'
    }
    this._pointerDown = event => {
      if (event.pointerType === 'touch') return
      this._updateDesktopAim(event)
      this.inputSource = 'desktop'
      if (event.button === 0 && !this.pointerFireSuppressed) {
        this._pointerFire = true
        this._pointerPressed = true
      }
    }
    this._pointerUp = event => {
      if (event.pointerType === 'touch') return
      this._updateDesktopAim(event)
      this._pointerFire = false
      this.pointerFireSuppressed = false
    }
    this._pointerLeave = event => {
      if (event.pointerType === 'touch') return
      this._pointerFire = false
      this._pointerPressed = false
    }
    this._blur = () => this.clearHeld()
    canvas.addEventListener('pointermove', this._pointerMove)
    canvas.addEventListener('pointerdown', this._pointerDown)
    canvas.addEventListener('pointerup', this._pointerUp)
    canvas.addEventListener('pointerleave', this._pointerLeave)
    window.addEventListener('blur', this._blur)
  }

  _updateDesktopAim(event) {
    const canvas = this.scene.game.canvas
    const rect = canvas.getBoundingClientRect()
    if (!rect.width || !rect.height) return
    const screenX = (event.clientX - rect.left) * Number(this.scene.game.config.width) / rect.width
    const screenY = (event.clientY - rect.top) * Number(this.scene.game.config.height) / rect.height
    const world = this.scene.cameras.main.getWorldPoint(screenX, screenY)
    this.aim = { x: world.x, y: world.y }
  }

  _mountControls() {
    const root = document.createElement('div')
    root.id = 'touch-controls'
    root.className = this.touchControlsVisible ? 'is-visible' : ''
    root.innerHTML = `
      <div class="touch-dpad" aria-label="移动">
        <button data-action="move_up" class="north">▲</button>
        <button data-action="move_left" class="west">◀</button>
        <button data-action="move_right" class="east">▶</button>
        <button data-action="move_down" class="south">▼</button>
      </div>
      <div id="touch-aim" class="touch-aim" aria-label="瞄准并射击"><span>瞄准</span></div>
      <button data-action="skill" class="touch-command skill">净焰</button>
      <button data-action="interact" class="touch-command interact">交互</button>
      <button data-action="pause" class="touch-command pause">Ⅱ</button>`
    this.sceneTree.ui.mount(root)
    this._controls = root
    this.touchControlsVisible = getComputedStyle(root).display !== 'none'

    root.querySelectorAll('[data-action]').forEach(button => {
      const action = button.dataset.action
      const press = event => {
        event.preventDefault()
        this._enableTouchMode()
        this.inputSource = 'touch'
        this._touchHeld.add(action)
        this._touchPressed.add(action)
        button.setPointerCapture?.(event.pointerId)
      }
      const release = event => {
        event.preventDefault()
        this._touchHeld.delete(action)
      }
      button.addEventListener('pointerdown', press)
      button.addEventListener('pointerup', release)
      button.addEventListener('pointercancel', release)
    })

    const aim = root.querySelector('#touch-aim')
    const updateAim = event => {
      const rect = this.scene.game.canvas.getBoundingClientRect()
      const x = (event.clientX - rect.left) * (Number(this.scene.game.config.width) / rect.width)
      const y = (event.clientY - rect.top) * (Number(this.scene.game.config.height) / rect.height)
      if (x >= 0 && x <= Number(this.scene.game.config.width) && y >= 0 && y <= Number(this.scene.game.config.height)) this.aim = { x, y }
      this.inputSource = 'touch'
    }
    aim.addEventListener('pointerdown', event => {
      event.preventDefault()
      this._enableTouchMode()
      updateAim(event)
      if (!this.pointerFireSuppressed) {
        this._touchHeld.add('fire')
        this._touchPressed.add('fire')
      }
      aim.setPointerCapture?.(event.pointerId)
    })
    aim.addEventListener('pointermove', event => { if (this._touchHeld.has('fire')) updateAim(event) })
    const releaseAim = () => { this._touchHeld.delete('fire'); this.pointerFireSuppressed = false }
    aim.addEventListener('pointerup', releaseAim)
    aim.addEventListener('pointercancel', releaseAim)
    aim.addEventListener('pointerleave', releaseAim)
  }

  _enableTouchMode() {
    this.touchControlsVisible = true
    this._controls?.classList.add('is-visible')
  }

  runtimeState() {
    return {
      aim: { ...this.aim }, heldActions: [...this.heldActions], pointerFireSuppressed: this.pointerFireSuppressed,
      touchControlsVisible: this.touchControlsVisible, inputSource: this.inputSource, actionState: { ...this.actionState }
    }
  }

  destroy() {
    const canvas = this.scene.game.canvas
    canvas.removeEventListener('pointermove', this._pointerMove)
    canvas.removeEventListener('pointerdown', this._pointerDown)
    canvas.removeEventListener('pointerup', this._pointerUp)
    canvas.removeEventListener('pointerleave', this._pointerLeave)
    window.removeEventListener('blur', this._blur)
    this.scene.events.off('postupdate', this._postUpdate)
    this._controls?.remove()
  }
}
