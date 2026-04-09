import { useEffect } from 'react'

// eslint-disable-next-line no-restricted-syntax
export function useMountEffect(effect: () => void | (() => void)) {
  useEffect(effect, []) // eslint-disable-line react-hooks/exhaustive-deps
}
