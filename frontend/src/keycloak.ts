import Keycloak from 'keycloak-js'

const keycloak = new Keycloak({
  url: 'http://localhost:8080',
  realm: 'f1-realm',
  clientId: 'f1-frontend',
})

export default keycloak
