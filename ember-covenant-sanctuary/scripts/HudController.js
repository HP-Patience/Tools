import { Node } from '/engine/Node.js'

export default class HudController extends Node {
  ready() {
    const player = this.findByTag('player')[0]
    this.playerHpText = `${player.hp} / ${player.maxHp}`
    this.skillState = 'ready'
    this.bossBarVisible = false
    this.sigilIds = []
    this.damageNumberCount = 0
    this._damageNumbers = []
    const damageNumberLimit = Number(this.config.damageNumberLimit)
    if (!Number.isFinite(damageNumberLimit) || damageNumberLimit < 1) throw new Error('HudController requires a positive damageNumberLimit')
    this.damageNumberLimit = Math.floor(damageNumberLimit)
    this.damageNumberClusterRadius = Number(this.config.damageNumberClusterRadius)
    this.damageNumberOffset = {
      x: Number(this.config.damageNumberOffset?.x),
      y: Number(this.config.damageNumberOffset?.y)
    }
    if (!Number.isFinite(this.damageNumberClusterRadius) || this.damageNumberClusterRadius < 1) throw new Error('HudController requires a positive damageNumberClusterRadius')
    if (!Number.isFinite(this.damageNumberOffset.x) || !Number.isFinite(this.damageNumberOffset.y)) throw new Error('HudController requires finite damageNumberOffset coordinates')
    this.reticleBand = 'base'
    this.reticleTexture = 'aim_reticle'
    this.roomIntroVisible = false
    this.roomIntroText = ''
    this.exitFeedbackVisible = false
    this.exitFeedbackText = ''
    const hud = document.createElement('div')
    hud.id = 'sanctuary-hud'
    hud.innerHTML = `
      <div class="hud-left"><div id="hp-number">${this.playerHpText}</div><div id="skill-status"><img id="pureflame-icon" alt=""><span>净焰：就绪</span></div></div>
      <div id="sigil-list" class="sigil-list"><span class="empty-sigils">尚无契印</span></div><div id="owned-sigil-detail" class="owned-sigil-detail"></div>
      <div id="room-intro" class="room-intro"></div>
      <div id="boss-label" class="boss-label">失火主教</div>
      <img id="aim-reticle" class="aim-reticle" alt="">
      <div id="toast" class="toast"></div><div id="route-choice-labels" class="route-choice-labels"></div>`
    this.sceneTree.ui.mount(hud)
    this.sceneTree.ui.setImage(hud.querySelector('#pureflame-icon'), 'pureflame_icon')
    this.sceneTree.ui.setImage(hud.querySelector('#aim-reticle'), this.reticleTexture)
    this.element = hud
    this.playerBar = this.findByTag('player_bar')[0]
    this.bossBar = this.findByTag('boss_bar')[0]
    this._positionBar(this.playerBar)
    this._positionBar(this.bossBar)
    this.bossBar?.gameObject?.setVisible(false)
  }

