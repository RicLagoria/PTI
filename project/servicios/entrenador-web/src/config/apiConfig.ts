export default class ApiConfig {
  // En Docker, el nginx de entrenador-web expone ia-entrenamiento-api bajo /api.
  // En "npm run dev" sin Docker, el proxy de vite.config.ts reenvía /api a http://localhost:8002.
  static baseURL = "/api";

  // El login no lo atiende ia-entrenamiento-api: las cuentas son las del sitio
  // de análisis y las valida cliente-api. Los dos proxies reenvían /auth allá
  // (ver nginx.conf y vite.config.ts), así que desde el navegador sigue siendo
  // el mismo origen.
  static authURL = "/auth";
}
