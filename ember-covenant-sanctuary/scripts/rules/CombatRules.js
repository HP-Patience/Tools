export function sigilEffect(registry, id) {
  return registry?.find(sigil => sigil.id === id)?.effects || {}
}

export function derivePlayerStats(owned, hp, base, registry) {
  const stats = { ...base, hp: Math.min(hp, base.maxHp), pierce: 0, fanAngles: [0] }
  for (const id of owned) {
    const effect = sigilEffect(registry, id)
    stats.maxHp += effect.maxHpAdd || 0
    stats.movementSpeed *= effect.movementSpeedMultiplier || 1
    stats.shotDamage *= effect.shotDamageMultiplier || 1
    stats.shotsPerSecond *= effect.shotsPerSecondMultiplier || 1
    stats.projectileSpeed *= effect.projectileSpeedMultiplier || 1
    stats.pulseRadius *= effect.pulseRadiusMultiplier || 1
    if (Number.isFinite(effect.pulseCooldownSet)) stats.pulseCooldown = effect.pulseCooldownSet
    stats.pierce += effect.pierceAdd || 0
    if (Array.isArray(effect.fanAngles)) stats.fanAngles = [...effect.fanAngles]
  }
  stats.hp = Math.min(stats.hp, stats.maxHp)
  return stats
}

export function shotDamageAtHit(baseDamage, owned, registry, hp, maxHp, distance) {
  let damage = baseDamage
  const close = sigilEffect(registry, 'close_flame')
  if (owned.includes('close_flame')) damage *= distance <= close.closeThreshold ? close.closeDamageMultiplier : close.farDamageMultiplier
  const candle = sigilEffect(registry, 'last_candle')
  if (owned.includes('last_candle')) damage *= hp <= maxHp * candle.hpThresholdRate ? candle.lowHpDamageMultiplier : candle.highHpDamageMultiplier
  return Math.max(0, Math.round(damage))
}

export function clampHp(value, maxHp) {
  return Math.max(0, Math.min(maxHp, Math.round(value)))
}