  update(dt) {
    this.updateTimers(dt)
    const player = this.findByTag('player')[0]
    const director = this.parent
    if (!player) return
    this.playerHpText = `${player.hp} / ${player.maxHp}`
    this.element.querySelector('#hp-number').textContent = this.playerHpText
    this.playerBar.leftRate = player.hp / player.maxHp
    if (player.skill.lastRejected === 'blood-prayer-low-hp') this.skillState = 'rejected'
    else if (player.skill.buffRemaining > 0) this.skillState = 'buff'
    else if (player.skill.cooldownRemaining > 0) this.skillState = 'cooldown'
    else this.skillState = 'ready'
    const skillText = this.skillState === 'ready' ? '净焰：就绪' : this.skillState === 'buff' ? `血祷：${player.skill.buffRemaining.toFixed(this.config.timerPrecision)}s` : this.skillState === 'rejected' ? '血祷：生命不足' : `净焰：${player.skill.cooldownRemaining.toFixed(this.config.timerPrecision)}s`
    this.element.querySelector('#skill-status span').textContent = skillText

    this.sigilIds = [...director.ownedSigils]
    const list = this.element.querySelector('#sigil-list')
    const expected = this.sigilIds.join(',')
    if (list.dataset.ids !== expected) {
      list.dataset.ids = expected
      list.innerHTML = this.sigilIds.length ? '' : '<span class="empty-sigils">尚无契印</span>'
      for (const id of this.sigilIds) {
        const sigil = director.sigilRegistry?.find(item => item.id === id)
        const button = document.createElement('button')
        button.className = 'sigil-chip'; button.title = sigil ? `${sigil.benefit} / 代价：${sigil.cost}` : id
        button.setAttribute('aria-label', sigil?.label || id)
        const icon = document.createElement('img')
        icon.alt = ''
        if (sigil?.iconKey) this.sceneTree.ui.setImage(icon, sigil.iconKey)
        button.appendChild(icon)
        const show = () => {
          const detail = this.element.querySelector('#owned-sigil-detail')
          detail.innerHTML = `<strong>${sigil?.label || id}</strong><span>${sigil?.benefit || ''}</span><span>代价：${sigil?.cost || ''}</span>`
          detail.classList.add('is-visible')
        }
        const hide = () => this.element.querySelector('#owned-sigil-detail').classList.remove('is-visible')
        button.addEventListener('mouseenter', show); button.addEventListener('focus', show); button.addEventListener('click', show)
        button.addEventListener('mouseleave', hide); button.addEventListener('blur', hide)
        list.appendChild(button)
      }
    }

    const boss = this.findByTag('boss')[0]
    this.bossBarVisible = !!boss && director.config.stageDefs[String(director.stage)]?.kind === 'boss'
    this.bossBar?.gameObject?.setVisible(this.bossBarVisible)
    this.element.querySelector('#boss-label').classList.toggle('is-visible', this.bossBarVisible)
    if (boss && this.bossBar) this.bossBar.leftRate = boss.hp / boss.maxHp

    const reticle = this.element.querySelector('#aim-reticle')
    reticle.style.left = this._worldPercent(player.aimPoint.x, 'width'); reticle.style.top = this._worldPercent(player.aimPoint.y, 'height')
    const distance = Phaser.Math.Distance.Between(player.getPhysicsObject().x, player.getPhysicsObject().y, player.aimPoint.x, player.aimPoint.y)
    const closeThreshold = director.sigilRegistry?.find(sigil => sigil.id === 'close_flame')?.effects?.closeThreshold
    this.reticleBand = player.ownedSigils.includes('close_flame') ? (distance <= closeThreshold ? 'close' : 'far') : 'base'
    reticle.dataset.band = this.reticleBand
    const texture = this.reticleBand === 'close' ? 'aim_reticle_close' : 'aim_reticle'
    if (texture !== this.reticleTexture) {
      this.reticleTexture = texture
      this.sceneTree.ui.setImage(reticle, texture)
    }
  }

  showRoom(stage, name) {
    const el = this.element.querySelector('#room-intro')
    this.roomIntroText = `Stage ${stage} · ${name}`
    this.roomIntroVisible = true
    el.textContent = this.roomIntroText; el.classList.add('is-visible')
    this._introRemaining = this.config.introDuration
    this.exitFeedbackVisible = false
    this.exitFeedbackText = ''
  }

  showToast(text) {
    const el = this.element.querySelector('#toast'); el.textContent = text; el.classList.add('is-visible')
    this._toastRemaining = this.config.toastDuration
  }

  showExitFeedback(text = '出口已经开启') {
    this.exitFeedbackText = text
    this.exitFeedbackVisible = true
    this.showToast(text)
  }

  showRouteChoices(points, options) {
    const root = this.element.querySelector('#route-choice-labels')
    root.replaceChildren()
    for (const option of options) {
      const point = option.id === 'recovery' ? points.recovery : points.elite
      const label = document.createElement('div')
      label.className = `route-label ${option.id}`
      label.style.left = this._worldPercent(point[0], 'width'); label.style.top = this._worldPercent(point[1] + this.config.routeLabelOffset, 'height')
      label.innerHTML = `<strong>${option.label}</strong><span>${option.consequence}</span>`
      root.appendChild(label)
    }
  }

  hideRouteChoices() { this.element.querySelector('#route-choice-labels')?.replaceChildren() }

