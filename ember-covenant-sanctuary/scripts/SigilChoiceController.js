import { Node } from '/engine/Node.js'
import UpgradeChoiceModule from '/modules/UpgradeChoiceModule.js'
import { fetchJson } from '/engine/url.js'

void Node

const iconMarkup = sigil => `<img data-manifest-key="${sigil.iconKey}" alt="">`

function cardTerm(label, copy, className) {
  const row = document.createElement('div')
  row.className = `up-card-term ${className}`
  const tag = document.createElement('span')
  tag.className = 'up-card-term-label'
  tag.textContent = label
  const text = document.createElement('span')
  text.className = 'up-card-term-copy'
  text.textContent = copy
  row.append(tag, text)
  return row
}

export default class SigilChoiceController extends UpgradeChoiceModule {
  async ready() {
    const nodeConfig = this.config
    const data = await fetchJson('config/sigils.json')
    this.registry = data.sigils
    this.detailId = null
    this.selectedId = null
    this.optionIds = []
    this._selectCallback = null
    this.config = {
      ...nodeConfig,
      buffPool: this.registry.map(sigil => ({ ...sigil, icon: iconMarkup(sigil), desc: `收益：${sigil.benefit}\n代价：${sigil.cost}\n本局持续生效` })),
      onSelect: buff => this._commit(buff)
    }
    super.ready()
  }

  showOffer(ids, onSelect) {
    if (this._visible) return
    this.optionIds = [...ids]
    this.selectedId = null
    this.detailId = null
    this._lastPointerType = null
    this._selectCallback = onSelect
    this._buffPool = ids.map(id => this.registry.find(sigil => sigil.id === id)).filter(Boolean)
      .map(sigil => ({ ...sigil, icon: iconMarkup(sigil), desc: `收益：${sigil.benefit}\n代价：${sigil.cost}\n本局持续生效` }))
    this._choiceCount = this._buffPool.length
    this.sceneTree.running = false
    this.scene.scene.pause()
    super.show()
    const cards = [...(this._overlay?.querySelectorAll('.up-card') || [])]
    const cardById = new Map(this._options.map((option, index) => [option.id, cards[index]]))
    this._options = this.optionIds.map(id => this._buffPool.find(option => option.id === id)).filter(Boolean)
    const cardRoot = this._overlay?.querySelector('.up-cards')
    this._options.forEach((option, index) => {
      const card = cardById.get(option.id)
      if (!card) return
      card.dataset.idx = String(index)
      card.dataset.choiceId = option.id
      card.setAttribute('aria-pressed', 'false')
      card.setAttribute('aria-label', `${option.label}。收益：${option.benefit}。代价：${option.cost}。本局持续生效。`)
      const label = card.querySelector('.up-card-label')
      if (label) label.textContent = option.label
      const description = card.querySelector('.up-card-desc')
      description?.replaceChildren(
        cardTerm('收益', option.benefit, 'is-benefit'),
        cardTerm('代价', option.cost, 'is-cost'),
        cardTerm('持续', '本局持续生效', 'is-duration')
      )
      const action = card.querySelector('.up-card-key')
      if (action) {
        const key = document.createElement('span')
        key.className = 'up-card-key-index'
        key.textContent = String(index + 1)
        const copy = document.createElement('span')
        copy.className = 'up-card-key-label'
        action.replaceChildren(key, copy)
      }
      cardRoot?.appendChild(card)
    })
    for (const image of this._overlay?.querySelectorAll('[data-manifest-key]') || []) this.sceneTree.ui.setImage(image, image.dataset.manifestKey)
    for (const card of this._overlay?.querySelectorAll('.up-card') || []) this.sceneTree.ui.setBackground(card, this.config.cardSurfaceKey)
    this._syncCardActions()
    this._pointerTypeHandler = event => { this._lastPointerType = event.pointerType }
    this._overlay?.addEventListener('pointerdown', this._pointerTypeHandler, true)
    this._choiceResizeObserver = new ResizeObserver(() => this._syncCardActions())
    const mount = document.querySelector(this._mountSelector)
    if (mount) this._choiceResizeObserver.observe(mount)
  }

  _select(idx) {
    const option = this._options[idx]
    if (!option) return
    const touch = this._usesTouchChoice()
    if (touch && this.detailId !== option.id) {
      this.detailId = option.id
      this._syncCardActions()
      return
    }
    this.selectedId = option.id
    super._select(idx)
  }

  _usesTouchChoice() {
    const controls = document.querySelector('#touch-controls')
    const controlsVisible = controls && getComputedStyle(controls).display !== 'none'
    return this._lastPointerType === 'touch' || controlsVisible
  }

  _syncCardActions() {
    const touch = this._usesTouchChoice()
    document.querySelector('#touch-controls')?.classList.toggle('is-choice-layout', touch)
    this._overlay?.querySelectorAll('.up-card').forEach(card => {
      const isDetail = card.dataset.choiceId === this.detailId
      card.classList.toggle('is-detail', isDetail)
      card.setAttribute('aria-pressed', String(isDetail))
      const label = card.querySelector('.up-card-key-label')
      if (label) label.textContent = touch ? (isDetail ? '再次点击确认' : '查看详情') : '选择此契印'
    })
  }

  _teardown() {
    this._choiceResizeObserver?.disconnect()
    this._choiceResizeObserver = null
    document.querySelector('#touch-controls')?.classList.remove('is-choice-layout')
    super._teardown()
  }

  _commit(buff) {
    this.selectedId = buff.id
    this.scene.scene.resume()
    this.sceneTree.running = true
    this.parent.getChild('Input')?.suppressPointerUntilRelease()
    this._selectCallback?.(buff.id)
  }

  runtimeState() { return { visible: this._visible, optionIds: [...this.optionIds], detailId: this.detailId, selectedId: this.selectedId } }
}
