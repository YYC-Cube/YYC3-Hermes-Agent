import { describe, expect, it } from 'vitest'

import { bestOllamaModel } from './custom-endpoints-settings'

describe('bestOllamaModel', () => {
  it('prefers a tool-capable model, then the largest served context', () => {
    const best = bestOllamaModel([
      { context_length: 131072, id: 'big-no-tools', tools: false },
      { context_length: 8192, id: 'small-tools', tools: true },
      { context_length: 65536, id: 'qwen3-coder-30b-64k', tools: true }
    ])

    expect(best?.id).toBe('qwen3-coder-30b-64k')
  })

  it('falls back to the largest context when nothing supports tools', () => {
    const best = bestOllamaModel([
      { context_length: 4096, id: 'a', tools: false },
      { context_length: 32768, id: 'b', tools: false }
    ])

    expect(best?.id).toBe('b')
  })

  it('returns null for an empty scan', () => {
    expect(bestOllamaModel([])).toBeNull()
  })
})