  addDamageNumber(amount, x, y) {
    const originX = Number(x)
    const originY = Number(y)
    const label = String(amount)
    const cluster = this._damageNumbers.find(item =>
      item.label === label && Phaser.Math.Distance.Between(item.originX, item.originY, originX, originY) <= this.damageNumberClusterRadius
    )
    if (cluster) {
      cluster.count++
      cluster.remaining = cluster.duration
      cluster.element.style.transform = 'translate(-50%,-50%)'
      cluster.element.style.opacity = '1'
      this._renderDamageNumber(cluster)
      return
    }

    while (this._damageNumbers.length >= this.damageNumberLimit) this._damageNumbers.shift().element.remove()
    const digit = document.createElement('span')
    digit.className = 'damage-number'
    const value = document.createElement('span')
    value.className = 'damage-number-value'
    const count = document.createElement('span')
    count.className = 'damage-number-count'
    digit.append(value, count)
    const playerX = this.findByTag('player')[0]?.getPhysicsObject()?.x ?? Number(this.scene.game.config.width) / 2
    const awayFromPlayer = originX < playerX ? -1 : 1
    digit.style.left = this._worldPercent(originX + awayFromPlayer * this.damageNumberOffset.x, 'width')
    digit.style.top = this._worldPercent(originY + this.damageNumberOffset.y, 'height')
    this.element.appendChild(digit)
    const item = {
      element: digit,
      value,
      countElement: count,
      label,
      count: 1,
      originX,
      originY,
      remaining: this.config.damageNumberDuration,
      duration: this.config.damageNumberDuration
    }
    this._renderDamageNumber(item)
    this._damageNumbers.push(item)
    this.damageNumberCount = this._damageNumbers.length
  }

  _renderDamageNumber(item) {
    item.value.textContent = item.label
    item.countElement.textContent = item.count > 1 ? `×${item.count}` : ''
    item.countElement.hidden = item.count === 1
    item.element.setAttribute('aria-label', item.count > 1 ? `${item.label}，连续 ${item.count} 次命中` : item.label)
  }

  updateTimers(dt) {
    if (this._introRemaining > 0 && (this._introRemaining -= dt) <= 0) { this.roomIntroVisible = false; this.element.querySelector('#room-intro').classList.remove('is-visible') }
    if (this._toastRemaining > 0 && (this._toastRemaining -= dt) <= 0) { this.exitFeedbackVisible = false; this.element.querySelector('#toast').classList.remove('is-visible') }
    for (const item of this._damageNumbers) {
      item.remaining -= dt
      const progress = Phaser.Math.Clamp(1 - item.remaining / item.duration, 0, 1)
      item.element.style.transform = `translate(-50%, calc(-50% - ${Math.round(progress * this.config.damageNumberRise)}px))`
      item.element.style.opacity = String(1 - progress)
    }
    const expired = this._damageNumbers.filter(item => item.remaining <= 0)
    for (const item of expired) item.element.remove()
    this._damageNumbers = this._damageNumbers.filter(item => item.remaining > 0)
    this.damageNumberCount = this._damageNumbers.length
  }

  runtimeState() {
    return {
      playerHpText: this.playerHpText, skillState: this.skillState, bossBarVisible: this.bossBarVisible,
      sigilIds: [...this.sigilIds], damageNumberCount: this.damageNumberCount, reticleBand: this.reticleBand, reticleTexture: this.reticleTexture,
      roomIntroVisible: this.roomIntroVisible, roomIntroText: this.roomIntroText,
      exitFeedbackVisible: this.exitFeedbackVisible, exitFeedbackText: this.exitFeedbackText
    }
  }

  _worldPercent(value, dimension) {
    return `${value / Number(this.scene.game.config[dimension]) * 100}%`
  }

  _positionBar(bar) {
    if (!bar?.container) return
    bar.container.setPosition(
      Number(this.scene.game.config.width) * bar.config.anchorX,
      Number(this.scene.game.config.height) * bar.config.anchorY
    )
  }

  destroy() {
    for (const item of this._damageNumbers) item.element.remove()
    this._damageNumbers = []
    this.damageNumberCount = 0
    this.element?.remove()
    this.element = null
  }
}
