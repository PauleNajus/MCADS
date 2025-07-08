document.addEventListener('DOMContentLoaded', () => {
  const themeToggle = document.querySelector('.theme-toggle');
  const prefersDarkScheme = window.matchMedia('(prefers-color-scheme: dark)');
  
  // Function to set the theme
  const setTheme = (themeName) => {
    document.documentElement.setAttribute('data-bs-theme', themeName);
    localStorage.setItem('theme', themeName);
    updateThemeIcon(themeName);
  };
  
  // Function to toggle the theme
  const toggleTheme = () => {
    const currentTheme = getCurrentTheme();
    if (currentTheme === 'dark') {
      setTheme('light');
    } else {
      setTheme('dark');
    }
  };
  
  // Function to get current theme, respecting user preferences
  const getCurrentTheme = () => {
    // If user is authenticated and has preferences, use those
    if (window.userPreferences && window.userPreferences.theme && window.userPreferences.theme !== 'auto') {
      return window.userPreferences.theme;
    }
    
    // Fall back to localStorage or system preference
    const storedTheme = localStorage.getItem('theme');
    if (storedTheme && storedTheme !== 'auto') {
      return storedTheme;
    }
    
    // Use system preference for 'auto' or if no preference is set
    return prefersDarkScheme.matches ? 'dark' : 'light';
  };
  
  // Function to update the icon
  const updateThemeIcon = (themeName) => {
    if (!themeToggle) return;
    
    if (themeName === 'dark') {
      themeToggle.innerHTML = '<i class="bi bi-sun-fill"></i>';
      themeToggle.setAttribute('title', 'Switch to light mode');
    } else {
      themeToggle.innerHTML = '<i class="bi bi-moon-fill"></i>';
      themeToggle.setAttribute('title', 'Switch to dark mode');
    }
  };
  
  // Initialize theme based on user preferences or stored preferences
  const initializeTheme = () => {
    const theme = getCurrentTheme();
    setTheme(theme);
  };
  
  // Add event listener to theme toggle button
  if (themeToggle) {
    themeToggle.addEventListener('click', toggleTheme);
  }
  
  // Listen for system theme changes when user preference is 'auto'
  prefersDarkScheme.addEventListener('change', (e) => {
    const userTheme = window.userPreferences?.theme || localStorage.getItem('theme');
    if (!userTheme || userTheme === 'auto') {
      setTheme(e.matches ? 'dark' : 'light');
    }
  });
  
  // Initialize the theme
  initializeTheme();
}); 