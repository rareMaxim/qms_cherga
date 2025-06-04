// deploy-vue-assets.js
import fs from 'fs-extra';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const VITE_DIST_DIR = path.join(__dirname, 'frontend', 'dist');
const FRAPPE_APP_PUBLIC_DIR = path.join(__dirname, 'qms_cherga', 'public');
const FRAPPE_APP_WWW_CHERGA_DIR = path.join(__dirname, 'qms_cherga', 'www'); // Використовується для HTML

const KIOSK_HTML_SOURCE_NAME = 'kiosk.html';
const DISPLAYBOARD_HTML_SOURCE_NAME = 'display_board.html';
const KIOSK_HTML_TARGET_NAME = 'qms_kiosk.html';
const DISPLAYBOARD_HTML_TARGET_NAME = 'qms_display_board.html';

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

        // 1. Очистити та створити цільові директорії для JS, CSS та інших ассетів
        //    ensureDir видалить директорію, якщо вона існує і не порожня, а потім створить її.
        //    Або можна спочатку видалити, а потім створити.
        //    fs.emptyDirSync(publicJsDir); // Очищає директорію
        //    fs.emptyDirSync(publicCssDir);
        //    fs.emptyDirSync(publicOtherAssetsDir);
        //    АБО більш безпечно - видалити і створити заново:
        console.log(`Cleaning up old assets in ${publicJsDir}`);
        await fs.remove(publicJsDir);
        console.log(`Cleaning up old assets in ${publicCssDir}`);
        await fs.remove(publicCssDir);
        console.log(`Cleaning up old assets in ${publicOtherAssetsDir}`);
        await fs.remove(path.join(FRAPPE_APP_PUBLIC_DIR, 'vue_manifest.json')); // Видаляємо старий маніфест

        await fs.ensureDir(publicJsDir);
        await fs.ensureDir(publicCssDir);
        await fs.ensureDir(publicOtherAssetsDir);
        await fs.ensureDir(FRAPPE_APP_WWW_CHERGA_DIR); // Цю директорію не очищаємо повністю, якщо там є інші файли

        // 2. Копіювати ассети (JS, CSS, other_assets)
        console.log('Copying assets...');
        if (await fs.pathExists(path.join(VITE_DIST_DIR, 'js'))) {
            await fs.copy(path.join(VITE_DIST_DIR, 'js'), publicJsDir, { overwrite: true });
        }
        if (await fs.pathExists(path.join(VITE_DIST_DIR, 'css'))) {
            await fs.copy(path.join(VITE_DIST_DIR, 'css'), publicCssDir, { overwrite: true });
        }
        if (await fs.pathExists(path.join(VITE_DIST_DIR, 'other_assets'))) {
            await fs.copy(path.join(VITE_DIST_DIR, 'other_assets'), publicOtherAssetsDir, { overwrite: true });
        }

        // 3. Копіювати HTML файли (вони мають фіксовані імена, тому overwrite: true достатньо)
        const kioskSourcePath = path.join(VITE_DIST_DIR, KIOSK_HTML_SOURCE_NAME);
        const kioskTargetPath = path.join(FRAPPE_APP_WWW_CHERGA_DIR, KIOSK_HTML_TARGET_NAME);
        if (await fs.pathExists(kioskSourcePath)) {
            await fs.copy(kioskSourcePath, kioskTargetPath, { overwrite: true });
            console.log(`Copied Kiosk HTML to ${kioskTargetPath}`);
        } else {
            console.warn(`Warning: Kiosk HTML source file not found: ${kioskSourcePath}`);
        }

        const displayboardSourcePath = path.join(VITE_DIST_DIR, DISPLAYBOARD_HTML_SOURCE_NAME);
        const displayboardTargetPath = path.join(FRAPPE_APP_WWW_CHERGA_DIR, DISPLAYBOARD_HTML_TARGET_NAME);
        if (await fs.pathExists(displayboardSourcePath)) {
            await fs.copy(displayboardSourcePath, displayboardTargetPath, { overwrite: true });
            console.log(`Copied Display Board HTML to ${displayboardTargetPath}`);
        } else {
            console.warn(`Warning: Display Board HTML source file not found: ${displayboardSourcePath}`);
        }

        // 4. Копіювати manifest.json
        const manifestSourcePath = path.join(VITE_DIST_DIR, 'manifest.json');
        if (await fs.pathExists(manifestSourcePath)) {
            await fs.copy(manifestSourcePath, path.join(FRAPPE_APP_PUBLIC_DIR, 'vue_manifest.json'), { overwrite: true });
            console.log(`Copied manifest.json to ${path.join(FRAPPE_APP_PUBLIC_DIR, 'vue_manifest.json')}`);
        }

        console.log('Vue assets deployed successfully!');

    } catch (error) {
        console.error('Error deploying Vue assets:', error);
        process.exit(1);
    }
}

deployAssets();