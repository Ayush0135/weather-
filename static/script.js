document.addEventListener('DOMContentLoaded', () => {
    const cityInput = document.getElementById('city-input');
    const getWeatherBtn = document.getElementById('get-weather-btn');
    const errorMessage = document.getElementById('error-message');
    const weatherContainer = document.getElementById('weather-container');
    const hourlyContainer = document.getElementById('hourly-container');

    // UI Elements
    const cityNameEl = document.getElementById('city-name');
    const currentTempEl = document.getElementById('current-temp');
    const currentPressureEl = document.getElementById('current-pressure');
    const currentRainEl = document.getElementById('current-rain');
    const tomorrowMinEl = document.getElementById('tomorrow-min');
    const tomorrowMaxEl = document.getElementById('tomorrow-max');

    getWeatherBtn.addEventListener('click', fetchWeather);
    cityInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            fetchWeather();
        }
    });

    async function fetchWeather() {
        const city = cityInput.value.trim();
        if (!city) return;

        // Reset UI
        errorMessage.classList.add('hidden');
        weatherContainer.classList.add('hidden');
        getWeatherBtn.disabled = true;
        getWeatherBtn.textContent = 'Loading...';

        try {
            const response = await fetch(`/weather?city=${encodeURIComponent(city)}`);
            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Failed to fetch weather data');
            }

            updateUI(data);
        } catch (error) {
            showError(error.message);
        } finally {
            getWeatherBtn.disabled = false;
            getWeatherBtn.textContent = 'Get Weather';
        }
    }

    function updateUI(data) {
        cityNameEl.textContent = data.city;
        currentTempEl.textContent = data.current_temp;
        currentPressureEl.textContent = data.current_pressure;
        currentRainEl.textContent = data.current_rain;
        tomorrowMinEl.textContent = data.tomorrow_min;
        tomorrowMaxEl.textContent = data.tomorrow_max;

        // Hourly forecast
        hourlyContainer.innerHTML = '';
        data.hour_labels.forEach((label, index) => {
            const temp = data.hour_temps[index];
            const div = document.createElement('div');
            div.className = 'hour-item';
            div.innerHTML = `
                <span class="hour-time">${label}</span>
                <span class="hour-temp">${temp}°C</span>
            `;
            hourlyContainer.appendChild(div);
        });

        weatherContainer.classList.remove('hidden');
    }

    function showError(message) {
        errorMessage.textContent = message;
        errorMessage.classList.remove('hidden');
    }
});
