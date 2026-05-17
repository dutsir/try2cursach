import { useEffect, useState, useCallback } from 'react'
import type { User } from '@/types'

interface AuthContextType {
  user: User | null
  loading: boolean
  isAuth: boolean
  logout: () => Promise<void>
}

const initialState: AuthContextType = {
  user: null,
  loading: true,
  isAuth: false,
  logout: async () => {},
}

let authState = initialState

export function useAuth(): AuthContextType {
  const [state, setState] = useState(initialState)

  useEffect(() => {
    setState(authState)
  }, [])

  const logout = useCallback(async () => {
    try {
      await fetch('/api/auth/logout/', { method: 'POST', credentials: 'include' })
      authState = initialState
      setState(initialState)
    } catch (e) {
      console.error('Logout error:', e)
    }
  }, [])

  return { ...state, logout }
}

export async function initAuth(): Promise<User | null> {
  try {
    const res = await fetch('/api/auth/me/', { credentials: 'include' })
    if (res.ok) {
      const user = await res.json()
      authState = { user, loading: false, isAuth: true, logout: async () => {} }
      return user
    }
  } catch (e) {
    console.error('Auth check failed:', e)
  }
  authState = { ...initialState, loading: false }
  return null
}
