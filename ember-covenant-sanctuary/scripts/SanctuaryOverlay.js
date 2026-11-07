import { Node } from '/engine/Node.js'
import GameOverlayModule from '/modules/GameOverlayModule.js'

void Node

export default class SanctuaryOverlay extends GameOverlayModule {
  ready() {
    this.authority = null
    this.config = {
      ...this.config,
      style: { ...this.config.style, fontFamily: 'FusionPixel, monospace' },
      menus: [
        { id: 'title', title: '《烬契圣堂》', subtitle: '守住余烬，穿过七重圣堂。', pausesGame: false, buttons: [] },
        { id: 'pause', title: '余烬暂歇', subtitle: '圣堂时间已经冻结。', pausesGame: true, toggleKey: 'Escape', buttons: [
          { label: '继续', action: overlay => overlay.closeAuthority() },
          { label: '重新开始', action: overlay => overlay.replaceAuthority('restart-confirmation') },
          { label: '退出本局', action: 'quit' }
        ] },
        { id: 'restart-confirmation', title: '放弃本次契约？', subtitle: '当前路线、契印与进度都会消失。', pausesGame: true, buttons: [
          { label: '确认重新开始', action: 'restart' },
          { label: '返回', action: overlay => overlay.replaceAuthority('pause') }
        ] },
        { id: 'death', title: '余火熄灭', subtitle: '', pausesGame: true, buttons: [{ label: '重新开始', action: 'restart' }] },
        { id: 'victory', title: '最后的火种', subtitle: '', pausesGame: true, buttons: [{ label: '重新开始', action: 'restart' }] }
      ]
    }
    super.ready()
    for (const entry of this._menuDivs.values()) {
      const panel = entry.div.querySelector('[id$="-panel"]')
      if (panel) {
        panel.style.background = 'transparent'
        panel.style.width = `min(${this._style.panelWidth}px, 92%)`
        panel.style.height = 'auto'
        panel.style.minHeight = `${this._style.panelHeight}px`
        panel.style.maxHeight = '90%'
        panel.style.overflowY = 'auto'
        this.sceneTree.ui.setBackground(panel, this.config.surfaceKeys.panel)
      }
      const title = entry.div.querySelector('h2')
      if (title) title.style.letterSpacing = '0'
      const subtitle = entry.div.querySelector('p')
      if (subtitle) {
        subtitle.style.maxWidth = '90%'
        subtitle.style.whiteSpace = 'normal'
        subtitle.style.overflowWrap = 'anywhere'
        subtitle.style.lineHeight = '1.5'
      }
      for (const button of entry.div.querySelectorAll('button')) {
        button.style.letterSpacing = '0'
        button.style.backgroundColor = 'transparent'
        this.sceneTree.ui.setBackground(button, this.config.surfaceKeys.buttonIdle)
        button.addEventListener('mouseenter', () => this.sceneTree.ui.setBackground(button, this.config.surfaceKeys.buttonHover))
        button.addEventListener('mouseleave', () => this.sceneTree.ui.setBackground(button, this.config.surfaceKeys.buttonIdle))
      }
    }
  }

  showMenu(id) {
    if (id === 'pause' && this.parent.getChild('SigilChoice')?.isVisible()) return false
    if (this.authority && this.authority !== id) return false
    this.authority = id
    super.showMenu(id)
    return true
  }

  _toggleMenu(id) {
    this.parent.getChild('Input')?.suppressActionUntilRelease('pause')
    if (this.authority === id) this.closeAuthority()
    else this.showMenu(id)
  }

  replaceAuthority(id) {
    if (this.authority) {
      const entry = this._menuDivs.get(this.authority)
      if (entry) entry.div.style.display = 'none'
    }
    this.authority = id
    const next = this._menuDivs.get(id)
    if (next) next.div.style.display = 'flex'
    this._pauseGame()
  }

  closeAuthority() {
    if (this.authority) {
      const entry = this._menuDivs.get(this.authority)
      if (entry) entry.div.style.display = 'none'
    }
    this.authority = null
    this._resumeGame()
    this.parent.getChild('Input')?.suppressPointerUntilRelease()
  }

  showResult(kind, result) {
    const entry = this._menuDivs.get(kind)
    if (!entry) return
    const subtitle = entry.div.querySelector('p')
    const sigils = result.sigils.map(id => this.parent.sigilRegistry?.find(sigil => sigil.id === id)?.label || id).join('、') || '无'
    if (subtitle) subtitle.textContent = `抵达 Stage ${result.stage} · 契印 ${sigils} · 剩余生命 ${result.remainingHp}${result.damageSource ? ` · 来源 ${result.damageSource}` : ''}`
    this.authority = null
    this.showMenu(kind)
  }

  hideTitle() {
    const title = this._menuDivs.get('title')
    if (title) title.div.style.display = 'none'
    if (this.authority === 'title') this.authority = null
  }

  runtimeState() { return { ...super.runtimeState(), authority: this.authority } }
}
