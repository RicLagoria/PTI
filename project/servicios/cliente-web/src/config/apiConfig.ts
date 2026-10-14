export default class ApiConfig {
  // En Docker, nginx expone el backend bajo /api. En "npm run dev" sin Docker,
  // el proxy de vite.config.ts reenvía /api a http://localhost:8000.
  static baseURL = "/api";
  static weatherBaseURL = "https://api.open-meteo.com/v1/forecast";
}
