export function offerSigils(registry, ownedIds, rng, count) {
  const owned = new Set(ownedIds)
  const remaining = registry.filter(sigil => !owned.has(sigil.id))
  if (remaining.length <= count) return remaining.map(sigil => sigil.id)

  const shuffled = rng.shuffle(remaining)
  let offer = shuffled.slice(0, count)
  if (new Set(offer.map(item => item.category)).size < 2) {
    const replacement = shuffled.slice(count).find(item => item.category !== offer[0].category)
    if (replacement) offer[offer.length - 1] = replacement
  }
  return offer.map(sigil => sigil.id)
}

export function sigilById(registry, id) {
  return registry.find(sigil => sigil.id === id) || null
}
