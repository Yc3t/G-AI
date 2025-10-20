import React from 'react'
import { Link, useLocation } from 'react-router-dom'
import { Mic, Database, Home, Activity } from 'lucide-react'

interface LayoutProps {
  children: React.ReactNode
}

export const Layout: React.FC<LayoutProps> = ({ children }) => {
  const location = useLocation()

  const navItems = [
    { path: '/', label: 'Inicio', icon: Home },
    { path: '/recorder', label: 'Grabador', icon: Mic },
    { path: '/database', label: 'Base de Datos', icon: Database },
  ]

  const isActiveRoute = (path: string) => {
    if (path === '/') {
      return location.pathname === '/'
    }
    return location.pathname.startsWith(path)
  }

  return (
    <div className="min-h-screen">
      {children}
    </div>
  )
}
