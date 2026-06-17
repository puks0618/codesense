import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Dashboard from './pages/Dashboard.jsx'
import RepoDetail from './pages/RepoDetail.jsx'
import PRReview from './pages/PRReview.jsx'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function useAuthToken() {
  const params = new URLSearchParams(window.location.search)
  const urlToken = params.get('token')
  if (urlToken) {
    localStorage.setItem('codesense_token', urlToken)
    window.history.replaceState({}, '', '/')
  }
  return localStorage.getItem('codesense_token')
}

function RequireAuth({ children }) {
  const token = useAuthToken()
  if (!token) {
    window.location.href = `${API_URL}/auth/github`
    return null
  }
  return children
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<RequireAuth><Dashboard /></RequireAuth>} />
        <Route path="/repos/:owner/:repo" element={<RequireAuth><RepoDetail /></RequireAuth>} />
        <Route path="/repos/:owner/:repo/reviews/:prNumber" element={<RequireAuth><PRReview /></RequireAuth>} />
      </Routes>
    </BrowserRouter>
  )
}
