import ApiConfig from "../config/apiConfig";

export interface WeatherResponse {
  temperature: number;
  windspeed: number;
  weathercode: number;
  time: string;
}

export async function fetchCurrentWeather(latitude: number, longitude: number): Promise<WeatherResponse> {
  const url = `${ApiConfig.weatherBaseURL}?latitude=${latitude}&longitude=${longitude}&current_weather=true&timezone=America%2FArgentina%2FBuenos_Aires`;
  const response = await fetch(url);

  if (!response.ok) {
    throw new Error(`Weather API request failed with status ${response.status}`);
  }

  const data = await response.json();

  if (!data.current_weather) {
    throw new Error("Weather API no devolvió datos actuales.");
  }

  return {
    temperature: Number(data.current_weather.temperature),
    windspeed: Number(data.current_weather.windspeed),
    weathercode: Number(data.current_weather.weathercode),
    time: String(data.current_weather.time),
  };
}
