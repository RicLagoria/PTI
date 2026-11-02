export default class ApiConfig {
  // En Docker, el nginx de entrenador-web expone ia-entrenamiento-api bajo /api.
  // En "npm run dev" sin Docker, el proxy de vite.config.ts reenvía /api a http://localhost:8002.
  static baseURL = "/api";
}
