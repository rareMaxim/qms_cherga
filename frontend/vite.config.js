import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueJsx from '@vitejs/plugin-vue-jsx'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'
import { resolve } from 'path'
import { visualizer } from 'rollup-plugin-visualizer'
import Icons from 'unplugin-icons/vite'
import Components from 'unplugin-vue-components/vite'
import IconsResolver from 'unplugin-icons/resolver'
import LucideIcons from './lucideIcons'
import vueDevTools from 'vite-plugin-vue-devtools'

export default defineConfig({
    // ВАЖЛИВО: base має відповідати тому, як Frappe буде генерувати URL до ваших JS/CSS файлів.
    // Якщо JS/CSS файли будуть лежати в qms_cherga/public/js та qms_cherga/public/css,
    // то Frappe зазвичай робить їх доступними за URL /assets/qms_cherga/js/ та /assets/qms_cherga/css/.
    base: '/assets/qms_cherga/',

    plugins: [
        vue(),
        vueJsx(),
        vueDevTools(),
        tailwindcss(),
        Components({
            resolvers: [IconsResolver({ prefix: false, enabledCollections: ['lucide'] })],
        }),
        Icons({
            customCollections: {
                lucide: LucideIcons,
            },
        }),
        visualizer({ emitFile: true }),
        // Плагін transformIndexHtml тут може не мати сенсу, якщо ви будете генерувати
        // HTML-файли вручну або через шаблони Frappe, а не модифікувати вихідний index.html від Vite.
        // Якщо ви все ж використовуєте index.html від Vite як основу для ваших сторінок у www/cherga/,
        // то цей плагін може бути корисним для вставки даних Frappe boot.
        // Але тоді цей index.html потрібно буде копіювати в www/cherga/ і перейменовувати.
        {
            name: 'transform-index.html',
            transformIndexHtml(html, context) {
                if (!context.server) { // Тільки для build
                    // Видаляємо стандартний div#app, якщо він не потрібен у фінальному HTML Frappe
                    // Або адаптуємо його
                    // Цей плагін зараз додає window.boot, що може бути корисним
                    return html.replace(
                        /<\/body>/,
                        `
            <script>
                {% for key in boot %}
                window["{{ key }}"] = {{ boot[key] | tojson }};
                {% endfor %}
            </script>
            </body>
            `,
                    )
                }
                return html
            },
        },
    ],
    resolve: {
        alias: {
            '@': path.resolve(__dirname, 'src'),
            'tailwind.config.js': path.resolve(__dirname, 'tailwind.config.js'),
        },
    },
    optimizeDeps: {
        include: ['feather-icons', 'showdown', 'tailwind.config.js'],
    },
    build: {
        outDir: 'dist', // Буде створено qms_cherga/frontend/dist/
        emptyOutDir: true,
        sourcemap: true,
        manifest: true,
        rollupOptions: {
            input: {
                kiosk: resolve(__dirname, 'kiosk.html'),
                display_board: resolve(__dirname, 'display_board.html'),
                operator_dashboard: resolve(__dirname, 'operator_dashboard.html'),
            },
            output: {
                // JS файли будуть у frontend/dist/js/
                entryFileNames: `js/[name].[hash].js`,
                chunkFileNames: `js/[name].[hash].js`,
                // CSS та інші ассети
                assetFileNames: (assetInfo) => {
                    if (assetInfo.name && assetInfo.name.endsWith('.css')) {
                        // CSS файли будуть у frontend/dist/css/
                        return `css/[name].[hash][extname]`;
                    }
                    // Інші ассети (зображення, шрифти)
                    // будуть у frontend/dist/other_assets/
                    return `other_assets/[name].[hash][extname]`;
                },
            },
        },
        commonjsOptions: {
            include: [/tailwind.config.js/, /node_modules/],
        },
    }
})