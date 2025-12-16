import { useCallback, useEffect, useState } from 'react'
import { contactsApi } from '../services/api'

export type ContactEntry = { name: string; email?: string | null }

export const useContactsList = (autoLoad = true) => {
  const [contacts, setContacts] = useState<ContactEntry[]>([])
  const [loadingContacts, setLoadingContacts] = useState(false)

  const reloadContacts = useCallback(async () => {
    setLoadingContacts(true)
    try {
      const list = await contactsApi.list()
      setContacts(Array.isArray(list) ? list : [])
    } catch (err) {
      console.error('Failed to load contacts', err)
    } finally {
      setLoadingContacts(false)
    }
  }, [])

  useEffect(() => {
    if (!autoLoad) return
    void reloadContacts()
  }, [autoLoad, reloadContacts])

  return { contacts, loadingContacts, reloadContacts }
}
