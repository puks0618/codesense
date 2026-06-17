import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const api = axios.create({ baseURL: BASE_URL })

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('codesense_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('codesense_token')
      window.location.href = `${BASE_URL}/auth/github`
    }
    return Promise.reject(err)
  },
)

export const getRepos = () => api.get('/api/repos').then((r) => r.data)

export const getRepoReviews = (owner, repo) =>
  api.get(`/api/repos/${owner}/${repo}/reviews`).then((r) => r.data)

export const getReview = (owner, repo, prNumber) =>
  api.get(`/api/repos/${owner}/${repo}/reviews/${prNumber}`).then((r) => r.data)

export const getMetrics = (owner, repo) =>
  api.get(`/api/repos/${owner}/${repo}/metrics`).then((r) => r.data)
