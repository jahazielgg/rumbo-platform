export interface SearchableDestination {
  label: string
  detail: string
}

/** Accent-insensitive, case-insensitive AND search over destination name and location. */
export function filterDestinations<T extends SearchableDestination>(
  destinations: readonly T[],
  query: string,
): T[] {
  const normalize = (value: string) =>
    value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('es').trim()

  const terms = normalize(query).split(/\s+/).filter(Boolean)
  if (!terms.length) return [...destinations]

  return destinations.filter((destination) => {
    const content = normalize(`${destination.label} ${destination.detail}`)
    return terms.every((term) => content.includes(term))
  })
}
