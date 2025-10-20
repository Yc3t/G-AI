import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import { Layout } from './components/Layout'
import { RecorderPage } from './pages/RecorderPage'
import { MeetingAnalysisPage } from './pages/MeetingAnalysisPage'
import { DatabasePage } from './pages/DatabasePage'
import { ContactsPage } from './pages/ContactsPage'

function App() {
  return (
    <Router>
      <Layout>
        <Routes>
          <Route path="/" element={<RecorderPage />} />
          <Route path="/meeting/:id" element={<MeetingAnalysisPage />} />
          <Route path="/database" element={<DatabasePage />} />
          <Route path="/table" element={<ContactsPage />} />
        </Routes>
      </Layout>
    </Router>
  )
}

export default App