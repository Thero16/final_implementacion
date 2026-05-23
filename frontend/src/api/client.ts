import axios from 'axios'
import keycloak from '../keycloak'

const api = axios.create({
  baseURL: 'http://localhost:8000/api/v1',
})

api.interceptors.request.use(async (config) => {
  try {
    await keycloak.updateToken(30)
  } catch {
    keycloak.login()
  }
  if (keycloak.token) {
    config.headers.Authorization = `Bearer ${keycloak.token}`
  }
  return config
})

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      keycloak.login()
    }
    return Promise.reject(err)
  },
)

export default api
