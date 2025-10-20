import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, Edit2, Check, X } from 'lucide-react'
import { contactsApi } from '../services/api'

export const ContactsPage: React.FC = () => {
  const navigate = useNavigate()
  const [rows, setRows] = useState<Array<{ name: string; email?: string }>>([])
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [editingRow, setEditingRow] = useState<string | null>(null)
  const [editName, setEditName] = useState('')
  const [editEmail, setEditEmail] = useState('')

  const load = async () => {
    setLoading(true)
    try {
      const list = await contactsApi.list()
      setRows(list)
      setError(null)
    } catch (e) {
      setError('Error cargando contactos')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { void load() }, [])

  const save = async () => {
    if (!name.trim() || !email.trim()) {
      setError('Nombre y email son requeridos')
      return
    }
    try {
      await contactsApi.upsert(name.trim(), email.trim())
      setName('')
      setEmail('')
      setError(null)
      await load()
    } catch (e) {
      setError('Error guardando contacto')
    }
  }

  const startEdit = (row: { name: string; email?: string }) => {
    setEditingRow(row.name)
    setEditName(row.name)
    setEditEmail(row.email || '')
  }

  const cancelEdit = () => {
    setEditingRow(null)
    setEditName('')
    setEditEmail('')
  }

  const saveEdit = async (oldName: string) => {
    if (!editName.trim() || !editEmail.trim()) {
      setError('Nombre y email son requeridos')
      return
    }
    try {
      // If name changed, delete old and create new
      if (oldName !== editName.trim()) {
        await contactsApi.remove(oldName)
      }
      await contactsApi.upsert(editName.trim(), editEmail.trim())
      setEditingRow(null)
      setEditName('')
      setEditEmail('')
      setError(null)
      await load()
    } catch (e) {
      setError('Error actualizando contacto')
    }
  }

  const remove = async (n: string) => {
    try {
      await contactsApi.remove(n)
      await load()
    } catch (e) {
      setError('Error eliminando contacto')
    }
  }

  return (
    <div className="min-h-screen bg-white">
      {/* Header Navbar */}
      <header className="bg-white border-b border-gray-200 px-4 sm:px-6 py-3 sm:py-4">
        <div className="flex items-center justify-between">
          <button
            onClick={() => navigate('/database')}
            className="flex h-10 w-10 items-center justify-center rounded-full bg-white text-slate-600 ring-1 ring-slate-200 transition hover:text-slate-800 hover:ring-slate-300 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-slate-200"
            aria-label="Volver a base de datos"
          >
            <ArrowLeft className="h-5 w-5" />
          </button>
          <img
            src="/frumecar.jpg"
            alt="Frumecar"
            className="h-10 w-10 rounded-xl object-contain shadow-sm ring-1 ring-slate-200"
          />
          <div className="w-10"></div>
        </div>
      </header>

      {/* Main Content */}
      <div className="max-w-3xl mx-auto px-4 sm:px-6 py-6 space-y-6">
        <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">Tabla de Contactos</h1>
        {error && <div className="bg-red-100 text-red-700 px-3 py-2 rounded">{error}</div>}

        <div className="bg-white border rounded-lg p-4 space-y-3 shadow-sm">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <input
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="Nombre *"
              className="border rounded px-3 py-2 focus:ring-2 focus:ring-primary-500 focus:border-transparent"
              required
            />
            <input
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="Email *"
              className="border rounded px-3 py-2 focus:ring-2 focus:ring-primary-500 focus:border-transparent"
              required
            />
            <button
              onClick={save}
              className="bg-primary-600 text-white rounded px-4 py-2 hover:bg-primary-700 transition-colors disabled:opacity-50"
              disabled={!name.trim() || !email.trim()}
            >
              Agregar Contacto
            </button>
          </div>
        </div>

        <div className="bg-white border rounded-lg shadow-sm overflow-hidden">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="bg-gray-50 border-b">
                <th className="text-left p-3 font-semibold text-gray-900">Nombre</th>
                <th className="text-left p-3 font-semibold text-gray-900">Email</th>
                <th className="p-3"></th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td className="p-3" colSpan={3}>Cargando...</td></tr>
              ) : rows.length === 0 ? (
                <tr><td className="p-3 text-gray-500 italic" colSpan={3}>Sin contactos</td></tr>
              ) : rows.map(r => (
                <tr key={r.name} className="border-t hover:bg-gray-50 transition-colors">
                  {editingRow === r.name ? (
                    <>
                      <td className="p-3">
                        <input
                          value={editName}
                          onChange={e => setEditName(e.target.value)}
                          className="w-full border rounded px-2 py-1 text-sm focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                        />
                      </td>
                      <td className="p-3">
                        <input
                          type="email"
                          value={editEmail}
                          onChange={e => setEditEmail(e.target.value)}
                          className="w-full border rounded px-2 py-1 text-sm focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                        />
                      </td>
                      <td className="p-3 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <button
                            onClick={() => saveEdit(r.name)}
                            className="text-green-600 hover:text-green-800 transition-colors p-1 rounded hover:bg-green-50"
                            title="Guardar"
                          >
                            <Check className="h-4 w-4" />
                          </button>
                          <button
                            onClick={cancelEdit}
                            className="text-gray-600 hover:text-gray-800 transition-colors p-1 rounded hover:bg-gray-50"
                            title="Cancelar"
                          >
                            <X className="h-4 w-4" />
                          </button>
                        </div>
                      </td>
                    </>
                  ) : (
                    <>
                      <td className="p-3">{r.name}</td>
                      <td className="p-3 text-gray-600">{r.email || ''}</td>
                      <td className="p-3 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <button
                            onClick={() => startEdit(r)}
                            className="text-blue-600 hover:text-blue-800 transition-colors p-1 rounded hover:bg-blue-50"
                            title="Editar"
                          >
                            <Edit2 className="h-4 w-4" />
                          </button>
                          <button
                            onClick={() => remove(r.name)}
                            className="text-red-600 hover:text-red-800 transition-colors px-3 py-1 rounded hover:bg-red-50"
                          >
                            Eliminar
                          </button>
                        </div>
                      </td>
                    </>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}


