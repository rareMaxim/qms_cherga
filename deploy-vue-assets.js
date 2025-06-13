import fs from 'fs-extra';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const VITE_DIST_DIR = path.join(__dirname, 'frontend', 'dist');
const FRAPPE_APP_PUBLIC_DIR = path.join(__dirname, 'qms_cherga', 'public');
const FRAPPE_APP_WWW_CHERGA_DIR = path.join(__dirname, 'qms_cherga', 'www');

// Імена файлів-джерел (з dist) та файлів-цілей (в www)
const KIOSK_HTML_SOURCE_NAME = 'kiosk.html';
const DISPLAYBOARD_HTML_SOURCE_NAME = 'display_board.html';
const OPERATOR_DASHBOARD_HTML_SOURCE_NAME = 'operator_dashboard.html'; // <-- Новий файл

const KIOSK_HTML_TARGET_NAME = 'qms_kiosk.html';
const DISPLAYBOARD_HTML_TARGET_NAME = 'qms_display_board.html';
const OPERATOR_DASHBOARD_HTML_TARGET_NAME = 'qms_operator_dashboard.html'; // <-- Новий файл

async function deployAssets() {
    try {
        console.log('Starting deployment of Vue assets...');

        if (!await fs.pathExists(VITE_DIST_DIR)) {
            console.error(`Error: Vite distribution directory not found at ${VITE_DIST_DIR}. Run "yarn build" first.`);
            process.exit(1);
        }

        const publicJsDir = path.join(FRAPPE_APP_PUBLIC_DIR, 'js');
        const publicCssDir = path.join(FRAPPE_APP_PUBLIC_DIR, 'css');
        const publicOtherAssetsDir = path.join(FRAPPE_APP_PUBLIC_DIR, 'other_assets');

        // Очищення старих ассетів
        console.log(`Cleaning up old assets...`);
        await fs.remove(publicJsDir);
        await fs.remove(publicCssDir);
        await fs.remove(publicOtherAssetsDir);
        await fs.remove(path.join(FRAPPE_APP_PUBLIC_DIR, 'vue_manifest.json'));

        // Створення директорій
        await fs.ensureDir(publicJsDir);
        await fs.ensureDir(publicCssDir);
        await fs.ensureDir(publicOtherAssetsDir);
        await fs.ensureDir(FRAPPE_APP_WWW_CHERGA_DIR);

        // Копіювання JS, CSS та інших ассетів
        console.log('Copying assets...');
        await fs.copy(path.join(VITE_DIST_DIR, 'js'), publicJsDir);
        await fs.copy(path.join(VITE_DIST_DIR, 'css'), publicCssDir);
        if (await fs.pathExists(path.join(VITE_DIST_DIR, 'other_assets'))) {
            await fs.copy(path.join(VITE_DIST_DIR, 'other_assets'), publicOtherAssetsDir);
        }

        // Копіювання HTML файлів
        const copyHtml = async (sourceName, targetName) => {
            const sourcePath = path.join(VITE_DIST_DIR, sourceName);
            const targetPath = path.join(FRAPPE_APP_WWW_CHERGA_DIR, targetName);
            if (await fs.pathExists(sourcePath)) {
                await fs.copy(sourcePath, targetPath, { overwrite: true });
                console.log(`Copied ${sourceName} to ${targetPath}`);
            } else {
                console.warn(`Warning: Source HTML file not found: ${sourcePath}`);
            }
        };

        await copyHtml(KIOSK_HTML_SOURCE_NAME, KIOSK_HTML_TARGET_NAME);
        await copyHtml(DISPLAYBOARD_HTML_SOURCE_NAME, DISPLAYBOARD_HTML_TARGET_NAME);
        await copyHtml(OPERATOR_DASHBOARD_HTML_SOURCE_NAME, OPERATOR_DASHBOARD_HTML_TARGET_NAME); // <-- Копіюємо новий файл

        // Копіювання manifest.json
        const manifestSourcePath = path.join(VITE_DIST_DIR, 'manifest.json');
        if (await fs.pathExists(manifestSourcePath)) {
            await fs.copy(manifestSourcePath, path.join(FRAPPE_APP_PUBLIC_DIR, 'vue_manifest.json'));
            console.log(`Copied manifest.json.`);
        }

        console.log('Vue assets deployed successfully!');

    } catch (error) {
        console.error('Error deploying Vue assets:', error);
        process.exit(1);
    }
}

deployAssets();