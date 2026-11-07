export function nextWaypoint(room, from, target, tileSize) {
  if (!room?.isPassable) return target
  const start = { x: Math.floor(from.x / tileSize), y: Math.floor(from.y / tileSize) }
  const goal = { x: Math.floor(target.x / tileSize), y: Math.floor(target.y / tileSize) }
  const key = point => `${point.x},${point.y}`
  const queue = [start]
  const previous = new Map([[key(start), null]])
  const directions = [{ x: 1, y: 0 }, { x: 0, y: 1 }, { x: -1, y: 0 }, { x: 0, y: -1 }]

  while (queue.length) {
    const current = queue.shift()
    if (current.x === goal.x && current.y === goal.y) break
    for (const delta of directions) {
      const next = { x: current.x + delta.x, y: current.y + delta.y }
      if (previous.has(key(next)) || !room.isPassable(next.x, next.y)) continue
      previous.set(key(next), current)
      queue.push(next)
    }
  }

  if (!previous.has(key(goal))) return target
  let step = goal
  while (previous.get(key(step)) && key(previous.get(key(step))) !== key(start)) step = previous.get(key(step))
  return { x: (step.x + 0.5) * tileSize, y: (step.y + 0.5) * tileSize }
}
