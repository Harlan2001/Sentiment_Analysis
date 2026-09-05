import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { Loading } from './Loading'

describe('Loading', () => {
  it('渲染 spinner svg', () => {
    const { container } = render(<Loading />)
    expect(container.querySelector('svg')).not.toBeNull()
  })
})