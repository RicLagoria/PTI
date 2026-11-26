// Prueba de carga con k6 (Entrega 6 de PDC). La corre pdc/medir-escalado.sh.
//
// Simula usuarios mirando el mapa: cada uno pide teselas del ortomosaico (lo
// más pesado que hace cliente-api en uso normal: lee el COG y arma un PNG) y
// de vez en cuando el listado de imágenes y las estadísticas.
// Rampa: 0 -> VUS usuarios en 15 s, VUS durante 45 s, bajada en 5 s.
import http from "k6/http";
import { check, sleep } from "k6";

const BASE = __ENV.BASE || "https://gateway/api";
const VUS = Number(__ENV.VUS || 30);

export const options = {
  // El certificado del gateway es autofirmado y el nombre "gateway" no figura
  // en él: solo para esta prueba interna se salta la verificación.
  insecureSkipTLSVerify: true,
  stages: [
    { duration: "15s", target: VUS },
    { duration: "45s", target: VUS },
    { duration: "5s", target: 0 },
  ],
  thresholds: {
    http_req_failed: ["rate<0.01"],    // menos de 1% de errores
    http_req_duration: ["p(95)<2000"], // p95 por debajo de 2 s
  },
};

// Coordenadas de tesela (esquema XYZ) de un punto.
function tesela(lat, lon, z) {
  const n = 2 ** z;
  const x = Math.floor(((lon + 180) / 360) * n);
  const r = (lat * Math.PI) / 180;
  const y = Math.floor(((1 - Math.log(Math.tan(r) + 1 / Math.cos(r)) / Math.PI) / 2) * n);
  return [x, y];
}

export function setup() {
  const r = http.post(`${BASE}/auth/login`, JSON.stringify({ usuario: "lector", contrasena: "Lector2026!" }), {
    headers: { "Content-Type": "application/json" },
  });
  const token = r.json("token");
  const auth = { headers: { Authorization: `Bearer ${token}` } };
  const img = http.get(`${BASE}/imagenes`, auth).json()[0];
  // Las teselas de zoom 18 y 19 del interior del ortomosaico. Se deja afuera
  // un 15 % de cada borde: las teselas del borde dan 404 siempre (no tienen
  // píxeles), haya carga o no, y ensuciarían la tasa de errores.
  const [[s0, o0], [n0, e0]] = img.bounds;
  const mLat = (n0 - s0) * 0.15, mLon = (e0 - o0) * 0.15;
  const [s, o, nn, e] = [s0 + mLat, o0 + mLon, n0 - mLat, e0 - mLon];
  const lista = [];
  for (const z of [18, 19]) {
    const [x0, y0] = tesela(nn, o, z);
    const [x1, y1] = tesela(s, e, z);
    for (let x = x0; x <= x1; x++) for (let y = y0; y <= y1; y++) lista.push(`${z}/${x}/${y}`);
  }
  return { token, id: img.id, teselas: lista };
}

export default function (d) {
  const auth = { headers: { Authorization: `Bearer ${d.token}` }, tags: {} };
  if (Math.random() < 0.85) {
    const t = d.teselas[Math.floor(Math.random() * d.teselas.length)];
    auth.tags.tipo = "tesela";
    const r = http.get(`${BASE}/imagenes/${d.id}/tiles/${t}.png`, auth);
    check(r, { "tesela 200": (x) => x.status === 200 });
  } else {
    auth.tags.tipo = "listado";
    const r = http.get(`${BASE}/${Math.random() < 0.5 ? "imagenes" : "estadisticas"}`, auth);
    check(r, { "listado 200": (x) => x.status === 200 });
  }
  sleep(0.2);
}

export function handleSummary(datos) {
  return { [`/salida/resumen-${__ENV.ETIQUETA || "prueba"}.json`]: JSON.stringify(datos, null, 2) };
}
