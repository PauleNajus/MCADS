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
    if (localStorage.getItem('theme') === 'dark') {
      setTheme('light');
    } else {
      setTheme('dark');
    }
  };
  
  // Function to update the icon
  const updateThemeIcon = (themeName) => {
    if (themeName === 'dark') {
      themeToggle.innerHTML = '<i class="bi bi-sun-fill"></i>';
      themeToggle.setAttribute('title', 'Switch to light mode');
    } else {
      themeToggle.innerHTML = '<i class="bi bi-moon-fill"></i>';
      themeToggle.setAttribute('title', 'Switch to dark mode');
    }
  };
  
  // Set the initial theme based on localStorage or system preferences
  if (localStorage.getItem('theme') === null) {
    if (prefersDarkScheme.matches) {
      setTheme('dark');
    } else {
      setTheme('light');
    }
  } else {
    const theme = localStorage.getItem('theme');
    setTheme(theme);
  }
  
  // Add event listener to theme toggle button
  if (themeToggle) {
    themeToggle.addEventListener('click', toggleTheme);
  }
}); 