// OpenWeather API Key 
const API_KEY = '886fd4ba10d0c75d11db9b67492a6ab6'; //free api key

// DOM Elements
const searchInput = document.querySelector('input[type="text"]');
const searchButton = document.querySelector('button:nth-of-type(1)');
const currentLocationButton = document.querySelector('button:nth-of-type(2)');
const cityNameElement = document.querySelector('.flex-1 h1');
const temperatureElement = document.querySelector('.text-yellow-300');
const windElement = document.querySelector('.text-blue-300');
const humidityElement = document.querySelector('.text-green-300');
const weatherIcon = document.querySelector('.flex-shrink-0 img');
const weatherConditionElement = document.querySelector('.flex-shrink-0 p');
const forecastContainer = document.querySelector('.grid');
const dropdownMenu = document.createElement('select');
dropdownMenu.className = 'recent-cities-dropdown';
// dropdownMenu.style.margin = '10px';
document.querySelector('.flex.flex-col.md\\:flex-row.items-center').appendChild(dropdownMenu);

// Initialize dropdown with no options
updateDropdownMenu([]);

// Load any previously searched cities from local storage
let recentCities = JSON.parse(localStorage.getItem('recentCities')) || [];

// Event Listeners
searchButton.addEventListener('click', () => {
  const city = searchInput.value.trim();
  if (city) {
    fetchWeatherData(city);
    updateDropdownMenu(recentCities);
  } else {
    alert('Please enter a valid city name.');
  }
});

currentLocationButton.addEventListener('click', () => {
  if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition(position => {
      const { latitude, longitude } = position.coords;
      fetchWeatherDataByCoords(latitude, longitude);
    });
  } else {
    alert('Geolocation is not supported by this browser.');
  }
});

dropdownMenu.addEventListener('change', function () {
  const city = this.value;
  if (city) fetchWeatherData(city);
});

// Fetch Weather Data by City Name
function fetchWeatherData(city) {
  const apiUrl = `https://api.openweathermap.org/data/2.5/weather?q=${city}&units=metric&appid=${API_KEY}`;

  fetch(apiUrl)
    .then(response => handleApiResponse(response))
    .then(data => {
      updateWeatherUI(data);
      fetchFiveDayForecast(data.coord.lat, data.coord.lon);
      addCityToDropdown(city);
    })
    .catch(error => handleApiError(error));
}

// Fetch Weather Data by Coordinates
function fetchWeatherDataByCoords(lat, lon) {
  const apiUrl = `https://api.openweathermap.org/data/2.5/weather?lat=${lat}&lon=${lon}&units=metric&appid=${API_KEY}`;

  fetch(apiUrl)
    .then(response => handleApiResponse(response))
    .then(data => {
      updateWeatherUI(data);
      fetchFiveDayForecast(lat, lon);
    })
    .catch(error => handleApiError(error));
}

// Fetch 5-Day Forecast Data
function fetchFiveDayForecast(lat, lon) {
  const apiUrl = `https://api.openweathermap.org/data/2.5/forecast?lat=${lat}&lon=${lon}&units=metric&appid=${API_KEY}`;

  fetch(apiUrl)
    .then(response => handleApiResponse(response))
    .then(data => updateFiveDayForecastUI(data))
    .catch(error => handleApiError(error));
}

// Handle API Response
function handleApiResponse(response) {
  if (!response.ok) {
    throw new Error(`API Error: ${response.statusText}`);
  }
  return response.json();
}

// Update Weather UI
function updateWeatherUI(data) {
  cityNameElement.textContent = data.name;
  temperatureElement.textContent = `${data.main.temp.toFixed(1)} °C`;
  windElement.textContent = `${data.wind.speed.toFixed(1)} km/h`;
  humidityElement.textContent = `${data.main.humidity.toFixed(1)} %`;
  weatherConditionElement.textContent = data.weather[0].main;
  updateWeatherIcon(data.weather[0].icon);
}

// Update 5-Day Forecast UI
function updateFiveDayForecastUI(data) {
  forecastContainer.innerHTML = ''; // Clear existing content
  const forecastList = data.list.filter(item => item.dt_txt.includes('12:00:00')); // 5 days at noon

  forecastList.forEach(forecast => {
    const forecastCard = document.createElement('div');
    forecastCard.className = 'bg-gray-800 rounded-lg p-4 text-center text-white transform transition-transform duration-300 hover:shadow-lg hover:shadow-blue-500/50 hover:-translate-y-2';

    forecastCard.innerHTML = `
      <p class="text-lg font-semibold mb-4">${forecast.dt_txt.split(' ')[0]}</p>
      <img src="https://openweathermap.org/img/wn/${forecast.weather[0].icon}.png" alt="Weather Icon" class="w-16 h-16 mx-auto mb-4">
      <div class="text-lg mt-2">
          <p class="flex items-center justify-center mb-1"><i class="fas fa-temperature-high mr-2"></i>Temperature:</p>
          <span class="text-yellow-300">${forecast.main.temp.toFixed(1)} °C</span>
      </div>
      <div class="text-lg mt-2">
          <p class="flex items-center justify-center mb-1"><i class="fas fa-wind mr-2"></i>Wind:</p>
          <span class="text-blue-300">${forecast.wind.speed.toFixed(1)} km/h</span>
      </div>
      <div class="text-lg mt-2">
          <p class="flex items-center justify-center mb-1"><i class="fas fa-tint mr-2"></i>Humidity:</p>
          <span class="text-green-300">${forecast.main.humidity.toFixed(1)} %</span>
      </div>
    `;

    forecastContainer.appendChild(forecastCard);
  });
}

// Update Weather Icon
function updateWeatherIcon(iconCode) {
  weatherIcon.src = `https://openweathermap.org/img/wn/${iconCode}@2x.png`;
}

// Handle API Errors
function handleApiError(error) {
  alert(`Failed to fetch weather data: ${error.message}`);
}

// Add City to Dropdown
function addCityToDropdown(city) {
  if (!recentCities.includes(city)) {
    recentCities.push(city);
    localStorage.setItem('recentCities', JSON.stringify(recentCities));
    updateDropdownMenu(recentCities);
  }
}

// Update Dropdown Menu with Recently Searched Cities
function updateDropdownMenu(cities) {
  dropdownMenu.innerHTML = '<option value="">History</option>'; // Default option
  cities.forEach(city => {
    const option = document.createElement('option');
    option.value = city;
    option.textContent = city;
    dropdownMenu.appendChild(option);
  });
}
