// frontend/tailwind.config.js
/** @type {import('tailwindcss').Config} */
export default {
    content: [
        "./index.html", // Головний HTML-файл Vite
        "./src/**/*.{vue,js,ts,jsx,tsx}", // Усі файли Vue та JS/TS у директорії src
    ],
    theme: {
        extend: {
            fontFamily: { // Додаємо шрифт Inter, як у наданому дизайні
                sans: ['Inter', 'sans-serif'],
            },
        },
    },
    plugins: [],
}