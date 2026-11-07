export function seedFromQuery() {
  const raw = new URLSearchParams(window.location.search).get('seed')
  if (raw !== null && raw !== '') return hashSeed(raw)
  const words = new Uint32Array(1)
  crypto.getRandomValues(words)
  return words[0] || 0x9e3779b9
}

export function hashSeed(value) {
  let h = 2166136261 >>> 0
  for (const ch of String(value)) {
    h ^= ch.charCodeAt(0)
    h = Math.imul(h, 16777619)
  }
  return h >>> 0
}

export default class SeededRng {
  constructor(seed) { this.state = (Number(seed) >>> 0) || 0x9e3779b9 }

  next() {
    let x = this.state
    x ^= x << 13
    x ^= x >>> 17
    x ^= x << 5
    this.state = x >>> 0
    return this.state / 0x100000000
  }

  shuffle(values) {
    const result = [...values]
    for (let i = result.length - 1; i > 0; i--) {
      const j = Math.floor(this.next() * (i + 1))
      ;[result[i], result[j]] = [result[j], result[i]]
    }
    return result
  }
}
