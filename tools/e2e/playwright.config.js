// Configuración de los tests de extremo a extremo.
//
// El sitio se sirve bajo /cv/ a propósito. En producción, Traefik quita ese
// prefijo antes de llegar a Nginx, pero el HTML lleva `<base href="/cv/">`, así
// que el navegador pide /cv/styles.css. Servir src/ en la raíz haría que todo
// eso diera 404 y los tests medirían una página sin estilos ni JavaScript.
// Con el prefijo, las URLs son las mismas que ve un visitante.
const { defineConfig, devices } = require('@playwright/test');

module.exports = defineConfig({
	testDir: '.',
	timeout: 15000,
	expect: { timeout: 5000 },
	fullyParallel: true,
	forbidOnly: !!process.env.CI,
	retries: process.env.CI ? 1 : 0,
	reporter: process.env.CI ? 'github' : 'list',

	use: {
		// Ojo al navegar: `goto('/')` reemplaza el camino entero de la baseURL
		// y se sale de /cv/. Por eso los tests usan `goto('./')` y `goto('en/')`.
		baseURL: 'http://127.0.0.1:8123/cv/',
		trace: 'on-first-retry'
	},

	// `raiz/` es un directorio con un enlace `cv` a src/, creado por
	// preparar-servidor.sh. Así la ruta pública coincide con la real.
	webServer: {
		command: 'bash preparar-servidor.sh',
		url: 'http://127.0.0.1:8123/cv/',
		reuseExistingServer: !process.env.CI,
		timeout: 30000
	},

	projects: [
		{ name: 'escritorio', use: { ...devices['Desktop Chrome'] } },
		{ name: 'movil', use: { ...devices['Pixel 5'] } }
	]
});
