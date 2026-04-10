import axios from 'axios';

// When deployed to railway, the Flask backend should be made available under the same domain or via a specific URL.
// In dev Vite proxy will be used (configured in vite.config.js)
const API_BASE = '/api';

const backend = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json'
  }
});

// Helpful utility to set admin key
export const setAdminKey = (key) => {
  backend.defaults.headers.common['admin-key'] = key;
};

export default backend;
